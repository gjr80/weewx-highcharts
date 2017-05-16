#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# Search List Extension classes to support generation of JSON data file for
# use by Highcharts to plot weewx observations.
#
# Version: 0.2.1                                    Date: 16 May 2017
#
# Revision History
#   16 May 2017         v0.2.1
#       - Fixed bug with day/week windrose getSqlVectors call that resulted in 
#         'IndexError: list index out of range' error on line 962.
#   4 May 2017          v0.2.0
#       - Removed hard coding of weeWX-WD bindings for appTemp and Insolation
#         data. Now attempts to otain bindings for each from weeWX-WD, if
#         weeWX-WD is not installed bindings are sought in weewx.conf
#         [StdReport][[Highcharts]]. If no binding can be found appTemp and
#         insolation data is omitted.
#   22 November 2016    v0.1.0
#       - initial implementation
#

import calendar
import datetime
import json
import syslog
import time
import weewx

from datetime import date
from user.highcharts import getDaySummaryVectors
from weewx.cheetahgenerator import SearchList
from weewx.units import ValueTuple, getStandardUnitType, convert, _getUnitGroup
from weeutil.weeutil import TimeSpan, genMonthSpans, startOfInterval, option_as_list, startOfDay

def logmsg(level, msg):
    syslog.syslog(level, 'highchartsSearchX: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def logdbg2(msg):
    if weewx.debug >= 2:
        logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def roundNone(value, places):
    """Round value to 'places' places but also permit a value of None."""

    if value is not None:
        try:
            value = round(value, places)
        except Exception, e:
            value = None
    return value

def roundInt(value, places):
    """Round value to 'places' but return as an integer if places=0."""

    if places == 0:
        value = int(round(value, 0))
    else:
        value = round(value, places)
    return value

def get_ago(dt, d_years=0, d_months=0):
    """ Function to return date object holding date d_years and d_months ago.

       If we try to return an invalid date due to differing month lengths
       (eg 30 Feb or 31 Sep) then just return the end of month (ie 28 Feb
       (if not a leap year else 29 Feb) or 30 Sep).
    """

    # Get year number, month number and day number applying offset as required
    _y, _m, _d = dt.year + d_years, dt.month + d_months, dt.day
    # Calculate actual month number taking into account EOY rollover
    _a, _m = divmod(_m - 1, 12)
    # Calculate and return date object
    _eom = calendar.monthrange(_y + _a, _m + 1)[1]
    return date(_y + _a, _m + 1, _d if _d <= _eom else _eom)

class highchartsMinRanges(SearchList):
    """SearchList to return y-axis minimum range values for each plot."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

    def get_extension_list(self, timespan, db_lookup):
        """Obatin y-axis minimum range values and return as a list of
           dictionaries.

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
        mr_config_dict = self.generator.skin_dict['Extras'].get('MinRange') if self.generator.skin_dict.has_key('Extras') else None
        # if we have a config dict then loop through any key/value pairs
        # discarding any pairs that are non numeric
        if mr_config_dict:
            for _key, _value in mr_config_dict.iteritems():
                _value_list = option_as_list(_value)
                if len(_value_list) > 1:
                    try:
                        _group = _getUnitGroup(_key)
                        _value_vt = ValueTuple(float(_value_list[0]), _value_list[1], _group)
                    except ValueError, KeyError:
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
        logdbg2("highchartsMinRanges SLE executed in %0.3f seconds" % (t2 - t1))

        # Return our data dict
        return [mr_dict]

class highchartsWeek(SearchList):
    """SearchList to generate JSON vectors for Highcharts week plots."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        # Do we have bindings for maxSolarRad and appTemp? weewx-WD can provide
        # these (if installed) or the user can specify in
        # [StdReport][[Highcharts]] or failing this we will ignore maxSolarRad
        # and appTemp.

        # maxSolarRad. First try to get the binding from weewx-WD if installed
        try:
            self.insolation_binding = generator.config_dict['Weewx-WD']['Supplementary'].get('data_binding')
        except KeyError:
            # Likely weewx-WD is not installed so set to None
            self.insolation_binding = None
        if self.insolation_binding is None:
            # Try [StdReport][[Highcharts]]
            try:
                self.insolation_binding = generator.config_dict['StdReport']['Highcharts'].get('insolation_binding')
                # Just in case insolation_binding is included but not set
                if self.insolation_binding == '':
                    self.insolation_binding = None
            except KeyError:
                # Should only occur if the user chnaged the name of
                # [[Highcharts]] in [StdReport]
                self.insolation_binding = None
        # appTemp. First try to get the binding from weewx-WD if installed
        try:
            self.apptemp_binding = generator.config_dict['Weewx-WD'].get('data_binding')
        except KeyError:
            # Likely weewx-WD is not installed so set to None
            self.apptemp_binding = None
        if self.apptemp_binding is None:
            # Try [StdReport][[Highcharts]]
            try:
                self.apptemp_binding = generator.config_dict['StdReport']['Highcharts'].get('apptemp_binding')
                # Just in case apptemp_binding is included but not set
                if self.apptemp_binding == '':
                    self.apptemp_binding = None
            except KeyError:
                # Should only occur if the user chnaged the name of
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

        # Get UTC offset
        stop_struct = time.localtime(timespan.stop)
        utc_offset = (calendar.timegm(stop_struct) - calendar.timegm(time.gmtime(time.mktime(stop_struct))))/60

        # Get our start time, 7 days ago but aligned with start of day
        # first get the start of today
        _ts = startOfDay(timespan.stop)
        # then go back 7 days
        _ts_dt = datetime.datetime.fromtimestamp(_ts)
        _start_dt = _ts_dt - datetime.timedelta(days=7)
        _start_ts = time.mktime(_start_dt.timetuple())

        # Get our temperature vector
        (time_start_vt, time_stop_vt, outTemp_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                              'outTemp')
        # Convert our temperature vector
        outTemp_vt = self.generator.converter.convert(outTemp_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        tempRound = int(self.generator.skin_dict['Units']['StringFormats'].get(outTemp_vt[1], "1f")[-2])
        # Do the rounding
        outTempRound_vt =  [roundNone(x,tempRound) for x in outTemp_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        outTemp_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our dewpoint vector
        (time_start_vt, time_stop_vt, dewpoint_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                               'dewpoint')
        dewpoint_vt = self.generator.converter.convert(dewpoint_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        dewpointRound = int(self.generator.skin_dict['Units']['StringFormats'].get(dewpoint_vt[1], "1f")[-2])
        # Do the rounding
        dewpointRound_vt =  [roundNone(x,dewpointRound) for x in dewpoint_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        dewpoint_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our apparent temperature vector. appTemp data is not normally
        # archived so only try to get it if we have a binding for it. Wrap in a
        # try..except to catch any errors. If we don't have a binding then set
        # the vector to None
        if self.apptemp_binding is not None:
            try:
                (time_start_vt, time_stop_vt, appTemp_vt) = db_lookup(self.apptemp_binding).getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                                          'appTemp')
                appTemp_vt = self.generator.converter.convert(appTemp_vt)
                # Can't use ValueHelper so round our results manually
                # Get the number of decimal points
                apptempRound = int(self.generator.skin_dict['Units']['StringFormats'].get(appTemp_vt[1], "1f")[-2])
                # Do the rounding
                appTempRound_vt =  [roundNone(x,apptempRound) for x in appTemp_vt[0]]
                # Get our time vector in ms (Highcharts requirement)
                # Need to do it for each getSqlVectors result as they might be different
                appTemp_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]
            except weewx.UnknownBinding:
                raise
        else:
            appTempRound_vt = None

        # Get our wind chill vector
        (time_start_vt, time_stop_vt, windchill_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                'windchill')
        windchill_vt = self.generator.converter.convert(windchill_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        windchillRound = int(self.generator.skin_dict['Units']['StringFormats'].get(windchill_vt[1], "1f")[-2])
        # Do the rounding
        windchillRound_vt =  [roundNone(x,windchillRound) for x in windchill_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        windchill_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our heat index vector
        (time_start_vt, time_stop_vt, heatindex_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                'heatindex')
        heatindex_vt = self.generator.converter.convert(heatindex_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        heatindexRound = int(self.generator.skin_dict['Units']['StringFormats'].get(heatindex_vt[1], "1f")[-2])
        # Do the rounding
        heatindexRound_vt =  [roundNone(x,heatindexRound) for x in heatindex_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        heatindex_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our humidity vector
        (time_start_vt, time_stop_vt, outHumidity_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                  'outHumidity')
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        outHumidityRound = int(self.generator.skin_dict['Units']['StringFormats'].get(outHumidity_vt[1], "1f")[-2])
        # Do the rounding
        outHumidityRound_vt =  [roundNone(x,outHumidityRound) for x in outHumidity_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        outHumidity_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our barometer vector
        (time_start_vt, time_stop_vt, barometer_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                'barometer')
        barometer_vt = self.generator.converter.convert(barometer_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        barometerRound = int(self.generator.skin_dict['Units']['StringFormats'].get(barometer_vt[1], "1f")[-2])
        # Do the rounding
        barometerRound_vt =  [roundNone(x,barometerRound) for x in barometer_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        barometer_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our wind speed vector
        (time_start_vt, time_stop_vt, windSpeed_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                'windSpeed')
        windSpeed_vt = self.generator.converter.convert(windSpeed_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        windspeedRound = int(self.generator.skin_dict['Units']['StringFormats'].get(windSpeed_vt[1], "1f")[-2])
        # Do the rounding
        windSpeedRound_vt =  [roundNone(x,windspeedRound) for x in windSpeed_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        windSpeed_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our wind gust vector
        (time_start_vt, time_stop_vt, windGust_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                               'windGust')
        windGust_vt = self.generator.converter.convert(windGust_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        windgustRound = int(self.generator.skin_dict['Units']['StringFormats'].get(windGust_vt[1], "1f")[-2])
        # Do the rounding
        windGustRound_vt =  [roundNone(x,windgustRound) for x in windGust_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        windGust_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our wind direction vector
        (time_start_vt, time_stop_vt, windDir_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                              'windDir')
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        windDirRound = int(self.generator.skin_dict['Units']['StringFormats'].get(windDir_vt[1], "1f")[-2])
        # Do the rounding
        windDirRound_vt =  [roundNone(x,windDirRound) for x in windDir_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        windDir_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our rain vector, need to sum over the hour
        (time_start_vt, time_stop_vt, rain_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                           'rain', 'sum', 3600)
        # Check if we have a partial hour at the end
        # If we do then set the last time in the time vector to the hour
        # Avoids display issues with the column chart
        # Need to make sure we have at least 2 records though
        if len(time_stop_vt[0]) > 1:
            if time_stop_vt[0][-1] < time_stop_vt[0][-2] + 3600:
                time_stop_vt[0][-1] = time_stop_vt[0][-2] + 3600
        # Convert our rain vector
        rain_vt = self.generator.converter.convert(rain_vt)
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        rainRound = int(self.generator.skin_dict['Units']['StringFormats'].get(rain_vt[1], "1f")[-2])
        # Do the rounding
        rainRound_vt =  [roundNone(x,rainRound) for x in rain_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        timeRain_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our radiation vector
        (time_start_vt, time_stop_vt, radiation_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                'radiation')
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        radiationRound = int(self.generator.skin_dict['Units']['StringFormats'].get(radiation_vt[1], "1f")[-2])
        # Do the rounding
        radiationRound_vt =  [roundNone(x,radiationRound) for x in radiation_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        radiation_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Get our insolation vector. Insolation data is not normally archived
        # so only try to get it if we have a binding for it. Wrap in a
        # try..except to catch any errors. If we don't have a binding then set
        # the vector to None
        if self.insolation_binding is not None:
            try:
                (time_start_vt, time_stop_vt, insolation_vt) = db_lookup(self.insolation_binding).getSqlVectors(TimeSpan(_start_ts, timespan.stop),
                                                                                                                'maxSolarRad')
                # Can't use ValueHelper so round our results manually
                # Get the number of decimal points
                insolationRound = int(self.generator.skin_dict['Units']['StringFormats'].get(radiation_vt[1], "1f")[-2])
                # Do the rounding
                insolationRound_vt =  [roundNone(x,insolationRound) for x in insolation_vt[0]]
                # Get our time vector in ms (Highcharts requirement)
                # Need to do it for each getSqlVectors result as they might be different
                insolation_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]
            except weewx.UnknownBinding:
                raise
        else:
            insolationRound_vt = None

        # Get our UV vector
        (time_start_vt, time_stop_vt, uv_vt) = db_lookup().getSqlVectors(TimeSpan(_start_ts, timespan.stop), 'UV')
        # Can't use ValueHelper so round our results manually
        # Get the number of decimal points
        uvRound = int(self.generator.skin_dict['Units']['StringFormats'].get(uv_vt[1], "1f")[-2])
        # Do the rounding
        uvRound_vt =  [roundNone(x,uvRound) for x in uv_vt[0]]
        # Get our time vector in ms (Highcharts requirement)
        # Need to do it for each getSqlVectors result as they might be different
        UV_time_ms =  [float(x) * 1000 for x in time_stop_vt[0]]

        # Format our vectors in json format. Need the zip() to get time/value pairs
        # Assumes all vectors have the same number of elements
        outTemp_json = json.dumps(zip(outTemp_time_ms, outTempRound_vt))
        dewpoint_json = json.dumps(zip(dewpoint_time_ms, dewpointRound_vt))
        # convert our appTemp vector to JSON, if we don't have one then set
        # it to None
        if appTempRound_vt is not None:
            appTemp_json = json.dumps(zip(appTemp_time_ms, appTempRound_vt))
        else:
            appTemp_json = None
        windchill_json = json.dumps(zip(windchill_time_ms, windchillRound_vt))
        heatindex_json = json.dumps(zip(heatindex_time_ms, heatindexRound_vt))
        outHumidity_json = json.dumps(zip(outHumidity_time_ms, outHumidityRound_vt))
        barometer_json = json.dumps(zip(barometer_time_ms, barometerRound_vt))
        windSpeed_json = json.dumps(zip(windSpeed_time_ms, windSpeedRound_vt))
        windGust_json = json.dumps(zip(windGust_time_ms, windGustRound_vt))
        windDir_json = json.dumps(zip(windDir_time_ms, windDirRound_vt))
        radiation_json = json.dumps(zip(radiation_time_ms, radiationRound_vt))
        # convert our insolation vector to JSON, if we don't have one then set
        # it to None
        if insolationRound_vt is not None:
            insolation_json = json.dumps(zip(insolation_time_ms, insolationRound_vt))
        else:
            insolation_json = None
        uv_json = json.dumps(zip(UV_time_ms, uvRound_vt))
        rain_json = json.dumps(zip(timeRain_ms, rainRound_vt))

        # Put into a dictionary to return
        search_list_extension = {'outTempWeekjson' : outTemp_json,
                                 'dewpointWeekjson' : dewpoint_json,
                                 'appTempWeekjson' : appTemp_json,
                                 'windchillWeekjson' : windchill_json,
                                 'heatindexWeekjson' : heatindex_json,
                                 'outHumidityWeekjson' : outHumidity_json,
                                 'barometerWeekjson' : barometer_json,
                                 'windSpeedWeekjson' : windSpeed_json,
                                 'windGustWeekjson' : windGust_json,
                                 'windDirWeekjson' : windDir_json,
                                 'rainWeekjson' : rain_json,
                                 'radiationWeekjson' : radiation_json,
                                 'insolationWeekjson' : insolation_json,
                                 'uvWeekjson' : uv_json,
                                 'utcOffset': utc_offset,
                                 'weekPlotStart' : _start_ts * 1000,
                                 'weekPlotEnd' : timespan.stop * 1000}

        t2 = time.time()
        logdbg2("highchartsWeek SLE executed in %0.3f seconds" % (t2 - t1))

        # Return our json data
        return [search_list_extension]

class highchartsYear(SearchList):
    """SearchList to generate JSON vectors for Highcharts week plots.""""""SearchList to generate JSON vectors for Highcharts year plots."""

    def __init__(self, generator):
        SearchList.__init__(self, generator)

        # Do we have a binding for appTemp? weewx-WD can provide (if installed)
        # or the user can specify in [StdReport][[Highcharts]] or failing this
        # we will ignore appTemp.

        # First try to get the binding from weewx-WD if installed
        try:
            self.apptemp_binding = generator.config_dict['Weewx-WD'].get('data_binding')
        except KeyError:
            # Likely weewx-WD is not installed so set to None
            self.apptemp_binding = None
        if self.apptemp_binding is None:
            # Try [StdReport][[Highcharts]]
            try:
                self.apptemp_binding = generator.config_dict['StdReport']['Highcharts'].get('apptemp_binding')
                # Just in case apptemp_binding is included but not set
                if self.apptemp_binding == '':
                    self.apptemp_binding = None
            except KeyError:
                # Should only occur if the user chnaged the name of
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

        # Get UTC offset
        stop_struct = time.localtime(timespan.stop)
        utc_offset = (calendar.timegm(stop_struct) - calendar.timegm(time.gmtime(time.mktime(stop_struct))))/60

        # Our start time is one year ago from midnight at the start of today
        # first get the start of today
        _ts = startOfDay(timespan.stop)
        # then go back 1 year
        _ts_dt = datetime.datetime.fromtimestamp(_ts)
        try:
            _start_dt = _ts_dt.replace(year=_ts_dt.year-1)
        except ValueError:
            _start_dt = _ts_dt.replace(year=_ts_dt.year-1, day=_ts_dt.day-1)
        _start_ts = time.mktime(_start_dt.timetuple())
        _timespan = TimeSpan(_start_ts, timespan.stop)

         # Get our outTemp vectors
        (outTemp_time_vt, outTemp_dict) = getDaySummaryVectors(db_lookup(), 'outTemp', _timespan, ['min', 'max', 'avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        outTempMin_vt = self.generator.converter.convert(outTemp_dict['min'])
        outTempMax_vt = self.generator.converter.convert(outTemp_dict['max'])
        outTempAvg_vt = self.generator.converter.convert(outTemp_dict['avg'])

        # Get our appTemp vectors. appTemp data is not normally archived so
        # only try to get it if we have a binding for it. Wrap in a try..except
        # to catch any errors. If we don't have a binding then set the vectors
        # to None
        if self.apptemp_binding is not None:
            try:
                (appTemp_time_vt, appTemp_dict) = getDaySummaryVectors(db_lookup('wd_binding'),
                                                                       'appTemp',
                                                                       _timespan,
                                                                       ['min', 'max', 'avg'])
                # Get our vector ValueTuple out of the dictionary and convert it
                appTempMin_vt = self.generator.converter.convert(appTemp_dict['min'])
                appTempMax_vt = self.generator.converter.convert(appTemp_dict['max'])
                appTempAvg_vt = self.generator.converter.convert(appTemp_dict['avg'])
            except weewx.UnknownBinding:
                raise
        else:
            appTempMin_vt = None
            appTempMax_vt = None
            appTempAvg_vt = None

        # Get our windchill vector
        (windchill_time_vt, windchill_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'windchill',
                                                                   _timespan,
                                                                   ['avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        windchillAvg_vt = self.generator.converter.convert(windchill_dict['avg'])

        # Get our heatindex vector
        (heatindex_time_vt, heatindex_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'heatindex',
                                                                   _timespan,
                                                                   ['avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        heatindexAvg_vt = self.generator.converter.convert(heatindex_dict['avg'])
        # Get our humidity vectors
        (outHumidity_time_vt, outHumidity_dict) = getDaySummaryVectors(db_lookup(),
                                                                       'outHumidity',
                                                                       _timespan,
                                                                       ['min', 'max', 'avg'])

        # Get our barometer vectors
        (barometer_time_vt, barometer_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'barometer',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        barometerMin_vt = self.generator.converter.convert(barometer_dict['min'])
        barometerMax_vt = self.generator.converter.convert(barometer_dict['max'])
        barometerAvg_vt = self.generator.converter.convert(barometer_dict['avg'])

        # Get our wind vectors
        (wind_time_vt, wind_dict) = getDaySummaryVectors(db_lookup(),
                                                         'wind',
                                                         _timespan,
                                                         ['max', 'avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        windMax_vt = self.generator.converter.convert(wind_dict['max'])
        windAvg_vt = self.generator.converter.convert(wind_dict['avg'])

        # Get our windSpeed vectors
        (windSpeed_time_vt, windSpeed_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'windSpeed',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])
        # Get our vector ValueTuple out of the dictionary and convert it
        windSpeedMax_vt = self.generator.converter.convert(windSpeed_dict['max'])
        windSpeedAvg_vt = self.generator.converter.convert(windSpeed_dict['avg'])

        # Get our windDir vectors
        (windDir_time_vt, windDir_dict) = getDaySummaryVectors(db_lookup(),
                                                               'wind',
                                                               _timespan,
                                                               ['vecdir'])

        # Get our rain vectors
        (rain_time_vt, rain_dict) = getDaySummaryVectors(db_lookup(),
                                                         'rain',
                                                         _timespan,
                                                         ['sum'])
        # Get our vector ValueTuple out of the dictionary and convert it
        rainSum_vt = self.generator.converter.convert(rain_dict['sum'])

        # Get our radiation vectors
        (radiation_time_vt, radiation_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'radiation',
                                                                   _timespan,
                                                                   ['min', 'max', 'avg'])

        # Get our UV vectors
        (uv_time_vt, uv_dict) = getDaySummaryVectors(db_lookup(),
                                                     'UV',
                                                     _timespan,
                                                     ['min', 'max', 'avg'])

        # Get no of decimal places to use when formatting results
        tempPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(outTempMin_vt[1], "1f")[-2])
        outHumidityPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(outHumidity_dict['min'][1], "1f")[-2])
        barometerPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(barometerMin_vt[1], "1f")[-2])
        windPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(windMax_vt[1], "1f")[-2])
        windSpeedPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(windSpeedMax_vt[1], "1f")[-2])
        windDirPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(windDir_dict['vecdir'][1], "1f")[-2])
        rainPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(rainSum_vt[1], "1f")[-2])
        radiationPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(radiation_dict['max'][1], "1f")[-2])
        uvPlaces = int(self.generator.skin_dict['Units']['StringFormats'].get(uv_dict['max'][1], "1f")[-2])

        # Get our time vector in ms
        time_ms =  [float(x) * 1000 for x in outTemp_time_vt[0]]

        # Round our values from our ValueTuples
        outTempMinRound = [roundNone(x,tempPlaces) for x in outTempMin_vt[0]]
        outTempMaxRound = [roundNone(x,tempPlaces) for x in outTempMax_vt[0]]
        outTempAvgRound = [roundNone(x,tempPlaces) for x in outTempAvg_vt[0]]
        # round our appTemp values, if we don't have any then set it to None
        try:
            appTempMinRound = [roundNone(x,tempPlaces) for x in appTempMin_vt[0]]
            appTempMaxRound = [roundNone(x,tempPlaces) for x in appTempMax_vt[0]]
            appTempAvgRound = [roundNone(x,tempPlaces) for x in appTempAvg_vt[0]]
        except TypeError:
            appTempMinRound = None
            appTempMaxRound = None
            appTempAvgRound = None
        windchillAvgRound = [roundNone(x,tempPlaces) for x in windchillAvg_vt[0]]
        heatindexAvgRound = [roundNone(x,tempPlaces) for x in heatindexAvg_vt[0]]
        outHumidityMinRound = [roundNone(x,outHumidityPlaces) for x in outHumidity_dict['min'][0]]
        outHumidityMaxRound = [roundNone(x,outHumidityPlaces) for x in outHumidity_dict['max'][0]]
        outHumidityAvgRound = [roundNone(x,outHumidityPlaces) for x in outHumidity_dict['avg'][0]]
        barometerMinRound = [roundNone(x,tempPlaces) for x in barometerMin_vt[0]]
        barometerMaxRound = [roundNone(x,tempPlaces) for x in barometerMax_vt[0]]
        barometerAvgRound = [roundNone(x,tempPlaces) for x in barometerAvg_vt[0]]
        windMaxRound = [roundNone(x,windPlaces) for x in windMax_vt[0]]
        windAvgRound = [roundNone(x,windPlaces) for x in windAvg_vt[0]]
        windSpeedMaxRound = [roundNone(x,windSpeedPlaces) for x in windSpeedMax_vt[0]]
        windSpeedAvgRound = [roundNone(x,windSpeedPlaces) for x in windSpeedAvg_vt[0]]
        windDirRound = [roundNone(x,windDirPlaces) for x in windDir_dict['vecdir'][0]]
        rainSumRound = [roundNone(x,rainPlaces) for x in rainSum_vt[0]]
        radiationMinRound = [roundNone(x,radiationPlaces) for x in radiation_dict['min'][0]]
        radiationMaxRound = [roundNone(x,radiationPlaces) for x in radiation_dict['max'][0]]
        radiationAvgRound = [roundNone(x,radiationPlaces) for x in radiation_dict['avg'][0]]
        uvMinRound = [roundNone(x,uvPlaces) for x in uv_dict['min'][0]]
        uvMaxRound = [roundNone(x,uvPlaces) for x in uv_dict['max'][0]]
        uvAvgRound = [roundNone(x,uvPlaces) for x in uv_dict['avg'][0]]

        # Produce our JSON strings
        outTempMinMax_json = json.dumps(zip(time_ms, outTempMinRound, outTempMaxRound))
        outTempMin_json = json.dumps(zip(time_ms, outTempMinRound))
        outTempMax_json = json.dumps(zip(time_ms, outTempMaxRound))
        outTempAvg_json = json.dumps(zip(time_ms, outTempAvgRound))
        # appTemp. If we don't have any source data then set our JSON string to
        # None
        if appTempMinRound is not None and appTempMaxRound is not None:
            appTempMinMax_json = json.dumps(zip(time_ms, appTempMinRound, appTempMaxRound))
        else:
            appTempMinMax_json = None
        if appTempMinRound is not None:
            appTempMin_json = json.dumps(zip(time_ms, appTempMinRound))
        else:
            appTempMin_json = None
        if appTempMaxRound is not None:
            appTempMax_json = json.dumps(zip(time_ms, appTempMaxRound))
        else:
            appTempMax_json = None
        if appTempAvgRound is not None:
            appTempAvg_json = json.dumps(zip(time_ms, appTempAvgRound))
        else:
            appTempAvg_json = None
        windchillAvg_json = json.dumps(zip(time_ms, windchillAvgRound))
        heatindexAvg_json = json.dumps(zip(time_ms, heatindexAvgRound))
        outHumidityMinMax_json = json.dumps(zip(time_ms, outHumidityMinRound, outHumidityMaxRound))
        outHumidityMin_json = json.dumps(zip(time_ms, outHumidityMinRound))
        outHumidityMax_json = json.dumps(zip(time_ms, outHumidityMaxRound))
        outHumidityAvg_json = json.dumps(zip(time_ms, outHumidityAvgRound))
        barometerMinMax_json = json.dumps(zip(time_ms, barometerMinRound, barometerMaxRound))
        barometerMin_json = json.dumps(zip(time_ms, barometerMinRound))
        barometerMax_json = json.dumps(zip(time_ms, barometerMaxRound))
        barometerAvg_json = json.dumps(zip(time_ms, barometerAvgRound))
        windMax_json = json.dumps(zip(time_ms, windMaxRound))
        windAvg_json = json.dumps(zip(time_ms, windAvgRound))
        windSpeedMax_json = json.dumps(zip(time_ms, windSpeedMaxRound))
        windSpeedAvg_json = json.dumps(zip(time_ms, windSpeedAvgRound))
        windDir_json = json.dumps(zip(time_ms, windDirRound))
        rainSum_json = json.dumps(zip(time_ms, rainSumRound))
        radiationMax_json = json.dumps(zip(time_ms, radiationMaxRound))
        radiationAvg_json = json.dumps(zip(time_ms, radiationAvgRound))
        uvMax_json = json.dumps(zip(time_ms, uvMaxRound))
        uvAvg_json = json.dumps(zip(time_ms, uvAvgRound))

        # Put into a dictionary to return
        search_list_extension = {'outTempMinMax_json' : outTempMinMax_json,
                                 'outTempAvg_json' : outTempAvg_json,
                                 'appTempMinMax_json' : appTempMinMax_json,
                                 'appTempMin_json' : appTempMin_json,
                                 'appTempMax_json' : appTempMax_json,
                                 'appTempAvg_json' : appTempAvg_json,
                                 'windchillAvg_json' : windchillAvg_json,
                                 'heatindexAvg_json' : heatindexAvg_json,
                                 'outHumidityMinMax_json' : outHumidityMinMax_json,
                                 'outHumidityMin_json' : outHumidityMin_json,
                                 'outHumidityMax_json' : outHumidityMax_json,
                                 'outHumidityAvg_json' : outHumidityAvg_json,
                                 'barometerMinMax_json' : barometerMinMax_json,
                                 'barometerMin_json' : barometerMin_json,
                                 'barometerMax_json' : barometerMax_json,
                                 'barometerAvg_json' : barometerAvg_json,
                                 'windMax_json' : windMax_json,
                                 'windAvg_json' : windAvg_json,
                                 'windSpeedMax_json' : windSpeedMax_json,
                                 'windSpeedAvg_json' : windSpeedAvg_json,
                                 'windDir_json' : windDir_json,
                                 'rainSum_json' : rainSum_json,
                                 'radiationMax_json' : radiationMax_json,
                                 'radiationAvg_json' : radiationAvg_json,
                                 'uvMax_json' : uvMax_json,
                                 'uvAvg_json' : uvAvg_json,
                                 'utcOffset': utc_offset,
                                 'yearPlotStart' : _timespan.start * 1000,
                                 'yearPlotEnd' : _timespan.stop * 1000}

        t2 = time.time()
        logdbg2("highchartsYear SLE executed in %0.3f seconds" % (t2 - t1))

        # Return our json data
        return [search_list_extension]

class highchartsWindRose(SearchList):
    """SearchList to generate JSON vectors for Highcharts windrose plots."""

    def __init__(self, generator):
        # Call our superclass' __init__
        SearchList.__init__(self, generator)

        # Get a dictionary of ous skin settings
        self.windrose_dict = self.generator.skin_dict['Extras']['WindRose']
        # Look for plot title, if not defined then set a default
        try:
            self.title = self.windrose_dict['title'].strip()
        except KeyError:
            self.title = 'Wind Rose'
        # Look for plot source, if not defined then set a default
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
        # Look for aggregate type
        try:
            self.agg_type = self.windrose_dict['aggregate_type'].strip().lower()
            if self.agg_type not in [None, 'avg', 'max', 'min']:
                self.agg_type = None
        except KeyError:
            self.agg_type = None
        # Look for aggregate interval
        try:
            self.agg_interval = int(self.windrose_dict['aggregate_interval'])
            if self.agg_interval == 0:
                self.agg_interval = None
        except (KeyError, TypeError, ValueError):
            self.agg_interval = None
        # Look for speed band boundaries, if not defined then set some defaults
        try:
            self.speedfactor = self.windrose_dict['speedfactor']
        except KeyError:
            self.speedfactor = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
        if len(self.speedfactor) != 7 or max(self.speedfactor) > 1.0 or min(self.speedfactor) <0.0:
            self.speedfactor = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
        # Look for petal colours, if not defined then set some defaults
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
        # Look for number of petals, if not defined then set a default
        try:
            self.petals = int(self.windrose_dict['petals'])
        except KeyError:
            self.petals = 8
        if self.petals == None or self.petals == 0:
            self.petals = 8
        # Set our list of direction based on number of petals
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
        # Look for legend title, if not defined then set True
        try:
            self.legend_title = self.windrose_dict['legend_title'].strip().lower() == 'true'
        except KeyError:
            self.legend_title = True
        # Look for band percent, if not defined then set True
        try:
            self.band_percent = self.windrose_dict['band_percent'].strip().lower() == 'true'
        except KeyError:
            self.band_percent = True
        # Look for % precision, if not defined then set a default
        try:
            self.precision = int(self.windrose_dict['precision'])
        except KeyError:
            self.precision = 1
        if self.precision == None:
            self.precision = 1
        # Look for bullseye diameter, if not defined then set a default
        try:
            self.bullseye_size = int(self.windrose_dict['bullseye_size'])
        except KeyError:
            self.bullseye_size = 3
        if self.bullseye_size == None:
            self.bullseye_size = 3
        # Look for bullseye colour, if not defined then set some defaults
        try:
            self.bullseye_colour = self.windrose_dict['bullseye_color']
        except KeyError:
            self.bullseye_colour = 'white'
        if self.bullseye_colour == None:
            self.bullseye_colour = 'white'
        if self.bullseye_colour[0:2] == '0x':
            self.bullseye_colour = '#' + self.bullseye_colour[2:]
        # Look for 'calm' upper limit ie the speed below which we consider aggregate
        # wind speeds to be 'calm' (or 0)
        try:
            self.calm_limit = float(self.windrose_dict['calm_limit'])
        except:
            self.calm_limit = 0.1

    def calcWindRose(self, timespan, db_lookup, period):
        """Function to calculate windrose JSON data for a given timespan."""

        # Initialise a dictionary for our results
        wr_dict = {}
        if period <= 604800: # Week or less, get our vectors from archive via getSqlVectors
            # Get our wind speed vector
            (time_vec_speed_start_vt, time_vec_speed_vt, speed_vec_vt) = db_lookup().getSqlVectors(TimeSpan(timespan.stop-period + 1, timespan.stop),
                                                                                                   self.source,
                                                                                                   None,
                                                                                                   None)
            # Convert it
            speed_vec_vt = self.generator.converter.convert(speed_vec_vt)
            # Get our wind direction vector
            (time_vec_dir_start_vt, time_vec_dir_stop_vt, direction_vec_vt) = db_lookup().getSqlVectors(TimeSpan(timespan.stop-period + 1, timespan.stop),
                                                                                                        self.dir,
                                                                                                        None,
                                                                                                        None)
        else: # Get our vectors from daily summaries using custom getStatsVectors
            # Get our data tuples for speed
            (time_vec_speed_vt, speed_dict) = getDaySummaryVectors(db_lookup(),
                                                                   'wind',
                                                                   TimeSpan(timespan.stop - period, timespan.stop),
                                                                   ['avg'])
            # Get our vector ValueTuple out of the dictionary and convert it
            speed_vec_vt = self.generator.converter.convert(speed_dict['avg'])
            # Get our data tuples for direction
            (time_vec_dir_vt, dir_dict) = getDaySummaryVectors(db_lookup(),
                                                               'wind',
                                                               TimeSpan(timespan.stop - period, timespan.stop),
                                                               ['vecdir'])
            # Get our vector ValueTuple out of the dictionary, no need to convert
            direction_vec_vt = dir_dict['vecdir']
        # Get a string with our speed units
        speedUnits_str = self.generator.skin_dict['Units']['Labels'].get(speed_vec_vt[1]).strip()
        # To get a better display we will set our upper speed to a multiple of 10
        # Find maximum speed from our data
        maxSpeed = max(speed_vec_vt[0])
        # Set upper speed range for our plot
        maxSpeedRange = (int(maxSpeed/10.0) + 1) * 10
        # Setup a list to hold the cutoff speeds for our stacked columns on our
        # wind rose.
        speedList = [0 for x in range(7)]
        # Setup a list to hold the legend item text for each of our speed bands
        # (or legend labels)
        legendLabels = ["" for x in range(7)]
        legendNoLabels = ["" for x in range(7)]
        i = 1
        while i<7:
            speedList[i] = self.speedfactor[i]*maxSpeedRange
            i += 1
        # Setup 2D list for wind direction
        # windBin[0][0..self.petals] holds the calm or 0 speed counts for each
        # of self.petals (usually 16) compass directions ([0][0] for N, [0][1]
        # for ENE (or NE oe E depending self.petals) etc).
        # windBin[1][0..self.petals] holds the 1st speed band speed counts for
        # each of self.petals (usually 16) compass directions ([1][0] for
        # N, [1][1] for ENE (or NE oe E depending self.petals) etc).
        windBin = [[0 for x in range(self.petals)] for x in range(7)]
        # Setup a list to hold sample count (speed>0) for each direction. Used
        # to aid in bullseye scaling
        dirBin = [0 for x in range(self.petals)]
        # Setup list to hold obs counts for each speed range (irrespective of
        # direction)
        # [0] = calm
        # [1] = >0 and < 1st speed
        # [2] = >1st speed and <2nd speed
        # .....
        # [6] = >4th speed and <5th speed
        # [7] = >5th speed and <6th speed
        speedBin = [0 for x in range(7)]
        # How many obs do we have?
        samples = len(time_vec_speed_vt[0])
        # Calc factor to be applied to convert counts to %
        pcentFactor = 100.0/samples
        # Loop through each sample and increment direction counts
        # and speed ranges for each direction as necessary. 'None'
        # direction is counted as 'calm' (or 0 speed) and
        # (by definition) no direction and are plotted in the
        # 'bullseye' on the plot
        i = 0
        while i < samples:
            if (speed_vec_vt[0][i] is None) or (direction_vec_vt[0][i] is None):
                speedBin[0] +=1
            else:
                bin = int((direction_vec_vt[0][i]+11.25)/22.5)%self.petals
                if speed_vec_vt[0][i] <= self.calm_limit:
                    speedBin[0] +=1
                elif speed_vec_vt[0][i] > speedList[5]:
                    windBin[6][bin] += 1
                elif speed_vec_vt[0][i] > speedList[4]:
                    windBin[5][bin] += 1
                elif speed_vec_vt[0][i] > speedList[3]:
                    windBin[4][bin] += 1
                elif speed_vec_vt[0][i] > speedList[2]:
                    windBin[3][bin] += 1
                elif speed_vec_vt[0][i] > speedList[1]:
                    windBin[2][bin] += 1
                elif speed_vec_vt[0][i] > 0:
                    windBin[1][bin] += 1
                else:
                    windBin[0][bin] += 1
            i += 1
        i=0
        # Our windBin values are counts, need to change them to % of total samples
        # and round them to self.precision decimal places.
        # At the same time, to help with bullseye scaling lets count how many
        # samples we have (of any speed>0) for each direction
        while i<7:
            j=0
            while j<self.petals:
                dirBin[j] += windBin[i][j]
                windBin[i][j] = round(pcentFactor * windBin[i][j],self.precision)
                j += 1
            i += 1
        # Bullseye diameter is specified in skin.conf as a % of y axis range on
        # polar plot. To make space for bullseye we start the y axis at a small
        # -ve number. We supply Highcharts with the -ve value in y axis units
        # and Highcharts and some javascript takes care of the rest. # First we
        # need to work out our y axis max and the use skin.conf bullseye size
        # value to calculate the -ve value for our y axis min.
        maxDirPercent = round(pcentFactor * max(dirBin),self.precision) # the
            # size of our largest 'rose petal'
        maxYaxis = 10.0 * (1 + int(maxDirPercent/10.0)) # the y axis max value
        bullseyeRadius = maxYaxis * self.bullseye_size/100.0 # our bullseye
            # radius in y axis units
        # Need to get the counts for each speed band. To get this go through
        # each speed band and then through each petal adding the petal speed
        # 'count' to our total for each band and add the speed band counts to
        # the relevant speedBin. Values are already %.
        j = 0
        while j<7:
            i = 0
            while i<self.petals:
                speedBin[j] += windBin[j][i]
                i += 1
            j += 1
        # Determine our legend labels. Need to determine actual speed band
        # ranges, add unit and if necessary add % for that band
        calmPercent_str = str(round(speedBin[0] * pcentFactor,self.precision)) + "%"
        if self.band_percent:
            legendLabels[0]="Calm (" + calmPercent_str + ")"
            legendNoLabels[0]="Calm (" + calmPercent_str + ")"
        else:
            legendLabels[0]="Calm"
            legendNoLabels[0]="Calm"
        i=1
        while i<7:
            if self.band_percent:
                legendLabels[i] = str(roundInt(speedList[i-1],0)) + "-" + \
                    str(roundInt(speedList[i],0)) + speedUnits_str + " (" + \
                    str(round(speedBin[i] * pcentFactor,self.precision)) + "%)"
                legendNoLabels[i] = str(roundInt(speedList[i-1],0)) + "-" + \
                    str(roundInt(speedList[i],0)) + " (" + \
                    str(round(speedBin[i] * pcentFactor,self.precision)) + "%)"
            else:
                legendLabels[i] = str(roundInt(speedList[i-1],0)) + "-" + \
                    str(roundInt(speedList[i],0)) + speedUnits_str
                legendNoLabels[i] = str(roundInt(speedList[i-1],0)) + "-" + \
                    str(roundInt(speedList[i],0))
            i += 1
        # Build up our JSON result string
        jsonResult_str = '[{"name": "' + legendLabels[6] + '", "data": ' + \
            json.dumps(windBin[6]) + '}'
        jsonResultNoLabel_str = '[{"name": "' + legendNoLabels[6] + \
            '", "data": ' + json.dumps(windBin[6]) + '}'
        i=5
        while i>0:
            jsonResult_str += ', {"name": "' + legendLabels[i] + '", "data": ' + \
                json.dumps(windBin[i]) + '}'
            jsonResultNoLabel_str += ', {"name": "' + legendNoLabels[i] + \
                '", "data": ' + json.dumps(windBin[i]) + '}'
            i -= 1
        # Add ] to close our json array
        jsonResult_str += ']'

        # Fill our results dictionary
        wr_dict['windrosejson'] = jsonResult_str
        jsonResultNoLabel_str += ']'
        wr_dict['windrosenolabeljson'] = jsonResultNoLabel_str
        # Get our xAxis categories in json format
        wr_dict['xAxisCategoriesjson'] = json.dumps(self.directions)
        # Get our yAxis min/max settings
        wr_dict['yAxisjson'] = '{"max": %f, "min": %f}' % (maxYaxis, -1.0 * bullseyeRadius)
        # Get our stacked column colours in json format
        wr_dict['coloursjson'] = json.dumps(self.petal_colours)
        # Manually construct our plot title in json format
        wr_dict['titlejson'] = "[\"" + self.title + "\"]"
        # Manually construct our legend title in json format
        # Set to null if not required
        if self.legend_title:
            if self.source == 'windSpeed':
                legend_title_json = "[\"Wind Speed\"]"
                legend_title_no_label_json = "[\"Wind Speed<br>(" + speedUnits_str + ")\"]"
            else:
                legend_title_json = "[\"Wind Gust\"]"
                legend_title_no_label_json = "[\"Wind Gust<br>(" + speedUnits_str + ")\"]"
        else:
            legend_title_json = "[null]"
            legend_title_no_label_json = "[null]"
        wr_dict['legendTitlejson'] = legend_title_json
        wr_dict['legendTitleNoLabeljson'] = legend_title_no_label_json
        wr_dict['bullseyejson'] = '{"radius": %f, "color": "%s", "text": "%s"}' % (bullseyeRadius,
                                                                                   self.bullseye_colour,
                                                                                   calmPercent_str)

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

        # Look for plot period, if not defined then set a default
        try:
            _period_list = option_as_list(self.windrose_dict['period'])
        except (KeyError, TypeError):
            _period_list = ['day']  # 24 hours
        if _period_list is None:
            return None
        elif hasattr(_period_list, '__iter__') and len(_period_list) > 0:
            sle_dict ={}
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
                    # Our start time is midnight one month ago
                    # Get a time object for midnight
                    _mn_time = datetime.time(0)
                    # Get a datetime object for our end datetime
                    _day_date = datetime.datetime.fromtimestamp(timespan.stop)
                    # Calculate our start timestamp by combining date 1 month
                    # ago and midnight time
                    _start_ts  = int(time.mktime(datetime.datetime.combine(get_ago(_day_date,0,-1),_mn_time).timetuple()))
                    # So our period is
                    period = timespan.stop - _start_ts
                elif _period == 'year':
                    # Our start time is midnight one year ago
                    # Get a time object for midnight
                    _mn_time = datetime.time(0)
                    # Get a datetime object for our end datetime
                    _day_date = datetime.datetime.fromtimestamp(timespan.stop)
                    # Calculate our start timestamp by combining date 1 year
                    # ago and midnight time
                    _start_ts  = int(time.mktime(datetime.datetime.combine(get_ago(_day_date, -1, 0),_mn_time).timetuple()))
                    period = timespan.stop - _start_ts
                elif _period == 'alltime' or _period == 'all':
                    _start_ts = startOfDay(db_lookup().firstGoodStamp())
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
                # Set any aggregation types/intervals if we have a period > 1 week
                if period >= 2678400: # nominal month
                    if self.agg_type == None:
                        self.agg_type = 'avg'
                    if self.agg_interval == None:
                        self.agg_interval = 86400
                elif period >= 604800: # nominal week:
                    if self.agg_interval == None:
                        self.agg_interval = 3600
                # Can now get our windrose data
                _suffix = str(period) if _period not in ['day', 'week', 'month', 'year', 'all', 'alltime'] else str(_period)
                sle_dict['wr' + _suffix] = self.calcWindRose(timespan, db_lookup, period)

        t2 = time.time()
        logdbg2("highchartsWindRose SLE executed in %0.3f seconds" % (t2 - t1))

        # Return our json data
        return [sle_dict]