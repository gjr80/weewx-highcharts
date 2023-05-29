"""
highchartsgenerator.py

WeeWX generator to produce data files for use with Highcharts.

Copyright (C) 2023 Gary Roderick                  gjroderick<at>gmail.com

This program is free software: you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free
Software Foundation, either version 3 of the License, or (at your option) any
later version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program.  If not, see http://www.gnu.org/licenses/.

Version: 0.1.0                                      Date: 8 May 2023

Revision History
    8 May 2023          v0.1.0
       - initial implementation
"""

# python imports
import calendar
import datetime
import json
import logging
import math
import os
import time
from datetime import date

# WeeWX imports
import weewx
import weewx.cheetahgenerator
import weewx.units
import weeutil.weeutil
import weewx.xtypes
from weewx.units import ValueTuple, getStandardUnitType, convert
from weeutil.weeutil import TimeSpan, option_as_list

log = logging.getLogger(__name__)

VERSION = '0.4.0a1'


class HighchartsGenerator(weewx.reportengine.ReportGenerator):
    """Class for generating data files for use with Highcharts."""

    def __init__(self, config_dict, skin_dict, *args, **kwargs):
        """Initialise and instance of HighchartsGenerator."""

        # initialize my superclass
        super(HighchartsGenerator, self).__init__(self, config_dict, skin_dict, *args, **kwargs)
        self.generic_dict = dict()


    def run(self):
        """Main entry point."""

        self.setup()
        self.gen_files(self.gen_ts)

    def setup(self):
        """Perform any required post-__init__ setup."""

        # generic_dict will contain "generic" labels, such as "Outside Temperature"
        try:
            self.generic_dict = self.skin_dict['Labels']['Generic']
        except KeyError:
            pass
        # text_dict contains translated text strings
        self.text_dict = self.skin_dict.get('Texts', {})
        self.charts_dict = self.skin_dict['HighchartsGenerator']
        self.formatter = weewx.units.Formatter.fromSkinDict(self.skin_dict)
        self.converter = weewx.units.Converter.fromSkinDict(self.skin_dict)
        # ensure that the skin_dir is in the charts_dict
        self.charts_dict['skin_dir'] = os.path.join(self.config_dict['WEEWX_ROOT'],
                                                    self.skin_dict['SKIN_ROOT'],
                                                    self.skin_dict['skin'])
        # ensure that we are in a consistent right location
        os.chdir(self.charts_dict['skin_dir'])
        # get UTC offset
        time_struct = time.localtime(time.time())
        self.utc_offset = (calendar.timegm(time_struct) - calendar.timegm(time.gmtime(time.mktime(time_struct))))/60


    def gen_files(self, gen_ts):
        """Generate the Highcharts data files.

        The time scales will be chosen to include the given timestamp, with nice beginning and
        ending times.

        Args:
            gen_ts (int): The time around which plots are to be generated. This will also be used
                as the bottom label in the plots. [optional. Default is to use the time of the last
                record in the database.]

        [HighchartsGenerator]
            ....
            [[Week]]
                [[[temperature]]]
                    [[[[outTemp]]]]
                    [[[[apptemp]]]]
                [[[pressure]]]
                    [[[[barometer]]]]
            [[Year]]
                aggregate_type = max
                aggregate_interval = 86400
                [[[temperature]]]
                    [[[[outTemp]]]]
                    [[[[apptemp]]]]
                [[[pressure]]]
                    [[[[barometer]]]]

        """

        # the time we started processing, required fo summary reporting later
        t1 = time.time()
        # number of files generated
        ngen = 0
        # determine how much logging is desired
        log_success = weeutil.weeutil.to_bool(weeutil.weeutil.search_up(self.charts_dict,
                                                                        'log_success',
                                                                        True))
        # iterate over each chart group stanza (week, year, etc.)
        for chart_group in self.charts_dict.sections:
            # accumulate all options from parent nodes:
            chart_group_options = weeutil.weeutil.accumulateLeaves(self.charts_dict[chart_group])
            chart_root = os.path.join(self.config_dict['WEEWX_ROOT'],
                                      chart_group_options['HTML_ROOT'])
            # get the path and file for the data file to be generated
            chart_file = os.path.join(chart_root, '%s.json' % chart_group)
            # now, iterate over all charts in this chart group
            for chart_name in self.charts_dict[chart_group].sections:
                # accumulate all options from parent nodes:
                chart_options = weeutil.weeutil.accumulateLeaves(self.charts_dict[chart_group][chart_name])
                # get the chart generation timestamp, nominally it is gen_ts
                # but if it is None then use the last good timestamp in the db
                # and failing that fall back to the current system time
                if gen_ts is not None:
                    chart_gen_ts = gen_ts
                else:
                    binding = chart_options['data_binding']
                    db_manager = self.db_binder.get_manager(binding)
                    chart_gen_ts = db_manager.lastGoodStamp()
                    if chart_gen_ts is None:
                        chart_gen_ts = time.time()
                # check whether this plot needs to be done at all, if it
                # doesn't move on to the next chart
                if self._skip_this_plot(chart_gen_ts, chart_options, chart_file):
                    continue
                # generate the chart data
                chart_data = self.gen_chart_data(chart_gen_ts,
                                                 chart_options,
                                                 self.charts_dict[chart_group][chart_name])
                if chart_data:
                    chart_data_str = json.dumps(chart_data)
                    self.get_chart(chart_gen_ts,
                                   chart_options,
                                   chart_name,
                                   chart_data)
                    # Create the destination directory for the chart data file.
                    # Wrap in a try block in case it already exists.
                    try:
                        os.makedirs(os.path.dirname(chart_file))
                    except OSError:
                        pass
                    # now write the data to file
                    try:
                        with open(chart_file, 'w') as f:
                            f.write(chart_data_str)
                        ngen += 1
                    except IOError as e:
                        log.error("Unable to save to file '%s' %s:", chart_file, e)
        # get the finish timestamp
        t2 = time.time()
        # if required log success
        if log_success:
            log.info("Generated %d json data files for report %s in %.2f seconds",
                     ngen,
                     self.skin_dict['REPORT_NAME'],
                     t2 - t1)

    def gen_chart_data(self, chart_gen_ts, chart_options, chart_dict):
        """Generate the data for a single chart."""

        # calculate suitable min, max timestamps for the requested time length
        x_tspan = self.scale_time(int(chart_options.get('time_length', 86400)),
                                  chart_gen_ts)
        # Calculate the domain over which we should check for non-null data. It will be
        # 'None' if we are not to do the check at all.
        check_domain = self._get_check_domain(chart_options.get('skip_if_empty', False),
                                              x_tspan)
        # iterate over each 'line' on the chart
        for line_name in chart_dict.sections:
            # accumulate options from parent nodes
            line_options = weeutil.weeutil.accumulateLeaves(chart_dict[line_name])
            # determine the obs type to use for this line, by default use the
            # line name.
            var_type = line_options.get('data_type', line_name)
            # obtain a db manager so we can access hte database
            binding = line_options['data_binding']
            db_manager = self.db_binder.get_manager(binding)
            # if we were asked, see if there is any non-null data in the plot
            skip = self._skip_if_empty(db_manager, var_type, check_domain)
            if skip:
                # there is nothing but null data so skip this line and keep
                # going
                continue
            # either we found some non-null data, or skip_if_empty was false
            # and we don't care
            have_data = True
            # is there an aggregation type
            aggregate_type = line_options.get('aggregate_type', 'none')
            if aggregate_type.lower() in ('', 'none'):
                # no aggregation specified
                aggregate_type = aggregate_interval = None
            else:
                try:
                    # an aggregation type was specified, get the interval
                    aggregate_interval = weeutil.weeutil.nominal_spans(line_options['aggregate_interval'])
                except KeyError:
                    log.error("Aggregate interval required for aggregate type %s",
                              aggregate_type)
                    log.error("Line type %s skipped", var_type)
                    continue
            # we need to pass the line options and plotgen_ts to our xtype
            # first get a copy of line_options
            option_dict = dict(line_options)
            # but we need to pop off aggregate_type and aggregate_interval as
            # they are used as explicit arguments in our xtypes call
            option_dict.pop('aggregate_type', None)
            option_dict.pop('aggregate_interval', None)
            # then add plotgen_ts
            option_dict['plotgen_ts'] = chart_gen_ts
            try:
                start_vec_t, stop_vec_t, data_vec_t = weewx.xtypes.get_series(var_type,
                                                                              x_tspan,
                                                                              db_manager,
                                                                              aggregate_type=aggregate_type,
                                                                              aggregate_interval=aggregate_interval,
                                                                              **option_dict)
            except weewx.UnknownType:
                # If skip_if_empty is set, it's OK if a type is unknown.
                if not skip:
                    raise

    def get_chart(self, chart_gen_ts, chart_options, chart_name, chart_data):
        """Construct the chart data string."""

        _data = dict()
        _data['_version'] = '%s' % VERSION
        _data['utcoffset'] = '%d' % self.utc_offset
        _data['timespan'] = {'start': 'fred',
                             'stop': chart_gen_ts}
        _data[chart_name] = dict()
        _data[chart_name]['series'] = chart_data
        _data[chart_name]['units'] = 'C'
        if self.min_range.get(chart_name) is not None:
            _data[chart_name]['minRange'] = self.min_range.get(chart_name)

        return _data

    def scale_time(self, ts, time_delta):
        """Calculate a suitable chart timespan given a chart time and time length.

        ts:         the epoch timestamp of the end of the time period of concern
        time_delta: the length of the time period of concern in seconds

        Returns a TimeSpan object representing the time scale to be used.

        Example 1: 24 hours on an hour boundary
        >>> from weeutil.weeutil import timestamp_to_string as to_string
        >>> time_ts = time.mktime(time.strptime("2013-05-17 08:00", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 24*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 09:00:00 PDT (1368720000) 2013-05-17 09:00:00 PDT (1368806400) 10800

        Example 2: 24 hours on a 3-hour boundary
        >>> time_ts = time.mktime(time.strptime("2013-05-17 09:00", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 24*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 09:00:00 PDT (1368720000) 2013-05-17 09:00:00 PDT (1368806400) 10800

        Example 3: 24 hours on a non-hour boundary
        >>> time_ts = time.mktime(time.strptime("2013-05-17 09:01", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 24*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 12:00:00 PDT (1368730800) 2013-05-17 12:00:00 PDT (1368817200) 10800

        Example 4: 27 hours
        >>> time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 27*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 06:00:00 PDT (1368709200) 2013-05-17 09:00:00 PDT (1368806400) 10800

        Example 5: 3 hours on a 15 minute boundary
        >>> time_ts = time.mktime(time.strptime("2013-05-17 07:45", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 3*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-17 05:00:00 PDT (1368792000) 2013-05-17 08:00:00 PDT (1368802800) 900

        Example 6: 3 hours on a non-15 minute boundary
        >>> time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 3*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-17 05:00:00 PDT (1368792000) 2013-05-17 08:00:00 PDT (1368802800) 900

        Example 7: 12 hours
        >>> time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 12*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 20:00:00 PDT (1368759600) 2013-05-17 08:00:00 PDT (1368802800) 3600

        Example 8: 15 hours
        >>> time_ts = time.mktime(time.strptime("2013-05-17 07:46", "%Y-%m-%d %H:%M"))
        >>> xmin, xmax, xinc = scaletime(time_ts - 15*3600, time_ts)
        >>> print(to_string(xmin), to_string(xmax), xinc)
        2013-05-16 17:00:00 PDT (1368748800) 2013-05-17 08:00:00 PDT (1368802800) 7200
        """

        if time_delta <= 0:
            raise weewx.ViolatedPrecondition("scale_time called with time_delta <= 0")

        time_min_dt = datetime.datetime.fromtimestamp(ts - time_delta)

        if time_delta <= 16 * 3600:
            # use time_max_dt and the one-hour boundary below time_min_dt
            # get to the one-hour boundary below time_min_dt:
            start_dt = time_min_dt.replace(minute=0, second=0, microsecond=0)
            # if time_min_dt is not on a one-hour boundary we are done,
            # otherwise round down to the next one-hour boundary
            if time_min_dt == start_dt:
                start_dt -= datetime.timedelta(hours=1)
        elif time_delta <= 27 * 3600:
            # use time_max_dt and the three-hour boundary below time_min_dt
            # h is the hour of time_min_dt
            h = time_min_dt.timetuple()[3]
            # now get the three-hour boundary below time_min_dt
            start_dt = time_min_dt.replace(minute=0, second=0, microsecond=0) \
                - datetime.timedelta(hours=h % 3)
            # if time_min_dt is not on a three-hour boundary we are done,
            # otherwise round down to the next three-hour boundary
            if time_min_dt == start_dt:
                start_dt -= datetime.timedelta(hours=3)
        else:
            # use time_max_dt and the day boundary below time_min_dt
            start_dt = time_min_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        # return a TimeSpan object
        return weeutil.weeutil.TimeSpan(int(time.mktime(start_dt.timetuple())), ts)

    @staticmethod
    def _skip_this_plot(chart_gen_ts, chart_options, chart_file):
        """Do we skip this chart?

        A chart can be skipped if it was generated recently and has not
        changed. This happens if the time since the chart was generated is less
        than the aggregation interval. A chart may also be skipped if a
        stale_age has been specified, then it can also be skipped if the file
        has been freshly generated.
        """

        # get a numeric aggregate interval (it could be a string, eg 'hour')
        aggregate_interval = weeutil.weeutil.nominal_spans(chart_options.get('aggregate_interval'))

        # If the is no aggregation interval we generate every time. Also, the
        # chart definitely has to be generated if it doesn't exist.
        if aggregate_interval is None or not os.path.exists(chart_file):
            return False

        # if it is older than the aggregate interval it has to be regenerated
        if chart_gen_ts - os.stat(chart_file).st_mtime >= aggregate_interval:
            return False

        # if we are on an aggregation boundary regenerate
        time_dt = datetime.datetime.fromtimestamp(chart_gen_ts)
        tdiff = time_dt - time_dt.replace(hour=0, minute=0, second=0, microsecond=0)
        if abs(tdiff.seconds % aggregate_interval) < 1:
            return False

        # check for stale plots, but only if 'stale_age' is defined
        stale = weeutil.weeutil.to_int(chart_options.get('stale_age'))
        if stale:
            t_now = time.time()
            try:
                last_mod = os.path.getmtime(chart_file)
                if t_now - last_mod < stale:
                    log.debug("Skip '%s': last_mod=%s age=%s stale=%s",
                              chart_file, last_mod, t_now - last_mod, stale)
                    return True
            except os.error:
                pass
        return True

    @staticmethod
    def _skip_if_empty(db_manager, var_type, check_domain):
        """

        Args:
            db_manager: An open instance of weewx.manager.Manager, or a subclass.

            var_type: An observation type to check (e.g., 'outTemp')

            check_domain: A two-way tuple of timestamps that contain the time domain to be checked
            for non-null data.

        Returns:
            True if there is no non-null data in the domain. False otherwise.
        """
        if check_domain is None:
            return False
        try:
            val = weewx.xtypes.get_aggregate(var_type, check_domain, 'not_null', db_manager)
        except weewx.UnknownAggregation:
            return True
        return not val[0]

    @staticmethod
    def _get_check_domain(skip_if_empty, x_domain):
        """"""
        # convert skip_if_empty to lower-case, it might not be a string so be
        # prepared for an AttributeError
        try:
            skip_if_empty = skip_if_empty.lower()
        except AttributeError:
            pass
        # if it's something we recognize as False return None
        if skip_if_empty in ['false', False, None]:
            return None
        # if it's True return the existing time domain
        elif skip_if_empty in ['true', True]:
            return x_domain
        # Otherwise it's probably a string (such as 'day', 'month', etc).
        # Return the corresponding time domain
        else:
            return weeutil.weeutil.timespan_by_name(skip_if_empty, x_domain.stop)

