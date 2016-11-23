The Highcharts for weewx extension provides graphical plots of weewx 
observational data using the Highcharts charting tool.

Highcharts for weewx consists of a skin, a number of Search List 
Extensions (SLE) and supporting javascript.

Pre-Requisites

Highchart for weewx requires Weewx v3.4.0 or greater.

Installation Instructions

Installation using the wee_extension utility 

Note:   In the following code snippets the symbolic name *$DOWNLOAD_ROOT* is 
        the path to the directory containing the downloaded Highcharts for 
        weewx extension.

1.  Download the Highcharts for weewx extension from the Highcharts for weewx 
releases page (https://github.com/gjr80/weewx-highcharts/releases) into a 
directory accessible from the weewx machine.

    wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-highcharts/releases/hfw-0.1.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Highcharts for 
    weewx extension is to be downloaded.  

2.  Stop weewx:

    sudo /etc/init.d/weewx stop

	or

    sudo service weewx stop

3.  Install the Highcharts for weewx extension downloaded at step 1 using the 
weewx wee_extension* utility:

    wee_extension --install=$DOWNLOAD_ROOT/hfw-0.1.0.tar.gz

    This will result in output similar to the following:

        Request to install '/var/tmp/hfw-0.1.0.tar.gz'
        Extracting from tar archive /var/tmp/hfw-0.1.0.tar.gz
        Saving installer file to /home/weewx/bin/user/installer/Hfw
        Saved configuration dictionary. Backup copy at /home/weewx/weewx.conf.20161123124410
        Finished installing extension '/var/tmp/hfw-0.1.0.tar.gz'

4. Start weewx:

    sudo /etc/init.d/weewx start

	or

    sudo service weewx start

This will result in the Highcharts for weewx JSON data files being generated 
during each report generation cycle. The Highcharts for weewx installation can 
be further customized (eg units of measure, file locations etc) by referring 
to the Highcharts for weewx wiki.

Manual installation

1.  Download the Highcharts for weewx extension from the Highcharts for weewx 
releases page (https://github.com/gjr80/weewx-highcharts/releases) into a 
directory accessible from the weewx machine.

    wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-highcharts/releases/hfw-0.1.0.tar.gz

	where $DOWNLOAD_ROOT is the path to the directory where the Highcharts for 
    weewx extension is to be downloaded.  

2.  Unpack the extension as follows:

    tar xvfz hfw-0.1.0.tar.gz

3.  Copy files from within the resulting folder as follows:

    cp highcharts-weewx/bin/user/*.py $BIN_ROOT/user
    cp -R highcharts-weewx/skins/Highcharts $SKIN_ROOT
    
	replacing the symbolic names $BIN_ROOT and $SKIN_ROOT with the nominal 
    locations for your installation.

4.  Edit weewx.conf:

    vi weewx.conf

5.  In weewx.conf, modify the [StdReport] section by adding the following 
sub-section:

    [[Highcharts]]
        skin = Highcharts
        [[[Units]]]
            [[[[Groups]]]]
                group_altitude = meter
                group_speed2 = km_per_hour2
                group_pressure = hPa
                group_rain = mm
                group_rainrate = mm_per_hour
                group_temperature = degree_C
                group_degree_day = degree_C_day
                group_speed = km_per_hour
        [[[CopyGenerator]]]
            HTML_ROOT = public_html/
        [[[CheetahGenerator]]]
            HTML_ROOT = public_html/json

6. Start weewx:

    sudo /etc/init.d/weewx start

	or

    sudo service weewx start

This will result in the Highcharts for weewx JSON data files being generated 
during each report generation cycle. The Highcharts for weewx installation can 
be further customized (eg units of measure, file locations etc) by referring 
to the Highcharts for weewx wiki.
