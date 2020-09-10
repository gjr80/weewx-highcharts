"""
highchartssearchlist.py

Search List Extensions to support the weewx-highcharts extension.

Copyright (C) 2016-20 Gary Roderick               gjroderick<at>gmail.com

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see http://www.gnu.org/licenses/.

Version: 0.3.0                                      Date: 10 September 2020

Revision History
    10 September 2020   v0.3.0
        - renamed file
        - now WeeWX 4.0.0 python 2/3 compatible
        - refactored get_extension_list() code in each SLE class
    4 September 2018    v0.2.2
        - minor comment editing
    16 May 2017         v0.2.1
        - Fixed bug with day/week windrose getSqlVectors call that resulted in
          'IndexError: list index out of range' error on line 962.
    4 May 2017          v0.2.0
        - Removed hard coding of weeWX-WD bindings for appTemp and Insolation
          data. Now attempts to obtain bindings for each from WeeWX-WD, if
          WeeWX-WD is not installed bindings are sought in weewx.conf
          [StdReport][[Highcharts]]. If no binding can be found appTemp and
          insolation data is omitted.
    22 November 2016    v0.1.0
       - initial implementation
"""

# python imports
import calendar
import datetime
import json
import logging
import time
from datetime import date

# WeeWX imports
import weewx
import weewx.cheetahgenerator
import weewx.units
import weeutil.weeutil
from user.highcharts import get_day_summary_vectors
from weewx.units import ValueTuple, getStandardUnitType, convert
from weeutil.weeutil import TimeSpan, genMonthSpans, startOfInterval, option_as_list

# import/setup logging, WeeWX v3 is syslog based but WeeWX v4 is logging based,
# try v4 logging and if it fails use v3 logging
try:
    # WeeWX4 logging
    import logging

    log = logging.getLogger(__name__)

    def logdbg(msg):
        log.debug(msg)

except ImportError:
    # WeeWX legacy (v3) logging via syslog
    import syslog

    def logmsg(level, msg):
        syslog.syslog(level, 'gw1000: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)


def round_none(value, places):
    """Round value to 'places' places but also permit a value of None."""

    if value is not None:
        try:
            return round(value, places)
        except TypeError:
            pass
    return None


def round_int(value, places):
    """Round value to 'places' but return as an integer if places=0."""

    if places == 0:
        return int(round(value, 0))
    else:
        return round(value, places)


def get_ago(dt, d_years=0, d_months=0):
    """ Function to return date object holding date d_years and d_months ago.

       If we try to return an invalid date due to differing month lengths
       (eg 30 Feb or 31 Sep) then just return the end of month (ie 28 Feb
       (if not a leap year else 29 Feb) or 30 Sep).
    """

    # get year number, month number and day number applying offset as required
    _y, _m, _d = dt.year + d_years, dt.month + d_months, dt.day
    # calculate actual month number taking into account EOY rollover
    _a, _m = divmod(_m - 1, 12)
    # calculate and return date object
    _eom = calendar.monthrange(_y + _a, _m + 1)[1]
    return date(_y + _a, _m + 1, _d if _d <= _eom else _eom)


class HighchartsMinRanges(weewx.cheetahgenerator.SearchList):
    """SearchList to return y-axis minimum range values for each plot."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsMinRanges, self).__init__(generator)

    def get_extension_list(self, timespan, db_lookup):
        """Obtain y-axis minimum range values as a list of dictionaries.

        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
         """

        t1 = time.time()

        mr_dict = {}
        # get our MinRange config dict if it exists
        mr_config_dict = self.generator.skin_dict['Extras'].get('MinRange') \
            if 'Extras' in self.generator.skin_dict else None
        # if we have a config dict then loop through any key/value pairs
        # discarding any pairs that are non numeric
        if mr_config_dict:
            for _key, _value in mr_config_dict.items():
                _value_list = option_as_list(_value)
                if len(_value_list) > 1:
                    try:
                        _group = weewx.units._getUnitGroup(_key)
                        _value_vt = ValueTuple(float(_value_list[0]),
                                               _value_list[1],
                                               _group)
                    except (ValueError, KeyError):
                        continue
                    else:
                        _range = self.generator.converter.convert(_value_vt).value
                else:
                    try:
                        _range = float(_value)
                    except ValueError:
                        continue
                mr_dict[_key + '_min_range'] = _range
        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsMinRanges SLE executed in %0.3f seconds" % (t2 - t1))
        # return our data dict
        return [mr_dict]


class HighchartsWeek(weewx.cheetahgenerator.SearchList):
    """SearchList to generate JSON vectors for Highcharts week plots."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsWeek, self).__init__(generator)

        # Where do we get our maxSolarRad and appTemp data? WeeWX 4.0.0
        # introduced the wview_extended schema which contains fields appTemp
        # and maxSolarRad but they may or may not contain data. The default
        # schema for WeeWX 3.x and earlier does not contain maxSolarRad and
        # appTemp fields but a user may have added them. In addition 3rd party
        # extensions such as WeeWX-WD can provide maxSolarRad and appTemp. To
        # support obtaining maxSolarRad and appTemp data from databases other
        # than the 'WeeWX' database we will support a config option under
        # [StdReport][[Highcharts]] where the user can specify bindings for the
        # databases that contain maxSolarRad and appTemp.

        # maxSolarRad
        if 'Highcharts' in generator.config_dict['StdReport']:
            insolation_binding = generator.config_dict['StdReport']['Highcharts'].get('insolation_binding')
            # just in case insolation_binding is included but not set
            if insolation_binding == '':
                insolation_binding = None
        self.insolation_binding = insolation_binding
        # appTemp
        if 'Highcharts' in generator.config_dict['StdReport']:
            apptemp_binding = generator.config_dict['StdReport']['Highcharts'].get('apptemp_binding')
            # just in case apptemp_binding is included but not set
            if apptemp_binding == '':
                apptemp_binding = None
        self.apptemp_binding = apptemp_binding

    def get_vector(self, db_manager, timespan, obs_type,
                   aggregate_type=None,
                   aggregate_interval=None):
        """Get a data and timestamp vector for a given obs.

        Returns a two vectors. The first is the obs data vector and the second
        is the timestamp vector in ms.
        """

        # get our vectors as ValueTuples, wrap in a try..except in case
        # obs_type does not exist
        try:
            (t_start_vt, t_stop_vt, obs_vt) = db_manager.getSqlVectors(timespan,
                                                                       obs_type,
                                                                       aggregate_type=aggregate_type,
                                                                       aggregate_interval=aggregate_interval)
        except weewx.UnknownType:
            logdbg("Unknown type '%s'" % obs_type)
            return None, None
        # convert our obs ValueTuple
        obs_vt = self.generator.converter.convert(obs_vt)
        # can't use ValueHelper so round our results manually
        # first get the number of decimal points
        round_places = int(self.generator.skin_dict['Units']['StringFormats'].get(obs_vt.unit, "1f")[-2])
        # now do the rounding, our result is a vector
        obs_rounded_vector = [round_none(x, round_places) for x in obs_vt.value]
        # get our time vector in ms (Highcharts requirement)
        t_ms_vector = [float(x) * 1000 for x in t_stop_vt.value]
        # return our time and obs data vectors
        return obs_rounded_vector, t_ms_vector


    def get_extension_list(self, timespan, db_lookup):
        """Generate the JSON vectors and return as a list of dictionaries.

        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
         """

        t1 = time.time()

        # get UTC offset
        stop_struct = time.localtime(timespan.stop)
        utc_offset = (calendar.timegm(stop_struct) - calendar.timegm(time.gmtime(time.mktime(stop_struct))))/60

        # Our period of interest is a seven day period but starting on a start
        # of day boundary. Get a TimeSpan object covering this period.
        # first get the start of today
        _ts = weeutil.weeutil.startOfDay(timespan.stop)
        # get the start of today as a datetime object so we can do some
        # daylight saving safe date arithmetic
        _ts_dt = datetime.datetime.fromtimestamp(_ts)
        # now go back seven days in a daylight saving safe manner
        _start_dt = _ts_dt - datetime.timedelta(days=7)
        # and convert back to a timestamp
        _start_ts = time.mktime(_start_dt.timetuple())
        # get a TimeSpan object representing the time span of interest
        t_span = TimeSpan(_start_ts, timespan.stop)

        # get our temperature vector
        outtemp_vector, outtemp_time_vector = self.get_vector(db_lookup(),
                                                              timespan=t_span,
                                                              obs_type='outTemp')

        # get our dewpoint vector
        dewpoint_vector, dewpoint_time_vector = self.get_vector(db_lookup(),
                                                                timespan=t_span,
                                                                obs_type='dewpoint')

        # Get our apparent temperature vector. If we have a binding for appTemp
        # data then use it otherwise try to use the current WeeWX database but
        # be prepared to catch the exception if field appTemp does not exist.
        # If we don't have a working binding then set the vector to None.
        if self.apptemp_binding is not None:
            # we have an appTemp binding, try to use it
            try:
                db_manager = db_lookup(self.apptemp_binding)
            except weewx.UnknownBinding:
                # can't find that binding so log it and then try to use our
                # default binding
                logdbg("Invalid binding '%s', using default binding instead" % (self.apptemp_binding, ))
                db_manager = db_lookup()
        else:
            db_manager = db_lookup()
        try:
            apptemp_vector, apptemp_time_vector = self.get_vector(db_manager,
                                                                  timespan=t_span,
                                                                  obs_type='appTemp')
        except:
            raise
            # apptemp_vector = None
            # apptemp_time_vector = None
        # get our wind chill vector
        windchill_vector, windchill_time_vector = self.get_vector(db_lookup(),
                                                                  timespan=t_span,
                                                                  obs_type='windchill')
        # get our heat index vector
        heatindex_vector, heatindex_time_vector = self.get_vector(db_lookup(),
                                                                  timespan=t_span,
                                                                  obs_type='heatindex')
        # get our humidity vector
        outhumidity_vector, outhumidity_time_vector = self.get_vector(db_lookup(),
                                                                      timespan=t_span,
                                                                      obs_type='outHumidity')
        # get our barometer vector
        barometer_vector, barometer_time_vector = self.get_vector(db_lookup(),
                                                                  timespan=t_span,
                                                                  obs_type='barometer')
        # get our wind speed vector
        windspeed_vector, windspeed_time_vector = self.get_vector(db_lookup(),
                                                                  timespan=t_span,
                                                                  obs_type='windSpeed')
        # get our wind gust vector
        windgust_vector, windgust_time_vector = self.get_vector(db_lookup(),
                                                                timespan=t_span,
                                                                obs_type='windGust')
        # get our wind direction vector
        winddir_vector, winddir_time_vector = self.get_vector(db_lookup(),
                                                              timespan=t_span,
                                                              obs_type='windDir')
        # get our rain vector, need to sum over the hour
        rain_vector, rain_time_vector = self.get_vector(db_lookup(),
                                                        timespan=t_span,
                                                        obs_type='rain',
                                                        aggregate_type='sum',
                                                        aggregate_interval=3600)
        # Check if our last interval is a partial hour. If it is then round up
        # the last timestamp in the time vector to an hour boundary. This
        # avoids display issues with the column chart. We need to make sure we
        # have at least two intervals though.
        if len(rain_time_vector) > 1:
            if rain_time_vector[-1] < rain_time_vector[-2] + 3600:
                rain_time_vector[-1] = rain_time_vector[-2] + 3600
        # get our radiation vector
        radiation_vector, radiation_time_vector = self.get_vector(db_lookup(),
                                                                  timespan=t_span,
                                                                  obs_type='radiation')
        # Get our insolation vector. If we have a binding for maxSolarRad data
        # then use it otherwise try to use the current WeeWX database but be
        # prepared to catch the exception if field maxSolarRad does not exist.
        # If we don't have a working binding then set the vector to None.
        if self.insolation_binding is not None:
            # we have an insolation binding, try to use it
            try:
                db_manager = db_lookup(self.insolation_binding)
            except weewx.UnknownBinding:
                # can't find that binding so log it and then try to use our
                # default binding
                logdbg("Invalid binding '%s', using default binding instead" % (self.insolation_binding, ))
                db_manager = db_lookup()
        else:
            db_manager = db_lookup()
        try:
            insolation_vector, insolation_time_vector = self.get_vector(db_manager,
                                                                        timespan=t_span,
                                                                        obs_type='maxSolarRad')
        except:
            raise
            # insolation_vector = None
            # insolation_time_vector = None
        # get our UV vector
        uv_vector, uv_time_vector = self.get_vector(db_lookup(),
                                                    timespan=t_span,
                                                    obs_type='UV')
        # format our vectors in json format. Need the zip() to get time/value pairs
        # assumes all vectors have the same number of elements
        outtemp_json = json.dumps(list(zip(outtemp_time_vector, outtemp_vector))) if outtemp_vector is not None else None
        dewpoint_json = json.dumps(list(zip(dewpoint_time_vector, dewpoint_vector))) if dewpoint_vector is not None else None
        apptemp_json = json.dumps(list(zip(apptemp_time_vector, apptemp_vector))) if apptemp_vector is not None else None
        windchill_json = json.dumps(list(zip(windchill_time_vector, windchill_vector))) if windchill_vector is not None else None
        heatindex_json = json.dumps(list(zip(heatindex_time_vector, heatindex_vector))) if heatindex_vector is not None else None
        outhumidity_json = json.dumps(list(zip(outhumidity_time_vector, outhumidity_vector))) if outhumidity_vector is not None else None
        barometer_json = json.dumps(list(zip(barometer_time_vector, barometer_vector))) if barometer_vector is not None else None
        windspeed_json = json.dumps(list(zip(windspeed_time_vector, windspeed_vector))) if windspeed_vector is not None else None
        windgust_json = json.dumps(list(zip(windgust_time_vector, windgust_vector))) if windgust_vector is not None else None
        winddir_json = json.dumps(list(zip(winddir_time_vector, winddir_vector))) if winddir_vector is not None else None
        rain_json = json.dumps(list(zip(rain_time_vector, rain_vector))) if rain_vector is not None else None
        radiation_json = json.dumps(list(zip(radiation_time_vector, radiation_vector))) if radiation_vector is not None else None
        insolation_json = json.dumps(list(zip(insolation_time_vector, insolation_vector))) if insolation_vector is not None else None
        uv_json = json.dumps(list(zip(uv_time_vector, uv_vector))) if uv_vector is not None else None

        # put into a dictionary to return
        search_list_extension = {'outTempWeekjson': outtemp_json,
                                 'dewpointWeekjson': dewpoint_json,
                                 'appTempWeekjson': apptemp_json,
                                 'windchillWeekjson': windchill_json,
                                 'heatindexWeekjson': heatindex_json,
                                 'outHumidityWeekjson': outhumidity_json,
                                 'barometerWeekjson': barometer_json,
                                 'windSpeedWeekjson': windspeed_json,
                                 'windGustWeekjson': windgust_json,
                                 'windDirWeekjson': winddir_json,
                                 'rainWeekjson': rain_json,
                                 'radiationWeekjson': radiation_json,
                                 'insolationWeekjson': insolation_json,
                                 'uvWeekjson': uv_json,
                                 'utcOffset': utc_offset,
                                 'weekPlotStart': _start_ts * 1000,
                                 'weekPlotEnd': timespan.stop * 1000}
        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsWeek SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [search_list_extension]


class HighchartsYear(weewx.cheetahgenerator.SearchList):
    """SearchList to generate JSON vectors for Highcharts year plots."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsYear, self).__init__(self, generator)

        # Do we have a binding for appTemp? WeeWX-WD can provide (if installed)
        # or the user can specify in [StdReport][[Highcharts]] or failing this
        # we will ignore appTemp.

        # first try to get the binding from WeeWX-WD if installed
        try:
            self.apptemp_binding = generator.config_dict['Weewx-WD'].get('data_binding')
        except KeyError:
            # likely WeeWX-WD is not installed so set to None
            self.apptemp_binding = None
        if self.apptemp_binding is None:
            # try [StdReport][[Highcharts]]
            try:
                self.apptemp_binding = generator.config_dict['StdReport']['Highcharts'].get('apptemp_binding')
                # just in case apptemp_binding is included but not set
                if self.apptemp_binding == '':
                    self.apptemp_binding = None
            except KeyError:
                # should only occur if the user changed the name of
                # [[Highcharts]] in [StdReport]
                self.apptemp_binding = None

    def get_extension_list(self, timespan, db_lookup):
        """Generate the JSON vectors and return as a list of dictionaries.

        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
         """

        t1 = time.time()

        # get UTC offset
        stop_struct = time.localtime(timespan.stop)
        utc_offset = (calendar.timegm(stop_struct) - calendar.timegm(time.gmtime(time.mktime(stop_struct)))) / 60

        # our start time is one year ago from midnight at the start of today
        # first get the start of today
        _ts = weeutil.weeutil.startOfDay(timespan.stop)
        # then go back 1 year
        _ts_dt = datetime.datetime.fromtimestamp(_ts)
        try:
            _start_dt = _ts_dt.replace(year=_ts_dt.year-1)
        except ValueError:
            _start_dt = _ts_dt.replace(year=_ts_dt.year-1, day=_ts_dt.day-1)
        _start_ts = time.mktime(_start_dt.timetuple())
        _timespan = TimeSpan(_start_ts, timespan.stop)

        # get our outTemp vectors
        (outtemp_time_vt, outtemp_dict) = get_day_summary_vectors(db_lookup(), 'outTemp', _timespan, ['min', 'max', 'avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        outtemp_min_vt = self.generator.converter.convert(outtemp_dict['min'])
        outtemp_max_vt = self.generator.converter.convert(outtemp_dict['max'])
        outtemp_avg_vt = self.generator.converter.convert(outtemp_dict['avg'])

        # Get our appTemp vectors. appTemp data is not normally archived so
        # only try to get it if we have a binding for it. Wrap in a try..except
        # to catch any errors. If we don't have a binding then set the vectors
        # to None
        if self.apptemp_binding is not None:
            try:
                (apptemp_time_vt, apptemp_dict) = get_day_summary_vectors(db_lookup('wd_binding'),
                                                                       'appTemp',
                                                                       _timespan,
                                                                       ['min', 'max', 'avg'])
                # get our vector ValueTuple out of the dictionary and convert it
                apptemp_min_vt = self.generator.converter.convert(apptemp_dict['min'])
                apptemp_max_vt = self.generator.converter.convert(apptemp_dict['max'])
                apptemp_avg_vt = self.generator.converter.convert(apptemp_dict['avg'])
            except weewx.UnknownBinding:
                raise
        else:
            apptemp_min_vt = None
            apptemp_max_vt = None
            apptemp_avg_vt = None

        # get our windchill vector
        (windchill_time_vt, windchill_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'windchill',
                                                                   _timespan,
                                                                   ['avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        windchill_avg_vt = self.generator.converter.convert(windchill_dict['avg'])

        # get our heatindex vector
        (heatindex_time_vt, heatindex_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'heatindex',
                                                                   _timespan,
                                                                   ['avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        heatindex_avg_vt = self.generator.converter.convert(heatindex_dict['avg'])
        # get our humidity vectors
        (outhumidity_time_vt, outhumidity_dict) = get_day_summary_vectors(db_lookup(),
                                                                       'outHumidity',
                                                                       _timespan,
                                                                       ['min', 'max', 'avg'])

        # get our barometer vectors
        (barometer_time_vt, barometer_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'barometer',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        barometer_min_vt = self.generator.converter.convert(barometer_dict['min'])
        barometer_max_vt = self.generator.converter.convert(barometer_dict['max'])
        barometer_avg_vt = self.generator.converter.convert(barometer_dict['avg'])

        # get our wind vectors
        (wind_time_vt, wind_dict) = get_day_summary_vectors(db_lookup(),
                                                         'wind',
                                                         _timespan,
                                                         ['max', 'avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        wind_max_vt = self.generator.converter.convert(wind_dict['max'])
        wind_avg_vt = self.generator.converter.convert(wind_dict['avg'])

        # get our windSpeed vectors
        (windspeed_time_vt, windspeed_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'windSpeed',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])
        # get our vector ValueTuple out of the dictionary and convert it
        windspeed_max_vt = self.generator.converter.convert(windspeed_dict['max'])
        windspeed_avg_vt = self.generator.converter.convert(windspeed_dict['avg'])

        # get our windDir vectors
        (winddir_time_vt, winddir_dict) = get_day_summary_vectors(db_lookup(),
                                                               'wind',
                                                               _timespan,
                                                               ['vecdir'])

        # get our rain vectors
        (rain_time_vt, rain_dict) = get_day_summary_vectors(db_lookup(),
                                                         'rain',
                                                         _timespan,
                                                         ['sum'])
        # get our vector ValueTuple out of the dictionary and convert it
        rain_sum_vt = self.generator.converter.convert(rain_dict['sum'])

        # get our radiation vectors
        (radiation_time_vt, radiation_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'radiation',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])

        # get our UV vectors
        (uv_time_vt, uv_dict) = get_day_summary_vectors(db_lookup(),
                                                     'UV',
                                                     _timespan,
                                                     ['min', 'max', 'avg'])

        # get no of decimal places to use when formatting results
        temp_places = int(self.generator.skin_dict['Units']['StringFormats'].get(outtemp_min_vt[1], "1f")[-2])
        outhumidity_places = int(self.generator.skin_dict['Units']['StringFormats'].get(outhumidity_dict['min'][1], "1f")[-2])
        barometer_places = int(self.generator.skin_dict['Units']['StringFormats'].get(barometer_min_vt[1], "1f")[-2])
        wind_places = int(self.generator.skin_dict['Units']['StringFormats'].get(wind_max_vt[1], "1f")[-2])
        windspeed_places = int(self.generator.skin_dict['Units']['StringFormats'].get(windspeed_max_vt[1], "1f")[-2])
        winddir_places = int(self.generator.skin_dict['Units']['StringFormats'].get(winddir_dict['vecdir'][1], "1f")[-2])
        rain_places = int(self.generator.skin_dict['Units']['StringFormats'].get(rain_sum_vt[1], "1f")[-2])
        radiation_places = int(self.generator.skin_dict['Units']['StringFormats'].get(radiation_dict['max'][1], "1f")[-2])
        uv_places = int(self.generator.skin_dict['Units']['StringFormats'].get(uv_dict['max'][1], "1f")[-2])

        # get our time vector in ms
        time_ms = [float(x) * 1000 for x in outtemp_time_vt[0]]

        # round our values from our ValueTuples
        outtemp_min_round = [round_none(x, temp_places) for x in outtemp_min_vt[0]]
        outtemp_max_round = [round_none(x, temp_places) for x in outtemp_max_vt[0]]
        outtemp_avg_round = [round_none(x, temp_places) for x in outtemp_avg_vt[0]]
        # round our appTemp values, if we don't have any then set it to None
        try:
            apptemp_min_round = [round_none(x, temp_places) for x in apptemp_min_vt[0]]
            apptemp_max_round = [round_none(x, temp_places) for x in apptemp_max_vt[0]]
            apptemp_avg_round = [round_none(x, temp_places) for x in apptemp_avg_vt[0]]
        except TypeError:
            apptemp_min_round = None
            apptemp_max_round = None
            apptemp_avg_round = None
        windchill_avg_round = [round_none(x, temp_places) for x in windchill_avg_vt[0]]
        heatindex_avg_round = [round_none(x, temp_places) for x in heatindex_avg_vt[0]]
        outhumidity_min_round = [round_none(x, outhumidity_places) for x in outhumidity_dict['min'][0]]
        outhumidity_max_round = [round_none(x, outhumidity_places) for x in outhumidity_dict['max'][0]]
        outhumidity_avg_round = [round_none(x, outhumidity_places) for x in outhumidity_dict['avg'][0]]
        barometer_min_round = [round_none(x, barometer_places) for x in barometer_min_vt[0]]
        barometer_max_round = [round_none(x, barometer_places) for x in barometer_max_vt[0]]
        barometer_avg_round = [round_none(x, barometer_places) for x in barometer_avg_vt[0]]
        wind_max_round = [round_none(x, wind_places) for x in wind_max_vt[0]]
        wind_avg_round = [round_none(x, wind_places) for x in wind_avg_vt[0]]
        windspeed_max_round = [round_none(x, windspeed_places) for x in windspeed_max_vt[0]]
        windspeed_avg_round = [round_none(x, windspeed_places) for x in windspeed_avg_vt[0]]
        winddir_round = [round_none(x, winddir_places) for x in winddir_dict['vecdir'][0]]
        rain_sum_round = [round_none(x, rain_places) for x in rain_sum_vt[0]]
        radiation_max_round = [round_none(x, radiation_places) for x in radiation_dict['max'][0]]
        radiation_avg_round = [round_none(x, radiation_places) for x in radiation_dict['avg'][0]]
        uv_max_round = [round_none(x, uv_places) for x in uv_dict['max'][0]]
        uv_avg_round = [round_none(x, uv_places) for x in uv_dict['avg'][0]]

        # produce our JSON strings
        outtemp_min_max_json = json.dumps(list(zip(time_ms, outtemp_min_round, outtemp_max_round)))
        outtemp_avg_json = json.dumps(list(zip(time_ms, outtemp_avg_round)))
        # appTemp. If we don't have any source data then set our JSON string to
        # None
        if apptemp_min_round is not None and apptemp_max_round is not None:
            app_temp_min_max_json = json.dumps(list(zip(time_ms, apptemp_min_round, apptemp_max_round)))
        else:
            app_temp_min_max_json = None
        if apptemp_min_round is not None:
            app_temp_min_json = json.dumps(list(zip(time_ms, apptemp_min_round)))
        else:
            app_temp_min_json = None
        if apptemp_max_round is not None:
            app_temp_max_json = json.dumps(list(zip(time_ms, apptemp_max_round)))
        else:
            app_temp_max_json = None
        if apptemp_avg_round is not None:
            app_temp_avg_json = json.dumps(list(zip(time_ms, apptemp_avg_round)))
        else:
            app_temp_avg_json = None
        windchill_avg_json = json.dumps(list(zip(time_ms, windchill_avg_round)))
        heatindex_avg_json = json.dumps(list(zip(time_ms, heatindex_avg_round)))
        outhumidity_min_max_json = json.dumps(list(zip(time_ms, outhumidity_min_round, outhumidity_max_round)))
        outhumidity_min_json = json.dumps(list(zip(time_ms, outhumidity_min_round)))
        outhumidity_max_json = json.dumps(list(zip(time_ms, outhumidity_max_round)))
        outhumidity_avg_json = json.dumps(list(zip(time_ms, outhumidity_avg_round)))
        barometer_min_max_json = json.dumps(list(zip(time_ms, barometer_min_round, barometer_max_round)))
        barometer_min_json = json.dumps(list(zip(time_ms, barometer_min_round)))
        barometer_max_json = json.dumps(list(zip(time_ms, barometer_max_round)))
        barometer_avg_json = json.dumps(list(zip(time_ms, barometer_avg_round)))
        wind_max_json = json.dumps(list(zip(time_ms, wind_max_round)))
        wind_avg_json = json.dumps(list(zip(time_ms, wind_avg_round)))
        windspeed_max_json = json.dumps(list(zip(time_ms, windspeed_max_round)))
        windspeed_avg_json = json.dumps(list(zip(time_ms, windspeed_avg_round)))
        winddir_json = json.dumps(list(zip(time_ms, winddir_round)))
        rain_sum_json = json.dumps(list(zip(time_ms, rain_sum_round)))
        radiation_max_json = json.dumps(list(zip(time_ms, radiation_max_round)))
        radiation_avg_json = json.dumps(list(zip(time_ms, radiation_avg_round)))
        uv_max_json = json.dumps(list(zip(time_ms, uv_max_round)))
        uv_avg_json = json.dumps(list(zip(time_ms, uv_avg_round)))

        # put into a dictionary to return
        search_list_extension = {'outtemp_min_max_json': outtemp_min_max_json,
                                 'outtemp_avg_json': outtemp_avg_json,
                                 'app_temp_min_max_json': app_temp_min_max_json,
                                 'app_temp_min_json': app_temp_min_json,
                                 'app_temp_max_json': app_temp_max_json,
                                 'app_temp_avg_json': app_temp_avg_json,
                                 'windchill_avg_json': windchill_avg_json,
                                 'heatindex_avg_json': heatindex_avg_json,
                                 'outhumidity_min_max_json': outhumidity_min_max_json,
                                 'outhumidity_min_json': outhumidity_min_json,
                                 'outhumidity_max_json': outhumidity_max_json,
                                 'outhumidity_avg_json': outhumidity_avg_json,
                                 'barometer_min_max_json': barometer_min_max_json,
                                 'barometer_min_json': barometer_min_json,
                                 'barometer_max_json': barometer_max_json,
                                 'barometer_avg_json': barometer_avg_json,
                                 'wind_max_json': wind_max_json,
                                 'wind_avg_json': wind_avg_json,
                                 'windspeed_max_json': windspeed_max_json,
                                 'windspeed_avg_json': windspeed_avg_json,
                                 'winddir_json': winddir_json,
                                 'rain_sum_json': rain_sum_json,
                                 'radiation_max_json': radiation_max_json,
                                 'radiation_avg_json': radiation_avg_json,
                                 'uv_max_json': uv_max_json,
                                 'uv_avg_json': uv_avg_json,
                                 'utcOffset': utc_offset,
                                 'yearPlotStart': _timespan.start * 1000,
                                 'yearPlotEnd': _timespan.stop * 1000}

        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsYear SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [search_list_extension]


class highchartsWindRose(weewx.cheetahgenerator.SearchList):
    """SearchList to generate JSON vectors for Highcharts windrose plots."""

    def __init__(self, generator):
        # initialize my base class:
        super(highchartsWindRose, self).__init__(self, generator)

        # get a dictionary of ous skin settings
        self.windrose_dict = self.generator.skin_dict['Extras']['WindRose']
        # look for plot title, if not defined then set a default
        try:
            self.title = self.windrose_dict['title'].strip()
        except KeyError:
            self.title = 'Wind Rose'
        # look for plot source, if not defined then set a default
        try:
            self.source = self.windrose_dict['source'].strip()
        except KeyError:
            pass
        if self.source != 'windSpeed' and self.source != 'windGust':
            self.source = 'windSpeed'
        if self.source == 'windSpeed':
            self.dir = 'windDir'
        else:
            self.dir = 'windGustDir'
        # look for aggregate type
        try:
            self.agg_type = self.windrose_dict['aggregate_type'].strip().lower()
            if self.agg_type not in [None, 'avg', 'max', 'min']:
                self.agg_type = None
        except KeyError:
            self.agg_type = None
        # look for aggregate interval
        try:
            self.agg_interval = int(self.windrose_dict['aggregate_interval'])
            if self.agg_interval == 0:
                self.agg_interval = None
        except (KeyError, TypeError, ValueError):
            self.agg_interval = None
        # look for speed band boundaries, if not defined then set some defaults
        try:
            self.speedfactor = self.windrose_dict['speedfactor']
        except KeyError:
            self.speedfactor = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
        if len(self.speedfactor) != 7 or max(self.speedfactor) > 1.0 or min(self.speedfactor) < 0.0:
            self.speedfactor = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
        # look for petal colours, if not defined then set some defaults
        try:
            self.petal_colours = self.windrose_dict['petal_colors']
        except KeyError:
            self.petal_colours = ['lightblue', 'blue', 'midnightblue',
                                  'forestgreen', 'limegreen', 'green',
                                  'greenyellow']
        if len(self.petal_colours) != 7:
            self.petal_colours = ['lightblue', 'blue', 'midnightblue',
                                  'forestgreen', 'limegreen', 'green',
                                  'greenyellow']
        for x in range(len(self.petal_colours)-1):
            if self.petal_colours[x][0:2] == '0x':
                self.petal_colours[x] = '#' + self.petal_colours[x][2:]
        # look for number of petals, if not defined then set a default
        try:
            self.petals = int(self.windrose_dict['petals'])
        except KeyError:
            self.petals = 8
        if self.petals is None or self.petals == 0:
            self.petals = 8
        # set our list of direction based on number of petals
        if self.petals == 16:
            self.directions = ['N', 'NNE', 'NE', 'ENE',
                               'E', 'ESE', 'SE', 'SSE',
                               'S', 'SSW', 'SW', 'WSW',
                               'W', 'WNW', 'NW', 'NNW']
        elif self.petals == 8:
            self.directions = ['N', 'NE', 'E', 'SE',
                               'S', 'SW', 'W', 'NW']
        elif self.petals == 4:
            self.directions = ['N', 'E', 'S', 'W']
        # look for legend title, if not defined then set True
        try:
            self.legend_title = self.windrose_dict['legend_title'].strip().lower() == 'true'
        except KeyError:
            self.legend_title = True
        # look for band percent, if not defined then set True
        try:
            self.band_percent = self.windrose_dict['band_percent'].strip().lower() == 'true'
        except KeyError:
            self.band_percent = True
        # look for % precision, if not defined then set a default
        try:
            self.precision = int(self.windrose_dict['precision'])
        except KeyError:
            self.precision = 1
        if self.precision is None:
            self.precision = 1
        # look for bullseye diameter, if not defined then set a default
        try:
            self.bullseye_size = int(self.windrose_dict['bullseye_size'])
        except KeyError:
            self.bullseye_size = 3
        if self.bullseye_size is None:
            self.bullseye_size = 3
        # look for bullseye colour, if not defined then set some defaults
        try:
            self.bullseye_colour = self.windrose_dict['bullseye_color']
        except KeyError:
            self.bullseye_colour = 'white'
        if self.bullseye_colour is None:
            self.bullseye_colour = 'white'
        if self.bullseye_colour[0:2] == '0x':
            self.bullseye_colour = '#' + self.bullseye_colour[2:]
        # look for 'calm' upper limit ie the speed below which we consider aggregate
        # wind speeds to be 'calm' (or 0)
        try:
            self.calm_limit = float(self.windrose_dict['calm_limit'])
        except:
            self.calm_limit = 0.1

    def calc_windrose(self, timespan, db_lookup, period):
        """Function to calculate windrose JSON data for a given timespan."""

        # initialise a dictionary for our results
        wr_dict = {}
        if period <= 604800:
            # week or less, get our vectors from archive via getSqlVectors
            # get our wind speed vector
            t_span = TimeSpan(timespan.stop - period + 1, timespan.stop)
            (time_vec_speed_start_vt, time_vec_speed_vt, speed_vec_vt) = db_lookup().getSqlVectors(t_span,
                                                                                                   self.source,
                                                                                                   None,
                                                                                                   None)
            # convert it
            speed_vec_vt = self.generator.converter.convert(speed_vec_vt)
            # get our wind direction vector
            t_span = TimeSpan(timespan.stop-period + 1, timespan.stop)
            (time_vec_dir_start_vt, time_vec_dir_stop_vt, direction_vec_vt) = db_lookup().getSqlVectors(t_span,
                                                                                                        self.dir,
                                                                                                        None,
                                                                                                        None)
        else:
            # get our vectors from daily summaries using custom getStatsVectors
            # get our data tuples for speed
            (time_vec_speed_vt, speed_dict) = get_day_summary_vectors(db_lookup(),
                                                                   'wind',
                                                                   TimeSpan(timespan.stop - period, timespan.stop),
                                                                   ['avg'])
            # get our vector ValueTuple out of the dictionary and convert it
            speed_vec_vt = self.generator.converter.convert(speed_dict['avg'])
            # get our data tuples for direction
            (time_vec_dir_vt, dir_dict) = get_day_summary_vectors(db_lookup(),
                                                               'wind',
                                                               TimeSpan(timespan.stop - period, timespan.stop),
                                                               ['vecdir'])
            # get our vector ValueTuple out of the dictionary, no need to convert
            direction_vec_vt = dir_dict['vecdir']
        # get a string with our speed units
        speed_units_str = self.generator.skin_dict['Units']['Labels'].get(speed_vec_vt[1]).strip()
        # to get a better display we will set our upper speed to a multiple of 10
        # find maximum speed from our data
        max_speed = max(speed_vec_vt[0])
        # set upper speed range for our plot
        max_speed_range = (int(max_speed/10.0) + 1) * 10
        # setup a list to hold the cutoff speeds for our stacked columns on our
        # wind rose.
        speed_list = [0 for x in range(7)]
        # setup a list to hold the legend item text for each of our speed bands
        # (or legend labels)
        legend_labels = ["" for x in range(7)]
        legend_no_labels = ["" for x in range(7)]
        i = 1
        while i < 7:
            speed_list[i] = self.speedfactor[i] * max_speed_range
            i += 1
        # setup 2D list for wind direction
        # wind_bin[0][0..self.petals] holds the calm or 0 speed counts for each
        # of self.petals (usually 16) compass directions ([0][0] for N, [0][1]
        # for ENE (or NE oe E depending self.petals) etc)
        # wind_bin[1][0..self.petals] holds the 1st speed band speed counts for
        # each of self.petals (usually 16) compass directions ([1][0] for
        # N, [1][1] for ENE (or NE oe E depending self.petals) etc).
        wind_bin = [[0 for x in range(self.petals)] for x in range(7)]
        # Setup a list to hold sample count (speed>0) for each direction. Used
        # to aid in bullseye scaling
        dir_bin = [0 for x in range(self.petals)]
        # setup list to hold obs counts for each speed range (irrespective of
        # direction)
        # [0] = calm
        # [1] = >0 and < 1st speed
        # [2] = >1st speed and <2nd speed
        # .....
        # [6] = >4th speed and <5th speed
        # [7] = >5th speed and <6th speed
        speed_bin = [0 for x in range(7)]
        # how many obs do we have?
        samples = len(time_vec_speed_vt[0])
        # calc factor to be applied to convert counts to %
        pcent_factor = 100.0/samples
        # Loop through each sample and increment direction counts
        # and speed ranges for each direction as necessary. 'None'
        # direction is counted as 'calm' (or 0 speed) and
        # (by definition) no direction and are plotted in the
        # 'bullseye' on the plot
        i = 0
        while i < samples:
            if (speed_vec_vt[0][i] is None) or (direction_vec_vt[0][i] is None):
                speed_bin[0] += 1
            else:
                bin_num = int((direction_vec_vt[0][i]+11.25)/22.5) % self.petals
                if speed_vec_vt[0][i] <= self.calm_limit:
                    speed_bin[0] += 1
                elif speed_vec_vt[0][i] > speed_list[5]:
                    wind_bin[6][bin_num] += 1
                elif speed_vec_vt[0][i] > speed_list[4]:
                    wind_bin[5][bin_num] += 1
                elif speed_vec_vt[0][i] > speed_list[3]:
                    wind_bin[4][bin_num] += 1
                elif speed_vec_vt[0][i] > speed_list[2]:
                    wind_bin[3][bin_num] += 1
                elif speed_vec_vt[0][i] > speed_list[1]:
                    wind_bin[2][bin_num] += 1
                elif speed_vec_vt[0][i] > 0:
                    wind_bin[1][bin_num] += 1
                else:
                    wind_bin[0][bin_num] += 1
            i += 1
        i = 0
        # Our wind_bin values are counts, need to change them to % of total
        # samples and round them to self.precision decimal places. At the same
        # time, to help with bullseye scaling lets count how many samples we
        # have (of any speed>0) for each direction
        while i < 7:
            j = 0
            while j < self.petals:
                dir_bin[j] += wind_bin[i][j]
                wind_bin[i][j] = round(pcent_factor * wind_bin[i][j], self.precision)
                j += 1
            i += 1
        # Bullseye diameter is specified in skin.conf as a % of y axis range on
        # polar plot. To make space for bullseye we start the y axis at a small
        # -ve number. We supply Highcharts with the -ve value in y axis units
        # and Highcharts and some javascript takes care of the rest. # First we
        # need to work out our y axis max and the use skin.conf bullseye size
        # value to calculate the -ve value for our y axis min.

        # the size of our largest 'rose petal'
        max_dir_percent = round(pcent_factor * max(dir_bin), self.precision)
        # the y axis max value
        max_y_axis = 10.0 * (1 + int(max_dir_percent/10.0))
        # our bullseye radius in y axis units
        bullseye_radius = max_y_axis * self.bullseye_size/100.0
        # Need to get the counts for each speed band. To get this go through
        # each speed band and then through each petal adding the petal speed
        # 'count' to our total for each band and add the speed band counts to
        # the relevant speed_bin. Values are already %.
        j = 0
        while j < 7:
            i = 0
            while i < self.petals:
                speed_bin[j] += wind_bin[j][i]
                i += 1
            j += 1
        # Determine our legend labels. Need to determine actual speed band
        # ranges, add unit and if necessary add % for that band
        calm_percent_str = str(round(speed_bin[0] * pcent_factor, self.precision)) + "%"
        if self.band_percent:
            legend_labels[0] = "Calm (" + calm_percent_str + ")"
            legend_no_labels[0] = "Calm (" + calm_percent_str + ")"
        else:
            legend_labels[0] = "Calm"
            legend_no_labels[0] = "Calm"
        i = 1
        while i < 7:
            if self.band_percent:
                legend_labels[i] = str(round_int(speed_list[i - 1], 0)) + "-" + \
                                   str(round_int(speed_list[i], 0)) + speed_units_str + " (" + \
                                   str(round(speed_bin[i] * pcent_factor, self.precision)) + "%)"
                legend_no_labels[i] = str(round_int(speed_list[i - 1], 0)) + "-" + \
                                      str(round_int(speed_list[i], 0)) + " (" + \
                                      str(round(speed_bin[i] * pcent_factor, self.precision)) + "%)"
            else:
                legend_labels[i] = str(round_int(speed_list[i - 1], 0)) + "-" + \
                                   str(round_int(speed_list[i], 0)) + speed_units_str
                legend_no_labels[i] = str(round_int(speed_list[i - 1], 0)) + "-" + \
                                      str(round_int(speed_list[i], 0))
            i += 1
        # build up our JSON result string
        json_result_str = '[{"name": "' + legend_labels[6] + '", "data": ' + \
            json.dumps(wind_bin[6]) + '}'
        json_result_no_label_str = '[{"name": "' + legend_no_labels[6] + \
            '", "data": ' + json.dumps(wind_bin[6]) + '}'
        i = 5
        while i > 0:
            json_result_str += ', {"name": "' + legend_labels[i] + '", "data": ' + \
                json.dumps(wind_bin[i]) + '}'
            json_result_no_label_str += ', {"name": "' + legend_no_labels[i] + \
                '", "data": ' + json.dumps(wind_bin[i]) + '}'
            i -= 1
        # add ] to close our json array
        json_result_str += ']'

        # fill our results dictionary
        wr_dict['windrosejson'] = json_result_str
        json_result_no_label_str += ']'
        wr_dict['windrosenolabeljson'] = json_result_no_label_str
        # Get our xAxis categories in json format
        wr_dict['xAxisCategoriesjson'] = json.dumps(self.directions)
        # Get our yAxis min/max settings
        wr_dict['yAxisjson'] = '{"max": %f, "min": %f}' % (max_y_axis, -1.0 * bullseye_radius)
        # Get our stacked column colours in json format
        wr_dict['coloursjson'] = json.dumps(self.petal_colours)
        # Manually construct our plot title in json format
        wr_dict['titlejson'] = "[\"" + self.title + "\"]"
        # Manually construct our legend title in json format
        # Set to null if not required
        if self.legend_title:
            if self.source == 'windSpeed':
                legend_title_json = "[\"Wind Speed\"]"
                legend_title_no_label_json = "[\"Wind Speed<br>(" + speed_units_str + ")\"]"
            else:
                legend_title_json = "[\"Wind Gust\"]"
                legend_title_no_label_json = "[\"Wind Gust<br>(" + speed_units_str + ")\"]"
        else:
            legend_title_json = "[null]"
            legend_title_no_label_json = "[null]"
        wr_dict['legendTitlejson'] = legend_title_json
        wr_dict['legendTitleNoLabeljson'] = legend_title_no_label_json
        wr_dict['bullseyejson'] = '{"radius": %f, "color": "%s", "text": "%s"}' % (bullseye_radius,
                                                                                   self.bullseye_colour,
                                                                                   calm_percent_str)

        return wr_dict

    def get_extension_list(self, timespan, db_lookup):
        """Generate the JSON vectors and return as a list of dictionaries.

        Parameters:
          timespan: An instance of weeutil.weeutil.TimeSpan. This will
                    hold the start and stop times of the domain of
                    valid times.

          db_lookup: This is a function that, given a data binding
                     as its only parameter, will return a database manager
                     object.
         """

        t1 = time.time()

        # look for plot period, if not defined then set a default
        try:
            _period_list = option_as_list(self.windrose_dict['period'])
        except (KeyError, TypeError):
            # 24 hours
            _period_list = ['day']
        if _period_list is None:
            return None
        elif hasattr(_period_list, '__iter__') and len(_period_list) > 0:
            sle_dict = {}
            for _period_raw in _period_list:
                _period = _period_raw.strip().lower()
                if _period == 'day':
                    # normally this will be 86400 sec but it could be a daylight
                    # savings changeover day
                    # first get our stop time as a dt object so we can do some
                    # dt maths
                    _stop_dt = datetime.datetime.fromtimestamp(timespan.stop)
                    # then go back 1 day to get our start
                    _start_dt = _stop_dt - datetime.timedelta(days=1)
                    period = time.mktime(_stop_dt.timetuple()) - time.mktime(_start_dt.timetuple())
                elif _period == 'week':
                    # normally this will be 604800 sec but it could be a daylight
                    # savings changeover week
                    # first get our stop time as a dt object so we can do some
                    # dt maths
                    _stop_dt = datetime.datetime.fromtimestamp(timespan.stop)
                    # then go back 7 days to get our start
                    _start_dt = _stop_dt - datetime.timedelta(days=7)
                    period = time.mktime(_stop_dt.timetuple()) - time.mktime(_start_dt.timetuple())
                elif _period == 'month':
                    # our start time is midnight one month ago
                    # get a time object for midnight
                    _mn_time = datetime.time(0)
                    # get a datetime object for our end datetime
                    _day_date = datetime.datetime.fromtimestamp(timespan.stop)
                    # calculate our start timestamp by combining date 1 month
                    # ago and midnight time
                    _start_ts = int(time.mktime(datetime.datetime.combine(get_ago(_day_date, 0, -1),
                                                                          _mn_time).timetuple()))
                    # so our period is
                    period = timespan.stop - _start_ts
                elif _period == 'year':
                    # our start time is midnight one year ago
                    # get a time object for midnight
                    _mn_time = datetime.time(0)
                    # get a datetime object for our end datetime
                    _day_date = datetime.datetime.fromtimestamp(timespan.stop)
                    # calculate our start timestamp by combining date 1 year
                    # ago and midnight time
                    _start_ts = int(time.mktime(datetime.datetime.combine(get_ago(_day_date, -1, 0),
                                                                          _mn_time).timetuple()))
                    period = timespan.stop - _start_ts
                elif _period == 'alltime' or _period == 'all':
                    _start_ts = weeutil.weeutil.startOfDay(db_lookup().firstGoodStamp())
                    period = timespan.stop - _start_ts
                else:
                    try:
                        period = int(_period)
                    except:
                        # default to 1 day but it could be a daylight savings
                        # changeover day
                        # first get our stop time as a dt object so we can do some
                        # dt maths
                        _stop_dt = datetime.datetime.fromtimestamp(timespan.stop)
                        # then go back 1 day to get our start
                        _start_dt = _stop_dt - datetime.timedelta(days=1)
                        period = time.mktime(_stop_dt.timetuple()) - time.mktime(_start_dt.timetuple())
                # set any aggregation types/intervals if we have a period > 1 week
                if period >= 2678400:
                    # nominal month
                    if self.agg_type is None:
                        self.agg_type = 'avg'
                    if self.agg_interval is None:
                        self.agg_interval = 86400
                elif period >= 604800:
                    # nominal week:
                    if self.agg_interval is None:
                        self.agg_interval = 3600
                # can now get our windrose data
                _suffix = str(period) if _period not in ['day', 'week', 'month', 'year', 'all', 'alltime'] else str(_period)
                sle_dict['wr' + _suffix] = self.calc_windrose(timespan, db_lookup, period)
        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsWindRose SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [sle_dict]
