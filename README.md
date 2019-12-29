# Highcharts for WeeWX extension #

## Description ##

The *Highcharts for WeeWX* extension provides a JSON data feed to support weekly and yearly observation plots using Highcharts. A sample HTML page and the JavaScript necessary to render the Highcharts plots is also included in the [*Highcharts for weewx* repositry](https://github.com/gjr80/weewx-highcharts).

## Pre-Requisites ##

The *Highcharts for WeeWX* extension requires *WeeWX v4.0.0* or greater. The display of the *Highcharts for WeeWX* extension data on a web page using the included Javascript files requires the Highcharts *Highstock* charting tool and the *JQuery* JavaScript library.

## Installation ##

The preferred method to install the *Highcharts for WeeWX* extension is to use the WeeWX *wee\_extension* utility. To install the *Highcharts for WeeWX* extension using the WeeWX *wee\_extension* utility:

**Note:** Symbolic names are used below to refer to some file location on the WeeWX system. These symbolic names allow a common name to be used to refer to a directory that may be different from system to system. The following symbolic names are used below:

*$DOWNLOAD_ROOT*. The path to the directory containing the downloaded *Highcharts for WeeWX* extension.

*$HTML_ROOT*. The path to the directory where WeeWX generated reports are saved. This directory is normally set in the *[StdReport]* section of *weewx.conf*. Refer to [where to find things](http://weewx.com/docs/usersguide.htm#Where_to_find_things) in the WeeWX [User's Guide](http://weewx.com/docs/usersguide.htm) for further information.

*$SKIN_ROOT*. The path to the directory where WeeWX skin directories are located. This directory is normally set in the *[StdReport]* section of *weewx.conf*.Refer to [where to find things](http://weewx.com/docs/usersguide.htm#Where_to_find_things) in the WeeWX [User's Guide](http://weewx.com/docs/usersguide.htm) for further information.

1.  Download the latest *Highcharts for WeeWX* extension from the *Highcharts for WeeWX* [releases page](https://github.com/gjr80/weewx-highcharts/releases) into a directory accessible from the WeeWX machine.

	    $ wget -P $DOWNLOAD_ROOT https://github.com/gjr80/weewx-highcharts/releases/download/v1.0.0/hfw-1.0.0.tar.gz

2.  Stop WeeWX:

	    $ sudo /etc/init.d/weewx stop

	or

	    $ sudo service weewx stop
	    
    or
    
        $ sudo systemctl stop weewx

3.  Install the *Highcharts for WeeWX* extension downloaded at step 1 using the *wee_extension* utility:

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

This will result in the *Highcharts for WeeWX* JSON data files being generated during each report generation cycle. A default installation will result in the generated JSON data files being placed in the *$HTML_ROOT/json* directory. The *Highcharts for WeeWX* installation can be further customized (eg units of measure, file locations etc) by referring to the *Highcharts for WeeWX* wiki.

## Support ###

General support issues may be raised in the Google Groups [weewx-user forum](https://groups.google.com/group/weewx-user "Google Groups weewx-user forum"). Specific bugs in the *Highcharts for WeeWX* extension code should be the subject of a new issue raised via the [Issues Page](https://github.com/gjr80/weewx-highcharts/issues "Highcharts for WeeWX extension Issues").
 
## Licensing ##

The *Highcharts for WeeWX* extension is licensed under the [GNU Public License v3](https://github.com/gjr80/weewx-highcharts/blob/master/LICENSE "Highcharts for WeeWX extension License").
