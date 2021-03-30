/*****************************************************************************
plots.js

Javascript to setup, configure and display Highcharts plots of WeeWX weather
data.

Based on Highcharts documentation and examples, and a lot of Stackoverflow
Q&As.

Key points:
    -   displays week and year plots
    -   week plot displays 7+ days of archive data in a Highstocks spline plot
        with a zoomable window (default 24 hours)
    -   year plot displays last 12 months of daily summary data in a
        Highstocks columnrange plot with a zoomable window (default 1 month).
        Plots show day min/max range in a column and day averages in one or
        more spline plots.
    -   requires JSON data feed from Highcharts for WeeWX extension
    -   requires Highstocks
    -   units of measure are set in Highcharts for WeeWX supplied through the
        JSON data files

To install/setup:
    -   install Highcharts for WeeWX extension and confirm proper generation
        of week and year JSON data files
    -   arrange for JSON data files to be transferred to your web server
        either by WeeWX or some other arrangement
    -   copy saratogaplots.js and weewxtheme.js to a suitable directory on your
        web server (the default directory used throughout is
        saratoga/scripts/js - remember this is relative to the root directory
        of your webserver so it could be /var/www/html/saratoga/scripts/js)
    -   if using the supplied wxgraphs2.php with the Saratoga templates then
        copy the file to the Saratoga templates folder on your web server
    -   if using the demo file, graphs.html, then copy the file to a suitable
        directory on your web server
    -   irrespective of what file you are using to display the plots make sure
        that any paths to the scripts in any <SCRIPT> tags reflect you setup
    -   check/set the paths to the JSON data files using the week_json and
        year_json variable below - remember the path is relative to your web
        server root
    -   open the wxgraphs2.php or graphs.html in your web browser
    -   once the default setup is working you may customise the display by
        changing the plot settings in this file and weewxtheme.js

Version: 0.7.1                                      Date: 30 March 2021

Revision History
    30 March 2021       v0.7.1
        -   fixed incorrect number of decimal places appearing in humidity and
            wind direction year plot tooltip values
    21 March 2021       v0.7.0
        -   div ids and json path/file name now specified in variables rather
            than direct in code
        -   reworked y axis titles such that they are obtained from the
            incoming json data
    20 September 2020   v0.6.0
        - version number change only
    4 September 2018    v0.5.2
        - version number change only
    4 May 2017          v0.5.0
        - ignores appTemp and insolation plots if no relevant data is available
    10 May 2016         v0.4.0
        -   fixed issue whereby x axis timescale was displayed using the local
            time of the system viewing the plot rather than the the weather
            station local time
        - revised comments
    17 March 2015       v0.3.0
        -   completely rewritten/restructured to plot week and year plots only
            rather than original day, week, month and year plots
    17 January 2015     v0.2.0
        -   tweaked tooltips
        -   added theoretical max solar radiation plot to solar radiation plot
    sometime in 2014    v0.1.0
        -   initial implementation

*****************************************************************************/

/*****************************************************************************

Set names of div ids to which the various plots will be rendered

*****************************************************************************/
var plotIds = {
    temperature: 'temperatureplot',
    windChill: 'windchillplot',
    humidity: 'humidityplot',
    barometer: 'barometerplot',
    wind: 'windplot',
    windDir: 'winddirplot',
    rain: 'rainplot',
    radiation:  'radiationplot',
    uv: 'uvplot'
};

/*****************************************************************************

Set paths/names of our week and year JSON data files

Paths are relative to the web server root

*****************************************************************************/
var week_json = '/weather_data/json/week.json';
var year_json = '/weather_data/json/year.json';

/*****************************************************************************

Set default plot options

These are common plot options across all plots. Change them by all means but
make sure you know what you are doing. The Highcharts API documentation is
your reference.

*****************************************************************************/
var commonOptions = {
    chart: {
        plotBackgroundColor: {
            linearGradient: { x1: 0, y1: 0, x2: 1, y2: 1 },
            stops: [
                [0, '#FCFFC5'],
                [1, '#E0E0FF']
            ]
        },
        spacing: [15, 20, 10, 0],
        zoomType: 'x'
    },
    legend: {
        enabled: true
    },
    plotOptions: {
        area: {
            lineWidth: 1,
            marker: {
                enabled: false,
                radius: 2,
                symbol: 'circle'
            },
            fillOpacity: 0.05
        },
        column: {
            dataGrouping: {
                dateTimeLabelFormats: {
                    hour: ['%e %B %Y hour to %H:%M', '%e %B %Y %H:%M', '-%H:%M'],
                    day: ['%e %B %Y', '%e %B', '-%e %B %Y'],
                    week: ['Week starting %e %B %Y', '%e %B', '-%e %B %Y'],
                    month: ['%B %Y', '%B', '-%B %Y'],
                    year: ['%Y', '%Y', '-%Y']
                },
                enabled: true,
                forced: false,
                units: [[
                    'hour',
                        [1]
                    ], [
                    'day',
                        [1]
                    ], [
                    'week',
                        [1]
                    ]
                ]
            },
        },
        columnrange: {
            dataGrouping: {
                dateTimeLabelFormats: {
                    hour: ['%e %B %Y hour to %H:%M', '%e %b %Y %H:%M', '-%H:%M'],
                    day: ['%e %B %Y', '%e %B', '-%e %B %Y'],
                    week: ['Week from %e %B %Y', '%e %B', '-%e %B %Y'],
                    month: ['%B %Y', '%B', '-%B %Y'],
                    year: ['%Y', '%Y', '-%Y']
                },
                enabled: true,
                forced: true,
                units: [[
                    'day',
                        [1]
                    ], [
                    'week',
                        [1]
                    ]
                ]
            },
        },
        series: {
            states: {
                hover: {
                    halo: {
                        size: 0,
                    }
                }
            }
        },
        scatter: {
            dataGrouping: {
                dateTimeLabelFormats: {
                    hour: ['%e %B %Y hour to %H:%M', '%e %b %Y %H:%M', '-%H:%M'],
                    day: ['%e %b %Y', '%e %b', '-%e %b %Y'],
                    week: ['Week from %e %b %Y', '%e %b', '-%e %b %Y'],
                    month: ['%B %Y', '%B', '-%B %Y'],
                    year: ['%Y', '%Y', '-%Y']
                },
                enabled: true,
                forced: true,
                units: [[
                    'hour',
                        [1]
                    ], [
                    'day',
                        [1]
                    ], [
                    'week',
                        [1]
                    ]
                ]
            },
            marker: {
                radius: 1,
                symbol: 'circle'
            },
            shadow: false,
            states: {
                hover: {
                    halo: false,
                }
            }
        },
        spline: {
            dataGrouping: {
                dateTimeLabelFormats: {
                    hour: ['%e %B %Y hour to %H:%M', '%e %b %Y %H:%M', '-%H:%M'],
                    day: ['%e %b %Y', '%e %b', '-%e %b %Y'],
                    week: ['Week from %e %b %Y', '%e %b', '-%e %b %Y'],
                    month: ['%B %Y', '%B', '-%B %Y'],
                    year: ['%Y', '%Y', '-%Y']
                },
                enabled: true,
                forced: true,
                units: [[
                    'hour',
                        [1]
                    ], [
                    'day',
                        [1]
                    ], [
                    'week',
                        [1]
                    ]
                ]
            },
            lineWidth: 1,
            marker: {
                radius: 1,
                enabled: false,
                symbol: 'circle'
            },
            shadow: false,
            states: {
                hover: {
                    lineWidth: 1,
                    lineWidthPlus: 1
                }
            }
        },
    },
    rangeSelector: {
        buttonSpacing: 0,
    },
    series: [{
    }],
    tooltip: {
        crosshairs: true,
        enabled: true,
        dateTimeLabelFormats: {
            minute: '%e %B %Y %H:%M',
            hour: '%e %B %Y %H:%M',
            day: '%A %e %B %Y'
        },
        shared: true,
        // need to set valueSuffix so we can set it later if needed
        valueSuffix: ''
    },
    xAxis: {
        dateTimeLabelFormats: {
            day: '%e %b',
            week: '%e %b',
            month: '%b %y',
        },
        lineColor: '#555',
        lineWidth: 1,
        minorGridLineWidth: 0,
        minorTickColor: '#555',
        minorTickLength: 2,
        minorTickPosition: 'inside',
        minorTickWidth: 1,
        tickColor: '#555',
        tickLength: 4,
        tickPosition: 'inside',
        tickWidth: 1,
        title: {
            style: {
                font: 'bold 12px Lucida Grande, Lucida Sans Unicode, Verdana, Arial, Helvetica, sans-serif'
            }
        },
        type: 'datetime',
    },
    yAxis: {
        endOnTick: true,
        labels: {
            x: -8,
            y: 3
        },
        lineColor: '#555',
        lineWidth: 1,
        minorGridLineWidth: 0,
        minorTickColor: '#555',
        minorTickLength: 2,
        minorTickPosition: 'inside',
        minorTickWidth: 1,
        opposite: false,
        showLastLabel: true,
        startOnTick: true,
        tickColor: '#555',
        tickLength: 4,
        tickPosition: 'inside',
        tickWidth: 1,
        title: {
            text: ''
        }
    }
};


function clone(obj) {
/*****************************************************************************

Function to clone an object

As found at http://stackoverflow.com/questions/728360/most-elegant-way-to-clone-a-javascript-object

*****************************************************************************/
    var copy;
    // Handle the 3 simple types, and null or undefined
    if (null === obj || 'object' !== typeof obj) {
        return obj;
    }

    // Handle Date
    if (obj instanceof Date) {
        copy = new Date();
        copy.setTime(obj.getTime());
        return copy;
    }

    // Handle Array
    if (obj instanceof Array) {
        copy = [];
        for (var i = 0, len = obj.length; i < len; i++) {
            copy[i] = clone(obj[i]);
        }
        return copy;
    }

    // Handle Object
    if (obj instanceof Object) {
        copy = {};
        for (var attr in obj) {
            if (obj.hasOwnProperty(attr)) {
                copy[attr] = clone(obj[attr]);
            }
        }
        return copy;
    }

    throw new Error('Unable to copy obj! Its type isn\'t supported.');
};

function addWeekOptions(obj) {
/*****************************************************************************

Function to add/set various plot options specific to the 'week' plot.

*****************************************************************************/
    // set range selector buttons
    obj.rangeSelector.buttons = [{
        type: 'hour',
        count: 1,
        text: '1h'
    }, {
        type: 'hour',
        count: 6,
        text: '6h'
    }, {
        type: 'hour',
        count: 12,
        text: '12h'
    }, {
        type: 'hour',
        count: 24,
        text: '24h'
    }, {
        type: 'hour',
        count: 36,
        text: '36h'
    }, {
        type: 'all',
        text: '7d'
    }],
    // set default range selector button
    obj.rangeSelector.selected = 3;
    // turn off data grouping for each plot type
    obj.plotOptions.column.dataGrouping.enabled = false;
    obj.plotOptions.spline.dataGrouping.enabled = false;
    obj.plotOptions.scatter.dataGrouping.enabled = false;
    return obj
};


function addYearOptions(obj) {
/*****************************************************************************

Function to add/set various plot options specific to the 'year' plot.

*****************************************************************************/
    // set range selector buttons
    obj.rangeSelector.buttons = [{
        type: 'day',
        count: 1,
        text: '1d'
    }, {
        type: 'week',
        count: 1,
        text: '1w'
    }, {
        type: 'month',
        count: 1,
        text: '1m'
    }, {
        type: 'month',
        count: 6,
        text: '6m'
    }, {
        type: 'all',
        text: '1y'
    }],
    // set default range selector button
    obj.rangeSelector.selected = 2;
    // turn off data grouping for each plot type
    obj.plotOptions.spline.dataGrouping.enabled = false;
    obj.plotOptions.column.dataGrouping.enabled = false;
    obj.plotOptions.columnrange.dataGrouping.enabled = false;
    return obj
};

function setTemp(obj) {
/*****************************************************************************

Function to add/set various plot options specific to temperature spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.temperature;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            lineColor: '#B44242'
        },
    },
    obj.title = {
        text: 'Temperature'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    return obj
};

function setTempStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline temperature plots

*****************************************************************************/
    obj = setTemp(obj);
    obj.chart.type = 'columnrange';
    obj.series = [{
        color: '#F0B0B0',
        name: 'Temperature Range',
        type: 'columnrange',
        visible: true
    }, {
        color: '#B44242',
        name: 'Average Temperature',
        type: 'spline',
        visible: true
    }];
    obj.tooltip.valueDecimals = 1;
    return obj
};

function setWindchill(obj) {
/*****************************************************************************

Function to add/set various plot options specific to windchill spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.windChill;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            color: '#C07777',
            lineColor: '#047B04'
        },
    },
    obj.title = {
        text: 'Apparent Temperature/Wind Chill/Heat Index'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    return obj
};

function setWindchillStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline windchill plots

*****************************************************************************/
    obj = setWindchill(obj);
    obj.chart.type = 'columnrange';
    obj.series = [{
        color: '#A6D3A6',
        name: 'Apparent Temperature Range',
        type: 'columnrange',
        visible: true
    }, {
        color: '#047B04',
        name: 'Average Apparent Temperature',
        type: 'spline',
        visible: true
    }, {
        name: 'Average Wind Chill',
        type: 'spline',
        visible: true
    }, {
        name: 'Average Heat Index',
        type: 'spline',
        visible: true
    }];
    obj.tooltip.valueDecimals = 1;
    return obj
};

function setHumidity(obj) {
/*****************************************************************************

Function to add/set various plot options specific to humidity spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.humidity;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            lineColor: '#4242B4'
        },
    },
    obj.plotOptions.series = {
        color: '#4242B4'
    };
    obj.title = {
        text: 'Humidity'
    };
    obj.tooltip.valueSuffix = '%';
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.max = 100;
    obj.yAxis.min = 0;
    obj.yAxis.minorTickInterval = 5;
    obj.yAxis.tickInterval = 25;
    return obj
};

function setHumidityStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
humidity spline plots

*****************************************************************************/
    obj = setHumidity(obj);
    obj.chart.type = 'columnrange';
    obj.navigator = {
        series: {
            color: '#C07777',
            lineColor: '#B06060'
        },
    },
    obj.series = [{
        color: '#8EC3D3',
        name: 'Humidity Range',
        type: 'columnrange',
        visible: true
    }, {
        color: '#4242B4',
        name: 'Average Humidity',
        type: 'spline',
        visible: true
    }];
    obj.tooltip.valueDecimals = 0;
    return obj
};

function setBarometer(obj) {
/*****************************************************************************

Function to add/set various plot options specific to barometric pressure
spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.barometer;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            lineColor: '#4242B4'
        },
    },
    obj.plotOptions.series = {
        color: '#4242B4'
    };
    obj.title = {
        text: 'Barometer'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    return obj
};

function setBarometerStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline barometric pressure plots

*****************************************************************************/
    obj = setBarometer(obj);
    obj.chart.type = 'columnrange';
    obj.navigator = {
        series: {
            color: '#C07777',
            lineColor: '#B06060'
        },
    },
    obj.series = [{
        color: '#8EC3D3',
        name: 'Barometeric Pressure Range',
        type: 'columnrange',
        visible: true
    }, {
        color: '#4242B4',
        name: 'Average Barometric Pressure',
        type: 'spline',
        visible: true
    }];
    obj.tooltip.valueDecimals = 1;
    return obj
};

function setWind(obj) {
/*****************************************************************************

Function to add/set various plot options specific to wind speed spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.wind;
    obj.chart.type = 'spline';
    obj.legend.reversed = true;
    obj.navigator = {
        series: {
            lineColor: '#439BB6'
        },
    },
    obj.title = {
        text: 'Wind/Gust Speed'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.min = 0;
    return obj
};

function setWindStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline wind speed plots

*****************************************************************************/
    obj = setWind(obj);
    obj.chart.type = 'spline';
    obj.series = [{
        name: 'Max Gust Speed',
        type: 'spline',
        color: '#B44242'
    },{
        name: 'Max 5 Minute Average Wind Speed',
        type: 'spline',
        color: '#4242B4'
    }, {
        name: 'Day Average Wind Speed',
        type: 'spline',
        color: '#439BB6'
    }];
    obj.tooltip.valueDecimals = 1;
    return obj
};

function setWindDir(obj) {
/*****************************************************************************

Function to add/set various plot options specific to wind direction spline
plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.windDir;
    obj.chart.type = 'scatter';
    obj.navigator = {
        series: {
            lineColor: '#439BB6'
        },
    },
    obj.title = {
        text: 'Wind Direction'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.max = 360;
    obj.yAxis.min = 0;
    obj.yAxis.tickInterval = 90;
    obj.plotOptions.series = {
        marker: {
            radius: 2
        },
        color: '#4242B4'
    };
    obj.series.marker = {
        lineWidth: 0,
        lineColor: null,
        radius: 10
    };
    obj.tooltip.headerFormat = '<span style="font-size: 10px">{point.key}</span><br/>'
    obj.tooltip.pointFormat = '<span style="color: {series.color}">●</span> {series.name}: <b>{point.y}</b>'
    obj.tooltip.xDateFormat = '%e %B %Y %H:%M';
    return obj
};

function setWindDirStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline wind direction plots

*****************************************************************************/
    obj = setWindDir(obj);
    obj.navigator = {
        series: {
            lineColor: '#439BB6'
        },
    };
    obj.series = [{
        name: 'Vector Average Wind Direction',
        color: '#439BB6'
    }];
    obj.tooltip.valueDecimals = 0;
    obj.tooltip.xDateFormat = '%e %B %Y';
    return obj
};

function setRain(obj) {
/*****************************************************************************

Function to add/set various plot options specific to rainfall plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.rain;
    obj.chart.type = 'column';
    obj.plotOptions.column.dataGrouping.enabled = true;
    obj.title = {
        text: 'Rainfall'
    };
    obj.xAxis.minRange = 3600000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.min = 0;
    obj.plotOptions.column.color = '#72B2C4';
    obj.plotOptions.column.borderWidth = 0;
    obj.plotOptions.column.marker = {
        enabled: false,
    };
    obj.plotOptions.series.pointPadding = 0;
    obj.plotOptions.series.groupPadding = 0;
    obj.plotOptions.series.borderWidth = 0;
    obj.tooltip.headerFormat = '<span style="font-size: 10px">{point.key}</span><br/>';
    obj.tooltip.pointFormat = '<tr><td><span style="color: {series.color}">{series.name}</span>: </td>' + '<td style="text-align: right"><b>{point.y}</b></td></tr>';
    obj.tooltip.crosshairs = false;
    obj.tooltip.xDateFormat = '%e %B %Y hour to %H:%M';
    return obj
};

function setRainStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline rainfall plots

*****************************************************************************/
    obj = setRain(obj);
    obj.navigator = {
        enabled: true
    };
    obj.plotOptions.column.dataGrouping.dateTimeLabelFormats.hour = [
        '%e %B %Y', '%e %B %Y %H:%M', '-%H:%M'
    ];
    obj.plotOptions.column.dataGrouping.enabled = true;
    obj.series = [{
        name: 'Rainfall',
        type: 'column',
        color: '#439BB6'
    }];
    obj.title = {
        text: 'Rainfall'
    };
    obj.tooltip.valueDecimals = 1;
    obj.tooltip.xDateFormat = '%e %B %Y';

    obj.tooltip.headerFormat = '<span style="font-size: 10px">{point.key}</span><br/>';
    obj.tooltip.pointFormat = '<span style="color: {series.color}">●</span> {series.name}: <b>{point.y}</b>'
    obj.tooltip.crosshairs = false;
    obj.yAxis.allowDecimals = true;
    obj.yAxis.labels = {
        format: '{value:.0f}',
    };
    return obj
};

function setRadiation(obj) {
/*****************************************************************************

Function to add/set various plot options specific to solar radiation spline
plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.radiation;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            lineColor: '#B44242'
        },
    },
    obj.title = {
        text: 'Solar Radiation'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.min = 0;
    return obj
};

function setRadiationStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to spline solar radiation
plots

*****************************************************************************/
    obj = setRadiation(obj);
    obj.chart.type = 'column';
    obj.series = [{
        name: 'Maximum Solar Radiation',
        type: 'spline',
        color: '#F0B0B0',
    }, {
        name: 'Average Solar Radiation',
        type: 'spline',
        color: '#B44242',
    }];
    return obj
};

function setUv(obj) {
/*****************************************************************************

Function to add/set various plot options specific to UV index spline plots

*****************************************************************************/
    obj.chart.renderTo = plotIds.uv;
    obj.chart.type = 'spline';
    obj.navigator = {
        series: {
            lineColor: '#9933FF'
        },
    },
    obj.plotOptions.spline.color = '#9933FF';
    obj.title = {
        text: 'UV Index'
    };
    obj.xAxis.minRange = 900000;
    obj.xAxis.minTickInterval = 900000;
    obj.yAxis.max = 20;
    obj.yAxis.min = 0;
    obj.yAxis.minorTickInterval = 1;
    obj.yAxis.tickInterval = 4;
    return obj
};

function setUvStock(obj) {
/*****************************************************************************

Function to add/set various plot options specific to combined columnrange
spline UV index plots

*****************************************************************************/
    obj = setUv(obj);
    obj.chart.type = 'column';
    obj.series = [{
        name: 'Maximum UV Index',
        type: 'spline',
        color: '#E0C2FF',
    }, {
        name: 'Average UV Index',
        type: 'spline',
        color: '#9933FF',
    }];
    obj.tooltip.valueDecimals = 1;
    return obj
};

function weekly () {
/*****************************************************************************

Function to add/set various plot options and then plot each week plot

*****************************************************************************/
    // gather all fixed plot options for each plot
    var optionsTemp = clone(commonOptions);
    optionsTemp = addWeekOptions(optionsTemp);
    optionsTemp = setTemp(optionsTemp);
    var optionsWindchill = clone(commonOptions);
    optionsWindchill = addWeekOptions(optionsWindchill);
    optionsWindchill = setWindchill(optionsWindchill);
    var optionsHumidity = clone(commonOptions);
    optionsHumidity = addWeekOptions(optionsHumidity);
    optionsHumidity = setHumidity(optionsHumidity);
    var optionsBarometer = clone(commonOptions);
    optionsBarometer = addWeekOptions(optionsBarometer);
    optionsBarometer = setBarometer(optionsBarometer);
    var optionsWind = clone(commonOptions);
    optionsWind = addWeekOptions(optionsWind);
    optionsWind = setWind(optionsWind);
    var optionsWindDir = clone(commonOptions);
    optionsWindDir = addWeekOptions(optionsWindDir);
    optionsWindDir = setWindDir(optionsWindDir);
    var optionsRain = clone(commonOptions);
    optionsRain = addWeekOptions(optionsRain);
    optionsRain = setRain(optionsRain);
    optionsRain.plotOptions.column.dataGrouping.groupPixelWidth = 50;
    var optionsRadiation = clone(commonOptions);
    optionsRadiation = addWeekOptions(optionsRadiation);
    optionsRadiation = setRadiation(optionsRadiation);
    var optionsUv = clone(commonOptions);
    optionsUv = addWeekOptions(optionsUv);
    optionsUv = setUv(optionsUv);

    /*
    jquery function call to get the week JSON data, set plot series and
    other 'variable' plot options (eg units of measure) obtain from the JSON
    data file and then display the actual plots
    */
    $.getJSON(week_json, function(seriesData) {
        optionsTemp.series[0] = seriesData[0].temperatureplot.series.outTemp;
        optionsTemp.series[1] = seriesData[0].temperatureplot.series.dewpoint;
        if ("appTemp" in seriesData[0].temperatureplot.series) {
            optionsTemp.series[2] = seriesData[0].temperatureplot.series.appTemp;
        }
        optionsTemp.yAxis.minRange = seriesData[0].temperatureplot.minRange;
        optionsTemp.yAxis.title.text = "(" + seriesData[0].temperatureplot.units + ")";
        optionsTemp.tooltip.valueSuffix = seriesData[0].temperatureplot.units;
        optionsTemp.xAxis.min = seriesData[0].timespan.start;
        optionsTemp.xAxis.max = seriesData[0].timespan.stop;
        optionsWindchill.series[1] = seriesData[0].windchillplot.series.windchill;
        optionsWindchill.series[0] = seriesData[0].windchillplot.series.heatindex;
        if ("appTemp" in seriesData[0].temperatureplot.series) {
            optionsWindchill.series[2] = seriesData[0].windchillplot.series.appTemp;
        }
        optionsWindchill.yAxis.minRange = seriesData[0].windchillplot.minRange;
        optionsWindchill.yAxis.title.text = "(" + seriesData[0].windchillplot.units + ")";
        optionsWindchill.tooltip.valueSuffix = seriesData[0].windchillplot.units;
        optionsWindchill.xAxis.min = seriesData[0].timespan.start;
        optionsWindchill.xAxis.max = seriesData[0].timespan.stop;
        optionsHumidity.series[0] = seriesData[0].humidityplot.series.outHumidity;
        optionsHumidity.xAxis.min = seriesData[0].timespan.start;
        optionsHumidity.xAxis.max = seriesData[0].timespan.stop;
        optionsHumidity.yAxis.title.text = "(" + seriesData[0].humidityplot.units + ")";
        optionsBarometer.series[0] = seriesData[0].barometerplot.series.barometer;
        optionsBarometer.yAxis.minRange = seriesData[0].barometerplot.minRange;
        optionsBarometer.yAxis.title.text = "(" + seriesData[0].barometerplot.units + ")";
        optionsBarometer.tooltip.valueSuffix = seriesData[0].barometerplot.units;
        optionsBarometer.xAxis.min = seriesData[0].timespan.start;
        optionsBarometer.xAxis.max = seriesData[0].timespan.stop;
        optionsWind.series[0] = seriesData[0].windplot.series.windSpeed;
        optionsWind.series[1] = seriesData[0].windplot.series.windGust;
        optionsWind.yAxis.minRange = seriesData[0].windplot.minRange;
        optionsWind.yAxis.title.text = "(" + seriesData[0].windplot.units + ")";
        optionsWind.tooltip.valueSuffix = seriesData[0].windplot.units;
        optionsWind.xAxis.min = seriesData[0].timespan.start;
        optionsWind.xAxis.max = seriesData[0].timespan.stop;
        optionsWindDir.series[0] = seriesData[0].winddirplot.series.windDir;
        optionsWindDir.yAxis.title.text = "(" + seriesData[0].winddirplot.units + ")";
        optionsWindDir.xAxis.min = seriesData[0].timespan.start;
        optionsWindDir.xAxis.max = seriesData[0].timespan.stop;
        optionsWindDir.tooltip.valueSuffix = seriesData[0].winddirplot.units;
        optionsRain.series[0] = seriesData[0].rainplot.series.rain;
        optionsRain.yAxis.minRange = seriesData[0].rainplot.minRange;
        optionsRain.yAxis.title.text = "(" + seriesData[0].rainplot.units + ")";
        optionsRain.tooltip.valueSuffix = seriesData[0].rainplot.units;
        optionsRadiation.series[0] = seriesData[0].radiationplot.series.radiation;
        if ("insolation" in seriesData[0].radiationplot.series) {
            optionsRadiation.series[1] = seriesData[0].radiationplot.series.insolation;
            optionsRadiation.series[1].type = 'area';
        }
        optionsRadiation.yAxis.minRange = seriesData[0].radiationplot.minRange;
        optionsRadiation.yAxis.title.text = "(" + seriesData[0].radiationplot.units + ")";
        optionsRadiation.xAxis.min = seriesData[0].timespan.start;
        optionsRadiation.xAxis.max = seriesData[0].timespan.stop;
        optionsRadiation.tooltip.formatter = function() {
            var order = [], i, j, temp = [],
                points = this.points;

            for(i=0; i<points.length; i++)
            {
                j=0;
                if( order.length )
                {
                    while( points[order[j]] && points[order[j]].y > points[i].y )
                        j++;
                }
                temp = order.splice(0, j);
                temp.push(i);
                order = temp.concat(order);
            }
            console.log(order);
            temp = '<span style="font-size: 10px">' + Highcharts.dateFormat('%e %B %Y %H:%M',new Date(this.x)) + '</span><br/>';
            $(order).each(function(i,j){
                temp += '<span style="color: '+points[j].series.color+'">' +
                    points[j].series.name + ': ' + points[j].y + seriesData[0].radiationplot.units + '</span><br/>';
            });
            return temp;
        };
        optionsUv.series[0] = seriesData[0].uvplot.series.uv;
        optionsUv.yAxis.minRange = seriesData[0].uvplot.minRange;
        optionsUv.yAxis.title.text = "(" + seriesData[0].uvplot.units + ")";
        optionsUv.xAxis.min = seriesData[0].timespan.start;
        optionsUv.xAxis.max = seriesData[0].timespan.stop;
        Highcharts.setOptions({
            global: {
                timezoneOffset: -seriesData[0].utcoffset,
            },
        });
        // generate/display the actual plots
        if (document.getElementById(optionsTemp.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsTemp);
        };
        if (document.getElementById(optionsWindchill.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWindchill);
        };
        if (document.getElementById(optionsHumidity.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsHumidity);
        };
        if (document.getElementById(optionsBarometer.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsBarometer);
        };
        if (document.getElementById(optionsWind.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWind);
        };
        if (document.getElementById(optionsWindDir.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWindDir);
        };
        if (document.getElementById(optionsRain.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsRain);
        };
        if (document.getElementById(optionsRadiation.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsRadiation);
        };
        if (document.getElementById(optionsUv.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsUv);
        };
    });
};

function yearly () {
/*****************************************************************************

Function to add/set various plot options and then plot each year plot

*****************************************************************************/
    // gather all fixed plot options for each plot
    var optionsTemp = clone(commonOptions);
    optionsTemp = addYearOptions(optionsTemp);
    optionsTemp = setTempStock(optionsTemp);
    var optionsWindchill = clone(commonOptions);
    optionsWindchill = addYearOptions(optionsWindchill);
    optionsWindchill = setWindchillStock(optionsWindchill);
    var optionsHumidity = clone(commonOptions);
    optionsHumidity = addYearOptions(optionsHumidity);
    optionsHumidity = setHumidityStock(optionsHumidity);
    var optionsBarometer = clone(commonOptions);
    optionsBarometer = addYearOptions(optionsBarometer);
    optionsBarometer = setBarometerStock(optionsBarometer);
    var optionsWind = clone(commonOptions);
    optionsWind = addYearOptions(optionsWind);
    optionsWind = setWindStock(optionsWind);
    var optionsWindDir = clone(commonOptions);
    optionsWindDir = addYearOptions(optionsWindDir);
    optionsWindDir = setWindDirStock(optionsWindDir);
    var optionsRain = clone(commonOptions);
    optionsRain = addYearOptions(optionsRain);
    optionsRain = setRainStock(optionsRain);
    optionsRain.title.text = 'Rainfall';
    var optionsRadiation = clone(commonOptions);
    optionsRadiation = addYearOptions(optionsRadiation);
    optionsRadiation = setRadiationStock(optionsRadiation);
    var optionsUv = clone(commonOptions);
    optionsUv = addYearOptions(optionsUv);
    optionsUv = setUvStock(optionsUv);

    /*
    jquery function call to get the year JSON data, set plot series and
    other 'variable' plot options (eg units of measure) obtain from the JSON
    data file and then display the actual plots
    */
    $.getJSON(year_json, function(seriesData) {
        optionsTemp.series[0].data = seriesData[0].temperatureplot.outTempminmax;
        optionsTemp.series[1].data = seriesData[0].temperatureplot.outTempaverage;
        optionsTemp.yAxis.minRange = seriesData[0].temperatureplot.minRange;
        optionsTemp.yAxis.title.text = "(" + seriesData[0].temperatureplot.units + ")";
        optionsTemp.tooltip.valueSuffix = seriesData[0].temperatureplot.units;
        optionsTemp.xAxis.min = seriesData[0].timespan.start;
        optionsTemp.xAxis.max = seriesData[0].timespan.stop;
        optionsWindchill.series[3].data = seriesData[0].windchillplot.heatindexaverage;
        optionsWindchill.series[2].data = seriesData[0].windchillplot.windchillaverage;
        if ("appTempminmax" in seriesData[0].windchillplot) {
            optionsWindchill.series[0].data = seriesData[0].windchillplot.appTempminmax;
        } else {
            optionsWindchill.series.shift();
        }
        if ("appTempaverage" in seriesData[0].windchillplot) {
            optionsWindchill.series[1].data = seriesData[0].windchillplot.appTempaverage;
        } else {
            optionsWindchill.series.shift();
        }
        if ((!("appTempminmax" in seriesData[0].windchillplot)) && (!("appTempaverage" in seriesData[0].windchillplot))) {
            optionsWindchill.title.text = 'Wind Chill/Heat Index';
        }
        optionsWindchill.yAxis.minRange = seriesData[0].windchillplot.minRange;
        optionsWindchill.yAxis.title.text = "(" + seriesData[0].windchillplot.units + ")";
        optionsWindchill.tooltip.valueSuffix = seriesData[0].windchillplot.units;
        optionsWindchill.xAxis.min = seriesData[0].timespan.start;
        optionsWindchill.xAxis.max = seriesData[0].timespan.stop;
        optionsHumidity.series[0].data = seriesData[0].humidityplot.outHumidityminmax;
        optionsHumidity.series[1].data = seriesData[0].humidityplot.outHumidityaverage;
        optionsHumidity.yAxis.title.text = "(" + seriesData[0].humidityplot.units + ")";
        optionsHumidity.xAxis.min = seriesData[0].timespan.start;
        optionsHumidity.xAxis.max = seriesData[0].timespan.stop;
        optionsBarometer.series[0].data = seriesData[0].barometerplot.barometerminmax;
        optionsBarometer.series[1].data = seriesData[0].barometerplot.barometeraverage;
        optionsBarometer.yAxis.minRange = seriesData[0].barometerplot.minRange;
        optionsBarometer.yAxis.title.text = "(" + seriesData[0].barometerplot.units + ")";
        optionsBarometer.tooltip.valueSuffix = seriesData[0].barometerplot.units;
        optionsBarometer.xAxis.min = seriesData[0].timespan.start;
        optionsBarometer.xAxis.max = seriesData[0].timespan.stop;
        optionsWind.series[0].data = seriesData[0].windplot.windmax;
        optionsWind.series[1].data = seriesData[0].windplot.windAvmax;
        optionsWind.series[2].data = seriesData[0].windplot.windaverage;
        optionsWind.yAxis.minRange = seriesData[0].windplot.minRange;
        optionsWind.yAxis.title.text = "(" + seriesData[0].windplot.units + ")";
        optionsWind.tooltip.valueSuffix = seriesData[0].windplot.units;
        optionsWind.xAxis.min = seriesData[0].timespan.start;
        optionsWind.xAxis.max = seriesData[0].timespan.stop;
        optionsWindDir.series[0].data = seriesData[0].winddirplot.windDir;
        optionsWindDir.yAxis.minRange = seriesData[0].winddirplot.minRange;
        optionsWindDir.yAxis.title.text = "(" + seriesData[0].winddirplot.units + ")";
        optionsWindDir.xAxis.min = seriesData[0].timespan.start;
        optionsWindDir.xAxis.max = seriesData[0].timespan.stop;
        optionsRain.series[0].data = seriesData[0].rainplot.rainsum;
        optionsRain.yAxis.minRange = seriesData[0].rainplot.minRange;
        optionsRain.yAxis.title.text = "(" + seriesData[0].rainplot.units + ")";
        optionsRain.tooltip.valueSuffix = seriesData[0].rainplot.units;
        optionsRain.xAxis.min = seriesData[0].timespan.start;
        optionsRain.xAxis.max = seriesData[0].timespan.stop;
        optionsRadiation.series[0].data = seriesData[0].radiationplot.radiationmax;
        optionsRadiation.series[1].data = seriesData[0].radiationplot.radiationaverage;
        optionsRadiation.yAxis.minRange = seriesData[0].radiationplot.minRange;
        optionsRadiation.yAxis.title.text = "(" + seriesData[0].radiationplot.units + ")";
        optionsRadiation.xAxis.min = seriesData[0].timespan.start;
        optionsRadiation.xAxis.max = seriesData[0].timespan.stop;
        optionsRadiation.tooltip.formatter = function() {
            var order = [], i, j, temp = [],
                points = this.points;

            for(i=0; i<points.length; i++)
            {
                j=0;
                if( order.length )
                {
                    while( points[order[j]] && points[order[j]].y > points[i].y )
                        j++;
                }
                temp = order.splice(0, j);
                temp.push(i);
                order = temp.concat(order);
            }
            console.log(order);
            temp = '<span style="font-size: 10px">' + Highcharts.dateFormat('%e %B %Y %H:%M',new Date(this.x)) + '</span><br/>';
            $(order).each(function(i,j){
                temp += '<span style="color: '+points[j].series.color+'">' +
                    points[j].series.name + ': ' + points[j].y + seriesData[0].radiationplot.units + '</span><br/>';
            });
            return temp;
        };
        optionsUv.series[0].data = seriesData[0].uvplot.uvmax;
        optionsUv.series[1].data = seriesData[0].uvplot.uvaverage;
        optionsUv.yAxis.minRange = seriesData[0].uvplot.minRange;
        optionsUv.yAxis.title.text = "(" + seriesData[0].uvplot.units + ")";
        optionsUv.xAxis.min = seriesData[0].timespan.start;
        optionsUv.xAxis.max = seriesData[0].timespan.stop;
        Highcharts.setOptions({
            global: {
                timezoneOffset: -seriesData[0].utcoffset,
            },
        });
        // generate/display the actual plots
        if (document.getElementById(optionsTemp.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsTemp);
        };
        if (document.getElementById(optionsWindchill.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWindchill);
        };
        if (document.getElementById(optionsHumidity.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsHumidity);
        };
        if (document.getElementById(optionsBarometer.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsBarometer);
        };
        if (document.getElementById(optionsWind.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWind);
        };
        if (document.getElementById(optionsWindDir.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsWindDir);
        };
        if (document.getElementById(optionsRain.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsRain);
        };
        if (document.getElementById(optionsRadiation.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsRadiation);
        };
        if (document.getElementById(optionsUv.chart.renderTo)){
            var chart = new Highcharts.StockChart(optionsUv);
        };
    });
};
