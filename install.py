"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                     Installer for Highcharts for WeeWX

 Version: 0.4.0                                         Date: xx xxxxx 2021

 Revision History
    xx xxxxx 2021       v0.4.0
        - changed required WeeWX version number
        - removed unused Label, StringFormat and group overrides
    17 March 2021       v0.3.2
        - version number change only
    16 October 2020
        - version number change only
    20 September 2020   v0.3.0
         - now supports WeeWX 4.0.0 under python 2 or python 3
         - removed highcharts.py from install file list
         - renamed highchartsSearchX.py to highchartssearchlist.py
    4 September 2018    v0.2.2
        - version number change only
    16 May 2017         v0.2.1
        - fixed errors in various 'Extras' settings (error previously hidden
          due to [[Windrose]]/[[WindRose]] issue)
    4 May 2017          v0.2.0
        - version number change only
    21 November 2016    v0.1.0
        - initial implementation
"""

import weewx

from distutils.version import StrictVersion
from setup import ExtensionInstaller

REQUIRED_VERSION = "4.5.0a1"
HFW_VERSION = "0.4.0"

def loader():
    return HfwInstaller()

class HfwInstaller(ExtensionInstaller):
    def __init__(self):
        if StrictVersion(weewx.__version__) < StrictVersion(REQUIRED_VERSION):
            msg = "%s requires WeeWX %s or greater, found %s" % ('Hfw ' + HFW_VERSION,
                                                                 REQUIRED_VERSION,
                                                                 weewx.__version__)
            raise weewx.UnsupportedFeature(msg)
        super(HfwInstaller, self).__init__(
            version=HFW_VERSION,
            name='Hfw',
            description='WeeWX support for plotting observational data using Highcharts.',
            author="Gary Roderick",
            author_email="gjroderick<@>gmail.com",
            config={
                'StdReport': {
                    'Highcharts': {
                        'skin': 'Highcharts',
                        'CheetahGenerator': {
                            'ToDate': {
                                'YearJSON': {
                                    'stale_age': '3600'
                                }
                            }
                        },
                        'Units': {
                            'Groups': {
                                'group_altitude': 'meter',
                                'group_degree_day': 'degree_C_day',
                                'group_pressure': 'hPa',
                                'group_rain': 'mm',
                                'group_speed': 'km_per_hour',
                                'group_temperature': 'degree_C'
                            },
                        },
                        'Extras': {
                            'MinRange': {
                                'outTemp': [10, 'degree_C'],
                                'windchill': [10, 'degree_C'],
                                'barometer': [20, 'hPa'],
                                'windSpeed': '10',
                                'rain': [5, 'mm'],
                                'radiation': '500',
                                'UV': '16'
                            },
                            'WindRose': {
                                'title': 'Wind Rose',
                                'source': 'windSpeed',
                                'period': [86400, 604800, 'month', 'year'],
                                'aggregate_type': '',
                                'aggregate_interval': '',
                                'petals': '16',
                                'petal_colors': ['aqua', '0x0099FF', '0x0033FF', '0x009900', '0x00CC00', '0x33FF33', '0xCCFF00'],
                                'speedfactor': ['0.0', '0.1', '0.2', '0.3', '0.5', '0.7', '1.0'],
                                'show_legend_title': 'True',
                                'show_band_percent': 'True',
                                'bullseye_percent': 'True',
                                'precision': '1',
                                'bullseye_size': '20',
                                'bullseye_color': '0xFFFACD',
                                'calm_limit': '0.5'
                            }
                        }
                    }
                }
            },
            files=[('bin/user', ['bin/user/highchartssearchlist.py']
                    ),
                   ('skins/Highcharts', ['skins/Highcharts/json/week.json.tmpl',
                                         'skins/Highcharts/json/year.json.tmpl',
                                         'skins/Highcharts/skin.conf'
                                         ]
                    )
                   ]
        )
