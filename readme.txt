The Highcharts for WeeWX extension provides graphical plots of WeeWX
observational data using the Highcharts charting tool.

Highcharts for WeeWX consists of a skin generating two reports, a number of
Search List Extensions (SLE) and supporting JavaScript.

Pre-Requisites

Highcharts for WeeWX requires Weewx v3.4.0 or greater. The display of the
Highcharts for WeeWX extension data on a web page using the included Javascript
files requires the Highcharts Highstock charting tool and JQuery JavaScript 
library.

Installation Instructions

Installation using the wee_extension utility 

Note:   Symbolic names are used below to refer to some file location on the 
WeeWX system. These symbolic names allow a common name to be used to refer to
a directory that may be different from system to system. The following symbolic 
names are used below:
-   $DOWNLOAD_ROOT. The path to the directory containing the downloaded 
    Highcharts for WeeWX extension.
-   $HTML_ROOT. The path to the directory where WeeWX generated reports are
    saved. This directory is normally set in the [StdReport] section of 
    weewx.conf. Refer to 'where to find things' in the WeeWX User's Guide:
    http://weewx.com/docs/usersguide.htm#Where_to_find_things for further 
    information.
-   $SKIN_ROOT. The path to the directory where WeeWX skin folders are located
    This directory is normally set in the [StdReport] section of 
    weewx.conf. Refer to 'where to find things' in the WeeWX User's Guide:
    http://weewx.com/docs/usersguide.htm#Where_to_find_things for further 
    information.

1.  Download the latest Highcharts for WeeWX extension from the Highcharts for
WeeWX releases page (https://github.com/gjr80/weewx-highcharts/releases) into
a directory accessible from the WeeWX machine.

    $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-highcharts/releases/download/v0.2.2/hfw-1.0.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Highcharts for 
    WeeWX extension is to be downloaded.

2.  Stop WeeWX:

    $ sudo /etc/init.d/weewx stop

	or

    $ sudo service weewx stop

    or

    $ sudo systemctl stop weewx

3.  Install the Highcharts for WeeWX extension downloaded at step 1 using the
*wee_extension* utility:

    $ wee_extension --install=$DOWNLOAD_ROOT/hfw-1.0.0.tar.gz

    This will result in output similar to the following:

        Request to install '/var/tmp/hfw-1.0.0.tar.gz'
        Extracting from tar archive /var/tmp/hfw-1.0.0.tar.gz
        Saving installer file to /home/weewx/bin/user/installer/Hfw
        Saved configuration dictionary. Backup copy at /home/weewx/weewx.conf.20161123124410
        Finished installing extension '/var/tmp/hfw-1.0.0.tar.gz'

4. Start WeeWX:

    $ sudo /etc/init.d/weewx start

	or

    $ sudo service weewx start

    or

    $ sudo systemctl start weewx

This will result in the Highcharts for WeeWX JSON data files being generated
during each report generation cycle. A default installation will result in the
generated JSON data files being placed in the $HTML_ROOT/json directory. The
Highcharts for WeeWX installation can be further customized (eg units of
measure, file locations etc) by referring to the Highcharts for WeeWX wiki.

Manual installation

1.  Download the latest Highcharts for WeeWX extension from the Highcharts for
WeeWX releases page (https://github.com/gjr80/weewx-highcharts/releases) into
a directory accessible from the WeeWX machine.

    $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-highcharts/releases/download/v0.2.2/hfw-1.0.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Highcharts for 
    WeeWX extension is to be downloaded.

2.  Unpack the extension as follows:

    $ tar xvfz hfw-1.0.0.tar.gz

3.  Copy files from within the resulting folder as follows:

    $ cp highcharts-weewx/bin/user/*.py $BIN_ROOT/user
    $ cp -R highcharts-weewx/skins/Highcharts $SKIN_ROOT
    
	replacing the symbolic names $BIN_ROOT and $SKIN_ROOT with the nominal 
    locations for your installation.

4.  Edit weewx.conf:

    $ vi weewx.conf

5.  In weewx.conf, modify the [StdReport] section by adding the following 
sub-section:

    [[Highcharts]]
        skin = Highcharts
        [[[Units]]]
            [[[[StringFormats]]]]
                centibar = %.0f
                cm = %.2f
                cm_per_hour = %.2f
                degree_compass = %.0f
                degree_C = %.1f
                degree_F = %.1f
                foot = %.0f
                inch = %.2f
                inch_per_hour = %.2f
                hPa = %.1f
                inHg = %.3f
                km_per_hour = %.0f
                km_per_hour2 = %.1f
                knot = %.0f
                knot2 = %.1f
                mbar = %.1f
                meter = %.0f
                meter_per_second = %.1f
                meter_per_second2 = %.1f
                mile_per_hour = %.0f
                mile_per_hour2 = %.1f
                mm = %.1f
                mm_per_hour = %.1f
                mmHg = %.1f
                percent = %.0f
                uv_index = %.1f
                volt = %.1f
                watt_per_meter_squared = %.0f
                NONE = N/A
            [[[[Labels]]]]
                centibar = cb
                cm = cm
                cm_per_hour = cm/hr
                degree_compass = \u00B0
                degree_C = \u00B0 C
                degree_F = \u00B0 F
                foot = feet
                hPa = hPa
                inch = in
                inch_per_hour = in/hr
                inHg = inHg
                km_per_hour = km/hr
                km_per_hour2 = km/hr
                knot = knots
                knot2 = knots
                mbar = mbar
                meter = meters
                meter_per_second = m/s
                meter_per_second2 = m/s
                mile_per_hour = mph
                mile_per_hour2 = mph
                mm = mm
                mm_per_hour = mm/hr
                mmHg = mmHg
                percent = %
                uv_index = Index
                volt = V
                watt_per_meter_squared = W/m\u00B2
                NONE = ""
            [[[[Groups]]]]
                group_altitude = meter
                group_degree_day = degree_C_day
                group_pressure = hPa
                group_rain = mm
                group_rainrate = mm_per_hour
                group_speed = km_per_hour
                group_speed2 = km_per_hour2
                group_temperature = degree_C
        [[[Extras]]]
            [[[[MinRange]]]]
                barometer = "20, hPa"
                outTemp = "10, degree_C"
                radiation = 500
                rain = "5, mm"
                UV = 16
                windchill = "10, degree_C"
                windSpeed = 10
            [[[[WindRose]]]]
                bullseye_percent = True
                band_percent = True
                aggregate_type = ""
                petal_colors = "aqua, 0x0099FF, 0x0033FF, 0x009900, 0x00CC00, 0x33FF33, 0xCCFF00"
                period = "86400, 604800, month, year"
                bullseye_size = 20
                precision = 1
                petals = 16
                aggregate_interval = ""
                speedfactor = "0.0, 0.1, 0.2, 0.3, 0.5, 0.7, 1.0"
                title = Wind Rose
                legend_title = True
                calm_limit = 0.5
                source = windSpeed
                bullseye_color = 0xFFFACD
        [[[CheetahGenerator]]]
            HTML_ROOT = public_html/json

6. Start WeeWX:

    $ sudo /etc/init.d/weewx start

	or

    $ sudo service weewx start

    or

    $ sudo systemctl start weewx

This will result in the Highcharts for WeeWX JSON data files being generated
during each report generation cycle. A default installation will resulting in 
the generated JSON data files being placed in the $HTML_ROOT/json directory. 
The Highcharts for WeeWX installation can be further customized (eg units of
measure, file locations etc) by referring to the Highcharts for WeeWX wiki.
