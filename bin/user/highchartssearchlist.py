"""
highchartssearchlist.py

Search List Extensions to support the weewx-highcharts extension.

Copyright (C) 2016-21 Gary Roderick               gjroderick<at>gmail.com

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see http://www.gnu.org/licenses/.

Version: 0.4.0                                      Date: xx xxxxx 2021

Revision History
    xx xxxxx 2021       v0.4.0
        - now uses .series tags introduced in WeeWX v4.5.0
        - removed SLE entries made redundant due to use of .series tags
        - now requires WeeWX v4.5.0 or later
    17 March 2021       v0.3.2
        - bindings for appTemp and maxSolarRad are now specified under
          skin.conf [Extras] using apptemp_binding and insolation_binding
          options
        - replaced getSqlVectors() calls with xtypes.get_series() calls
    16 October 2020     v0.3.1
        - fixed bug encountered when there are one or more None values returned
          in speed_vec_vt.value
    13 September 2020   v0.3.0
        - renamed file
        - now WeeWX 4.0.0 python 2/3 compatible
        - refactored get_extension_list() code in each SLE class
    4 September 2018    v0.2.2
        - minor comment editing
    16 May 2017         v0.2.1
        - fixed bug with day/week windrose getSqlVectors call that resulted in
          'IndexError: list index out of range' error on line 962
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
import math
import time
from datetime import date

# WeeWX imports
import weewx
import weewx.cheetahgenerator
import weewx.units
import weeutil.weeutil
import weewx.xtypes
from weewx.tags import TimespanBinder
from weewx.units import ValueTuple, getStandardUnitType, convert
from weeutil.weeutil import TimeSpan, option_as_list

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
        syslog.syslog(level, 'highcharts: %s' % msg)

    def logdbg(msg):
        logmsg(syslog.LOG_DEBUG, msg)

HFW_VERSION = "0.4.0"


# ============================================================================
#                    class HighchartsDaySummarySearchList
# ============================================================================

class HighchartsDaySummarySearchList(weewx.cheetahgenerator.SearchList):
    """Base class for a Highcharts search list that uses Daily Summaries."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsDaySummarySearchList, self).__init__(generator)

    @staticmethod
    def get_day_summary_vectors(db_manager, obs_type, timespan, agg_list=['max']):
        """Return a vector of aggregate data from the WeeWX daily summaries.

            Parameters:
              db_manager: A database manager object for the WeeWX archive.

              obs_type:   A statistical type, such as 'outTemp' 'barometer' etc.

              timespan:   TimeSpan object representing the time span over which the
                          vector is required.

              agg_list:   A list of the aggregates required eg ['max', 'min'].
                          Member elements can be any of 'min', 'max', 'mintime',
                          'maxtime', 'gustdir', 'sum', 'count', 'avg', 'rms',
                          'vecavg' or 'vecdir'.
           """

        # the list of supported aggregates
        vector_aggs = ['gustdir', 'rms', 'vecavg', 'vecdir']
        # sql field list for scalar types
        scalar_fields = 'dateTime,min,mintime,max,maxtime,sum,count,wsum,sumtime'
        # sql field list for vector types
        vector_fields = ','.join([scalar_fields,
                                  'max_dir,xsum,ysum,dirsumtime,squaresum,wsquaresum'])
        # setup up a list of lists for our vectors
        _vec = [list() for x in range(len(agg_list))]
        # initialise each list in the list of lists
        for agg in agg_list:
            _vec[agg_list.index(agg)] = list()
        # setup up our time vector list
        _time_vec = list()
        # initialise a dictionary for our results
        _return = {}
        # get the unit system in use
        _row = db_manager.getSql("SELECT usUnits FROM %s LIMIT 1;" % db_manager.table_name)
        std_unit_system = _row[0] if _row is not None else None
        # the list of fields we need depend on whether we have a scalar type or a
        # vector type, which one is it
        if any(x in vector_aggs for x in agg_list):
            # it's a vector
            sql_fields = vector_fields
        else:
            # it's a scalar
            sql_fields = scalar_fields
        # get our interpolation dictionary for the query
        inter_dict = {'start': weeutil.weeutil.startOfDay(timespan.start),
                      'stop': timespan.stop,
                      'table_name': 'archive_day_%s' % obs_type,
                      'sql_fields': sql_fields}
        # get a cursor object for our query
        _cursor = db_manager.connection.cursor()
        try:
            # put together our SQL query string
            sql_str = "SELECT %(sql_fields)s FROM %(table_name)s "\
                      "WHERE dateTime >= %(start)s AND dateTime < %(stop)s" % inter_dict
            # loop through each record our query returns
            for _rec in _cursor.execute(sql_str):
                # loop through each aggregate we have been asked for
                for agg in agg_list:
                    # Sql query result fields will vary depending on whether the
                    # underlying obs is a scalar or vector type. At the moment
                    # 'wind' is the only vector obs. Fields are as follows:
                    # scalar: [0]=dateTime    [1]=min        [2]=mintime     [3]=max
                    #         [4]=maxtime     [5]=sum        [6]=count       [7]=wsum
                    #         [8]=sumtime
                    # vector: [0]=dateTime    [1]=min        [2]=mintime     [3]=max
                    #         [4]=maxtime     [5]=sum        [6]=count       [7]=wsum
                    #         [8]=sumtime     [9]=max_dir    [10]=xsum       [11]=ysum
                    #         [12]=dirsumtime [13]=squaresum [14]=wsquaresum

                    # calculate the aggregate
                    if agg == 'min':
                        _result = _rec[1]
                    elif agg == 'max':
                        _result = _rec[3]
                    elif agg == 'sum':
                        _result = _rec[5]
                    elif agg == 'gustdir':
                        _result = _rec[9]
                    elif agg == 'mintime':
                        _result = int(_rec[2]) if _rec[2] else None
                    elif agg == 'maxtime':
                        _result = int(_rec[4]) if _rec[4] else None
                    elif agg == 'count':
                        _result = int(_rec[6]) if _rec[6] else None
                    elif agg == 'avg':
                        _result = _rec[7] / _rec[8] if _rec[6] else None
                    elif agg == 'rms':
                        _result = math.sqrt(_rec[14] / _rec[8]) if _rec[6] else None
                    elif agg == 'vecavg':
                        _result = math.sqrt((_rec[10] ** 2 + _rec[11] ** 2) / _rec[8] ** 2) if _rec[6] else None
                    elif agg == 'vecdir':
                        if _rec[10] == 0.0 and _rec[11] == 0.0:
                            _result = None
                        elif _rec[10] and _rec[11]:
                            deg = 90.0 - math.degrees(math.atan2(_rec[11], _rec[10]))
                            _result = deg if deg >= 0.0 else deg + 360.0
                        else:
                            _result = None
                    # if we have not found it then return None
                    else:
                        _result = None
                    # add the aggregate to our vector
                    _vec[agg_list.index(agg)].append(_result)
                # add the time to our time vector
                _time_vec.append(_rec[0])
        finally:
            # close our cursor
            _cursor.close()
        # get unit type and group for time
        (_time_type, _time_group) = weewx.units.getStandardUnitType(std_unit_system,
                                                                    'dateTime')
        # loop through each aggregate we were asked for getting unit and group and
        # producing a ValueTuple and adding to our result dictionary
        for agg in agg_list:
            (t, g) = weewx.units.getStandardUnitType(std_unit_system, obs_type, agg)
            _return[agg] = ValueTuple(_vec[agg_list.index(agg)], t, g)
        # return our time vector and dictionary of aggregate vectors
        return ValueTuple(_time_vec, _time_type, _time_group), _return


# ============================================================================
#                          class HighchartsMinRanges
# ============================================================================

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


# ============================================================================
#                            class HighchartsWeek
# ============================================================================

class HighchartsWeek(weewx.cheetahgenerator.SearchList):
    """SearchList to generate JSON vectors for Highcharts week plots."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsWeek, self).__init__(generator)

    def get_vector(self, db_manager, timespan, obs_type,
                   aggregate_type=None, aggregate_interval=None):
        """Get a data and timestamp vector for a given obs.

        Returns two vectors. The first is the obs data vector and the second
        is the timestamp vector in ms.
        """

        # get our vectors as ValueTuples, wrap in a try..except in case
        # obs_type does not exist
        try:
            (t_start_vt, t_stop_vt, obs_vt) = weewx.xtypes.get_series(obs_type, timespan, db_manager,
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

        # put into a dictionary to return
        search_list_extension = {'weekPlotStart': _start_ts * 1000,
                                 'weekPlotEnd': timespan.stop * 1000}
        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsWeek SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [search_list_extension]


# ============================================================================
#                            class HighchartsYear
# ============================================================================

class HighchartsYear(HighchartsDaySummarySearchList):
    """SearchList to generate JSON vectors for Highcharts year plots."""

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsYear, self).__init__(generator)

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
        t_span = TimeSpan(_start_ts, timespan.stop)

        # put into a dictionary to return
        search_list_extension = {'yearPlotStart': t_span.start * 1000,
                                 'yearPlotEnd': t_span.stop * 1000}

        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsYear SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [search_list_extension]


# ============================================================================
#                          class HighchartsWindRose
# ============================================================================


class HighchartsWindRose(HighchartsDaySummarySearchList):
    """SearchList to generate JSON vectors for Highcharts windrose plots."""

    default_speedfactor = [0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0]
    default_petal_colours = ['lightblue', 'blue', 'midnightblue', 'forestgreen',
                             'limegreen', 'green', 'greenyellow'
                             ]
    default_petals = 8
    dir_lookup = {16: ['N', 'NNE', 'NE', 'ENE', 'E', 'ESE', 'SE', 'SSE',
                       'S', 'SSW', 'SW', 'WSW', 'W', 'WNW', 'NW', 'NNW'
                       ],
                  8: ['N', 'NE', 'E', 'SE', 'S', 'SW', 'W', 'NW'],
                  4: ['N', 'E', 'S', 'W']
                  }
    default_bullseye_size = 3
    default_precision = 1
    default_calm_limit = 0.1

    def __init__(self, generator):
        # initialize my base class:
        super(HighchartsWindRose, self).__init__(generator)

        # get a dictionary of our skin settings
        windrose_dict = self.generator.skin_dict['Extras']['WindRose']
        # get plot title, if not specified then use a default
        self.title = windrose_dict.get('title', 'Wind Rose')
        # get the plot source, if not defined then use a default
        self.source = windrose_dict.get('source', 'windSpeed')
        if self.source == 'windGustDir':
            self.dir = 'windGustDir'
        else:
            self.dir = 'windDir'
        # get an aggregate type
        agg_type = windrose_dict.get('aggregate_type')
        agg_type = agg_type.strip().lower() if agg_type is not None else None
        self.agg_type = agg_type if agg_type in [None, 'avg', 'max', 'min'] else None
        # get any aggregate interval
        if self.agg_type is not None:
            agg_interval = weeutil.weeutil.to_int(windrose_dict.get('aggregate_interval',
                                                                    0))
            self.agg_interval = agg_interval if agg_interval > 0 else None
        else:
            self.agg_interval = None
        # get speed band boundaries, if not defined then set some defaults
        sf = weeutil.weeutil.option_as_list(windrose_dict.get('speedfactor',
                                                              self.default_speedfactor))
        # If a speedfactor was specified in the config dict it will be returned
        # as a list of strings, we need a list of numbers so do the type
        # conversion just in case. Wrap in a try..except in case one of the
        # elements can't be converted, if that is the case then use the default.
        try:
            speedfactor = [float(a) for a in sf]
        except ValueError:
            # we could not convert an element so use the default
            speedfactor = self.default_speedfactor
        # check that we have sufficient elements in the speedfactor list and
        # that their values are acceptable, if not use the default
        if len(speedfactor) != 7 or max(speedfactor) > 1.0 or min(speedfactor) < 0.0:
            speedfactor = self.default_speedfactor
        self.speedfactor = speedfactor
        # get petal colours, if not defined then set some defaults
        petal_colours = windrose_dict.get('petal_colors',
                                          self.default_petal_colours)
        petal_colours = self.default_petal_colours if len(petal_colours) != 7 else petal_colours
        for x in range(len(petal_colours) - 1):
            if petal_colours[x][0:2] == '0x':
                petal_colours[x] = '#' + petal_colours[x][2:]
        self.petal_colours = petal_colours
        # get the number of petals, if not defined then set a default
        petals = weeutil.weeutil.to_int(windrose_dict.get('petals',
                                                          self.default_petals))
        petals = self.default_petals if petals is None or petals == 0 else petals
        self.petals = petals
        # set our list of direction based on number of petals
        self.directions = self.dir_lookup.get(self.petals, self.dir_lookup[16])
        # get legend title, if not defined then set True
        self.show_legend_title = weeutil.weeutil.to_bool(windrose_dict.get('show_legend_title',
                                                                           True))
        # get band percent, if not defined then set True
        self.show_band_percent = weeutil.weeutil.to_bool(windrose_dict.get('show_band_percent',
                                                         True))
        # get % precision, if not defined then set a default
        self.precision = weeutil.weeutil.to_int(windrose_dict.get('precision',
                                                                  self.default_precision))
        # get bullseye diameter, if not defined then set a default
        self.bullseye_size = weeutil.weeutil.to_int(windrose_dict.get('bullseye_size',
                                                                      self.default_bullseye_size))
        # get bullseye colour, if not defined then set some defaults
        b_colour = windrose_dict.get('bullseye_color', 'white')
        b_colour = ''.join(['#', b_colour[2:]]) if b_colour[0:2] == '0x' else b_colour
        self.bullseye_colour = b_colour
        # get the 'calm' upper limit ie the speed below which we consider
        # aggregate wind speeds to be 'calm' (or 0)
        self.calm_limit = float(windrose_dict.get('calm_limit',
                                                  self.default_calm_limit))
        # and finally save our config dict
        self.windrose_dict = windrose_dict

    def calc_windrose(self, timespan, db_lookup, period):
        """Function to calculate windrose JSON data for a given timespan."""

        # initialise a dictionary for our results
        wr_dict = {}
        if period <= 604800:
            # week or less, get our vectors from archive via xtypes.get_series()
            # get our wind speed vector
            t_span = TimeSpan(timespan.stop - period + 1, timespan.stop)
            (_x_vt, time_vec_speed_vt, speed_vec_vt) = weewx.xtypes.get_series(self.source,
                                                                               t_span,
                                                                               db_lookup())
            # convert our speed vector
            speed_vec_vt = self.generator.converter.convert(speed_vec_vt)
            # get our wind direction vector
            t_span = TimeSpan(timespan.stop-period + 1, timespan.stop)
            (_x_vt, time_vec_dir_stop_vt, direction_vec_vt) = weewx.xtypes.get_series(self.dir,
                                                                               t_span,
                                                                               db_lookup())
        else:
            # get our vectors from daily summaries using custom getStatsVectors
            # get our data tuples for speed
            t_span = TimeSpan(timespan.stop - period, timespan.stop)
            (time_vec_speed_vt, speed_dict) = self.get_day_summary_vectors(db_lookup(),
                                                                           'wind',
                                                                           t_span,
                                                                           ['avg'])
            # get our speed vector ValueTuple out of the dictionary and convert
            # it
            speed_vec_vt = self.generator.converter.convert(speed_dict['avg'])
            # get our data tuples for direction
            (time_vec_dir_vt, dir_dict) = self.get_day_summary_vectors(db_lookup(),
                                                                       'wind',
                                                                       t_span,
                                                                       ['vecdir'])
            # get our vector ValueTuple out of the dictionary, no need to convert
            direction_vec_vt = dir_dict['vecdir']
        # get a string with our speed units
        speed_units_str = self.generator.skin_dict['Units']['Labels'].get(speed_vec_vt.unit).strip()
        # to get a better display we will set our upper speed to a multiple of 10
        # find maximum speed from our data
        # it is possible there could be a None value in speed_vec_vt.value so
        # strip out any None values first, it is also possible that there could
        # be no non-None values in speed_vec_vt.value so be prepared to catch
        # the ValueError and use an appropriate default
        try:
            max_speed = max([v for v in speed_vec_vt.value if v is not None])
        except ValueError as e:
            # there were no non-None values so use a reasonable default
            max_speed = 10
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
        samples = len(time_vec_speed_vt.value)
        # calc factor to be applied to convert counts to %
        pcent_factor = 100.0/samples
        # Loop through each sample and increment direction counts
        # and speed ranges for each direction as necessary. 'None'
        # direction is counted as 'calm' (or 0 speed) and
        # (by definition) no direction and are plotted in the
        # 'bullseye' on the plot
        i = 0
        while i < samples:
            if (speed_vec_vt.value[i] is None) or (direction_vec_vt.value[i] is None):
                speed_bin[0] += 1
            else:
                bin_num = int((direction_vec_vt.value[i]+11.25)/22.5) % self.petals
                if speed_vec_vt.value[i] <= self.calm_limit:
                    speed_bin[0] += 1
                elif speed_vec_vt.value[i] > speed_list[5]:
                    wind_bin[6][bin_num] += 1
                elif speed_vec_vt.value[i] > speed_list[4]:
                    wind_bin[5][bin_num] += 1
                elif speed_vec_vt.value[i] > speed_list[3]:
                    wind_bin[4][bin_num] += 1
                elif speed_vec_vt.value[i] > speed_list[2]:
                    wind_bin[3][bin_num] += 1
                elif speed_vec_vt.value[i] > speed_list[1]:
                    wind_bin[2][bin_num] += 1
                elif speed_vec_vt.value[i] > 0:
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
        calm_percent_str = ''.join([str(round(speed_bin[0] * pcent_factor, self.precision)),
                                    "%"])
        if self.show_band_percent:
            legend_labels[0] = ''.join(["Calm (", calm_percent_str, ")"])
            legend_no_labels[0] = ''.join(["Calm (", calm_percent_str, ")"])
        else:
            legend_labels[0] = "Calm"
            legend_no_labels[0] = "Calm"
        i = 1
        while i < 7:
            if self.show_band_percent:
                legend_labels[i] = ''.join([str(round_int(speed_list[i - 1], 0)),
                                            "-", str(round_int(speed_list[i], 0)),
                                            speed_units_str, " (",
                                            str(round(speed_bin[i] * pcent_factor, self.precision)),
                                            "%)"])
                legend_no_labels[i] = ''.join([str(round_int(speed_list[i - 1], 0)),
                                               "-", str(round_int(speed_list[i], 0)),
                                               " (",
                                               str(round(speed_bin[i] * pcent_factor, self.precision)),
                                               "%)"])
            else:
                legend_labels[i] = ''.join([str(round_int(speed_list[i - 1], 0)),
                                            "-", str(round_int(speed_list[i], 0)),
                                            speed_units_str])
                legend_no_labels[i] = ''.join([str(round_int(speed_list[i - 1], 0)),
                                               "-", str(round_int(speed_list[i], 0))])
            i += 1
        # build up our JSON result string
        json_result_str = ''.join(['[{"name": "', legend_labels[6],
                                   '", "data": ', json.dumps(wind_bin[6]),
                                   '}'])
        json_result_no_label_str = ''.join(['[{"name": "', legend_no_labels[6],
                                            '", "data": ', json.dumps(wind_bin[6]),
                                            '}'])
        i = 5
        while i > 0:
            json_result_str = ''.join([json_result_str, ', {"name": "',
                                       legend_labels[i], '", "data": ',
                                       json.dumps(wind_bin[i]), '}'])
            json_result_no_label_str = ''.join([json_result_no_label_str,
                                                ', {"name": "',
                                                legend_no_labels[i],
                                                '", "data": ',
                                                json.dumps(wind_bin[i]), '}'])
            i -= 1
        # add ] to close our json array
        json_result_str = ''.join([json_result_str, ']'])

        # fill our results dictionary
        wr_dict['windrosejson'] = json_result_str
        json_result_no_label_str = ''.join([json_result_no_label_str, ']'])
        wr_dict['windrosenolabeljson'] = json_result_no_label_str
        # Get our xAxis categories in json format
        wr_dict['xAxisCategoriesjson'] = json.dumps(self.directions)
        # Get our yAxis min/max settings
        wr_dict['yAxisjson'] = '{"max": %f, "min": %f}' % (max_y_axis, -1.0 * bullseye_radius)
        # Get our stacked column colours in json format
        wr_dict['coloursjson'] = json.dumps(self.petal_colours)
        # Manually construct our plot title in json format
        wr_dict['titlejson'] = ''.join(["[\"", self.title, "\"]"])
        # Manually construct our legend title in json format
        # Set to null if not required
        if self.show_legend_title:
            if self.source == 'windSpeed':
                legend_title_json = "[\"Wind Speed\"]"
                legend_title_no_label_json = ''.join(["[\"Wind Speed<br>(",
                                                      speed_units_str,
                                                      ")\"]"])
            else:
                legend_title_json = "[\"Wind Gust\"]"
                legend_title_no_label_json = ''.join(["[\"Wind Gust<br>(",
                                                      speed_units_str,
                                                      ")\"]"])
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
        _period_list = option_as_list(self.windrose_dict.get('period', ['day']))
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
                    except (ValueError, TypeError):
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
                _suffix = str(_period) if _period in ['day', 'week', 'month', 'year', 'all', 'alltime'] else str(period)
                sle_dict[''.join(['wr', _suffix])] = self.calc_windrose(timespan,
                                                                        db_lookup,
                                                                        period)
        t2 = time.time()
        if weewx.debug >= 2:
            logdbg("HighchartsWindRose SLE executed in %0.3f seconds" % (t2 - t1))
        # return our json data
        return [sle_dict]


# ==============================================================================
#                             Utility functions
# ==============================================================================


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


# ==============================================================================
#                           class HighchartsSpans
# ==============================================================================

class HighchartsSpans(weewx.cheetahgenerator.SearchList):
    """SLE to return various custom TimeSpanBinder based tags."""

    def __init__(self, generator):
        # initialise my superclass
        super(HighchartsSpans, self).__init__(generator)

    def get_extension_list(self, timespan, db_lookup):
        """Returns a search list with various custom TimespanBinder tags.

        Parameters:
            timespan: An instance of weeutil.weeutil.TimeSpan. This will hold
                      the start and stop times of the domain of valid times.

            db_lookup: This is a function that, given a data binding as its
                       only parameter, will return a database manager object.

        Returns:
            tspan_binder: A TimespanBinder object that allows a data binding to
                          be specified (default to None) when calling $alltime
                          eg $alltime.outTemp.max for the all time high outside
                          temp.
                          $alltime($data_binding='wd_binding').humidex.max
                          for the all time high humidex where humidex
                          resides in the 'wd_binding' database.

                          Standard WeeWX unit conversion and formatting options
                          are available.
        """

        t1 = time.time()

        class HighchartsTimeBinder(weewx.tags.TimeBinder):
            """Class supporting additional TimeSpan based aggregate tags."""

            def __init__(self, db_lookup, report_time,
                         formatter=weewx.units.Formatter(),
                         converter=weewx.units.Converter(), **option_dict):
                # initialise my superclass
                super(HighchartsTimeBinder, self).__init__(db_lookup, report_time,
                                                           formatter=formatter,
                                                           converter=converter,
                                                           **option_dict)

            def last_seven_day(self, data_binding=None):
                """Return a TimeSpanBinder for the the last 7 days."""

                # calculate the time at midnight, seven days ago.
                _stop_d = datetime.date.fromtimestamp(timespan.stop)
                seven_day_dt = _stop_d - datetime.timedelta(weeks=1)
                # now convert it to unix epoch time:
                seven_day_ts = time.mktime(seven_day_dt.timetuple())
                # get our 7 day timespan
                seven_day_tspan = TimeSpan(seven_day_ts, timespan.stop)
                # now return a TimespanBinder object, using the timespan we just
                # calculated
                return TimespanBinder(seven_day_tspan,
                                      self.db_lookup, context='week',
                                      data_binding=data_binding,
                                      formatter=self.formatter,
                                      converter=self.converter)

            def last_year(self, data_binding=None):
                """Return a TimeSpanBinder for the the last year."""

                # our start time is one year ago from midnight at the start of
                # today
                # first get the start of today
                _ts = weeutil.weeutil.startOfDay(timespan.stop)
                # then go back 1 year
                _ts_dt = datetime.datetime.fromtimestamp(_ts)
                try:
                    _start_dt = _ts_dt.replace(year=_ts_dt.year - 1)
                except ValueError:
                    # if we strike an invalid date, eg 29 February in a
                    # non-leap year, goto the day before
                    _start_dt = _ts_dt.replace(year=_ts_dt.year - 1, day=_ts_dt.day - 1)
                # now convert it to unix epoch time
                _start_ts = time.mktime(_start_dt.timetuple())
                # get our timespan
                last_year_tspan = TimeSpan(_start_ts, timespan.stop)
                # now return a TimespanBinder object, using the timespan we just
                # calculated
                return TimespanBinder(last_year_tspan,
                                      self.db_lookup, context='year',
                                      data_binding=data_binding,
                                      formatter=self.formatter,
                                      converter=self.converter)

        time_binder = HighchartsTimeBinder(db_lookup,
                                           timespan.stop,
                                           self.generator.formatter,
                                           self.generator.converter)

        t2 = time.time()
        if weewx.debug >= 2:
            log.debug("HighchartsSpans SLE executed in %0.3f seconds" % (t2-t1))

        return [time_binder]
