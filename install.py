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
#                     Installer for Highcharts for weewx
#
# Version: 0.1.0                                  Date: 22 November 2016
#
# Revision History
#  21 November 2016     v0.1.0
#       - initial implementation
#

import weewx

from distutils.version import StrictVersion
from setup import ExtensionInstaller

REQUIRED_VERSION = "3.4.0"
HFW_VERSION = "0.1.0"

def loader():
    return HfwInstaller()

class HfwInstaller(ExtensionInstaller):
    def __init__(self):
        if StrictVersion(weewx.__version__) < StrictVersion(REQUIRED_VERSION):
            msg = "%s requires weewx %s or greater, found %s" % ('Hfw ' + HFW_VERSION, 
                                                                 REQUIRED_VERSION, 
                                                                 weewx.__version__)
            raise weewx.UnsupportedFeature(msg)
        super(HfwInstaller, self).__init__(
            version=HFW_VERSION,
            name='Hfw',
            description='weewx support for plotting observationa data using Highcharts.',
            author="Gary Roderick",
            author_email="gjroderick@gmail.com",
            config={
                'StdReport': {
                    'Highcharts': {
                        'skin': 'Highcharts',
                        'CheetahGenerator': {
                            'HTML_ROOT': 'json'
                        },
                        'CopyGenerator': {
                            'HTML_ROOT': ''
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
                        },
                    }
                }
            },
            files=[('bin/user', ['bin/user/highcharts.py',
                                 'bin/user/highchartsSearchX.py'
                                ]
                   ),
                   ('skins/Highcharts', ['skins/Highcharts/week.json.tmpl',
                                         'skins/Highcharts/year.json.tmpl',
                                         'skins/Highcharts/skin.conf',
                                         'skins/Highcharts/scripts/saratogaplots.js',
                                         'skins/Highcharts/scripts/weewxtheme.js'
                                        ]
                   )
            ]
        )
