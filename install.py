"""
This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
PARTICULAR PURPOSE.  See the GNU General Public License for more details.

                     Installer for Highcharts for WeeWX

 Version: 1.0.0a1                                       Date: 29 December 2019

 Revision History
    29 December 2019    v1.0.0
         - now supports WeeWX 4.0.0 under python 2 or python 3
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

# TODO. Fix before release
REQUIRED_VERSION = "4.0.0b5"
HFW_VERSION = "1.0.0"

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
                                'group_rainrate': 'mm_per_hour',
                                'group_speed': 'km_per_hour',
                                'group_speed2': 'km_per_hour2',
                                'group_temperature': 'degree_C'
                            },
                            'StringFormats': {
                                'centibar': '%.0f',
                                'cm': '%.2f',
                                'cm_per_hour': '%.2f',
                                'degree_C': '%.1f',
                                'degree_F': '%.1f',
                                'degree_compass': '%.0f',
                                'foot': '%.0f',
                                'hPa': '%.1f',
                                'inHg': '%.3f',
                                'inch': '%.2f',
                                'inch_per_hour': '%.2f',
                                'km_per_hour': '%.0f',
                                'km_per_hour2': '%.1f',
                                'knot': '%.0f',
                                'knot2': '%.1f',
                                'mbar': '%.1f',
                                'meter': '%.0f',
                                'meter_per_second': '%.1f',
                                'meter_per_second2': '%.1f',
                                'mile_per_hour': '%.0f',
                                'mile_per_hour2': '%.1f',
                                'mm': '%.1f',
                                'mmHg': '%.1f',
                                'mm_per_hour': '%.1f',
                                'percent': '%.0f',
                                'uv_index': '%.1f',
                                'volt': '%.1f',
                                'watt_per_meter_squared': '%.0f',
                                'NONE': 'N/A'
                            },
                            'Labels': {
                                'centibar': 'cb',
                                'cm': 'cm',
                                'cm_per_hour': 'cm/hr',
                                'degree_C': '\u00B0 C',
                                'degree_F': '\u00B0 F',
                                'degree_compass': '\u00B0',
                                'foot': 'feet',
                                'hPa': 'hPa',
                                'inHg': 'inHg',
                                'inch': 'in',
                                'inch_per_hour': 'in/hr',
                                'km_per_hour': 'km/hr',
                                'km_per_hour2': 'km/hr',
                                'knot': 'knots',
                                'knot2': 'knots',
                                'mbar': 'mbar',
                                'meter': 'meters',
                                'meter_per_second': 'm/s',
                                'meter_per_second2': 'm/s',
                                'mile_per_hour': 'mph',
                                'mile_per_hour2': 'mph',
                                'mm': 'mm',
                                'mmHg': 'mmHg',
                                'mm_per_hour': 'mm/hr',
                                'percent': '%',
                                'uv_index': 'Index',
                                'volt': 'V',
                                'watt_per_meter_squared': 'W/m\u00B2',
                                'NONE':      ''
                            }
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
                                'legend_title': 'True',
                                'band_percent': 'True',
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
            files=[('bin/user', ['bin/user/highcharts.py',
                                 'bin/user/highchartsSearchX.py'
                                ]
                   ),
                   ('skins/Highcharts', ['skins/Highcharts/json/week.json.tmpl',
                                         'skins/Highcharts/json/year.json.tmpl',
                                         'skins/Highcharts/skin.conf'
                                        ]
                   )
            ]
        )
