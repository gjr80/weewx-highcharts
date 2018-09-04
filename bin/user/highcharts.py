# highcharts.py
#
# A function to return a vector of aggregate data based on the daily summaries.
#
# Copyright (C) 2016-18 Gary Roderick               gjroderick<at>gmail.com
#
# This program is free software: you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free
# Software Foundation, either version 3 of the License, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more
# details.
#
# You should have received a copy of the GNU General Public License along with
# this program.  If not, see http://www.gnu.org/licenses/.
#
#
# Version: 0.2.2                                    Date: 4 September 2018
#
# Revision History
#   4 September 2018    v0.2.2
#       - fixed error in getDaySummaryVectors aggregate calculations due to 
#         WeeWX archive_day_xxxxx schema chnage
#   16 May 2017         v0.2.1
#       - no change, version number chnage only
#   4 May 2017          v0.2.0
#       - no change, version number chnage only
#   22 November 2016    v0.1.0
#       - initial implementation

import math
import weewx
import weeutil.weeutil
import syslog

from weewx.units import getStandardUnitType, ValueTuple

def logmsg(level, msg):
    syslog.syslog(level, 'highcharts: %s' % msg)

def logdbg(msg):
    logmsg(syslog.LOG_DEBUG, msg)

def loginf(msg):
    logmsg(syslog.LOG_INFO, msg)

def logerr(msg):
    logmsg(syslog.LOG_ERR, msg)

def getDaySummaryVectors(db_manager, sql_type, timespan, agg_list='max'):
    """ Return a vector of aggregate data from the WeeWX daily summaries.

        Parameters:
          db_manager: A database manager object for the WeeWX archive.

          sql_type:   A statistical type, such as 'outTemp' 'barometer' etc.

          startstamp: The start time of the vector required.

          stopstamp:  The stop time of the vector required.

          agg_list:   A list of the aggregates required eg ['max', 'min'].
                      Member elements can be any of 'min', 'max', 'mintime',
                      'maxtime', 'gustdir', 'sum', 'count', 'avg', 'rms',
                      'vecavg' or 'vecdir'.
       """

    # get our interpolation dictionary for the query
    interDict = {'start'        : weeutil.weeutil.startOfDay(timespan.start),
                 'stop'         : timespan.stop,
                 'table_name'   : 'archive_day_%s' % sql_type}
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
    # get a cursor object for our query
    _cursor = db_manager.connection.cursor()
    try:
        # put together our SQL query string
        sql_str = "SELECT * FROM %(table_name)s  WHERE dateTime >= %(start)s AND dateTime < %(stop)s" % interDict
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
                elif agg == 'avg' :
                    _result = _rec[7]/_rec[8] if _rec[6] else None
                elif agg == 'rms' :
                    _result =  math.sqrt(_rec[14]/_rec[8]) if _rec[6] else None
                elif agg == 'vecavg' :
                    _result = math.sqrt((_rec[10]**2 + _rec[11]**2) / _rec[8]**2) if _rec[6] else None
                elif agg == 'vecdir' :
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
    # loop through each aggregate we were asked for getting unit and group and producing a ValueTuple
    # and adding to our result dictionary
    for agg in agg_list:
        (t,g) = weewx.units.getStandardUnitType(std_unit_system, sql_type, agg)
        _return[agg]=ValueTuple(_vec[agg_list.index(agg)], t, g)
    # return our time vector and dictionary of aggregate vectors
    return (ValueTuple(_time_vec, _time_type, _time_group), _return)