/**
 * Created by olatunde on 10/1/16.
 */
/**
 * file:  UpSet.js
 * desc:  d3js code for visualizing upset bar charts
 * auth: Oyinda Olatunde
 */

/**
 * UpSet module. For drawing the bar chart.
 */
var upset = function () {

    var exports = {},
        // SVG object
        svg = null,
        // SVG width in pixels
        width = 1100,
        // SVG height in pixel
        height = 800,
        // Bar chart margins
        margin = {
            top: 20,
            right: 20,
            bottom: 50,
            left: 300
        },
        //Padding between each individual bar
        diagramPadding = 0.5,
        // Bar data for each intersection bar
        Intersectionbars = [],
        //Circle data for each intersection circle
        IntersectionCircles = [],
        //Bar data for each set size bar
        Setbars = [],
        // Individual set text lines
        setText = [],
        // Padding (in pixels) between each individual diagram
        diagramPadding = 20,
        // Y-axis/X-axis labels for the bar chart
        chartLabels = [],
        // Chart dimensions
        chartWidth = +width - margin.left - margin.right,
        chartHeight = +height - margin.top - margin.bottom,
        textHeight = 50,
        // Bar chart colours: un-query black-grey, and query purple
        barFillColours = ['#C0C0C0', '#8E44AD'],
        // Circle diagram colours: un-query light grey. and query dark grey
        circleFillColours = ['#F0F0F0', '#636363'],
        // Shift bar diagrams and their labels N pixels to the right
        xShift = 20,
        // Shift bar diagrams and their labels down N pixels
        yShift = 100,
        // Data returned by the tool
        data = null;

    /** private **/

    /**
     * Transforms the bar chart data returned by the tool into a format
     * ready for display.
     *
     * Assumptions:
     */
    var makeBars = function () {
        var bx = 0,
            by = 0;

        //Makes bars for the intersection size bar diagram
        for (var i = 0; i < data.intersection_diagrams.length; i++) {
            var set = data.intersection_diagrams[i];

            var bar = {
                fill: barFillColours[0],
                height: set['intersection'],
                desc: set['desc1'],
                name: set['name1'],
                x: bx,
                y: by,
                textFill: '#000000'
            };

            Intersectionbars.push(bar);
            by = by + 30;
        }

        //Make bars for the set size bar diagram
        bx = 0;

        for (var j = 0; j < data.set_diagrams.length; j++){
            set = data.set_diagrams[j];

            var rect = {
                fill: barFillColours[0],
                height: set['size'],
                width: 18,
                x: bx,
                desc: set['desc1'],
                name: set['name1']
            };

            Setbars.push(rect);
            bx = bx + 20;
        }
    };

    /**
     * Transforms the circle data returned by the tool.
     */
    var makeCircles = function () {

        var vcx = 0,
            vcy = 0,
            vfill = circleFillColours[0];

        var genesets = data.genesets;
        for (var y = 0; y < data.intersection_diagrams.length; y++){
            for ( var x = 0; x < data.genesets.length; x++){

                var intersect = data.intersection_diagrams[y];
                for (var i = 0; i < intersect.sets.length; i++){
                    if (genesets.indexOf("GS" + intersect.sets[i]) === x){
                        vfill = circleFillColours[1];
                    }
                }

                var circle = {
                    cx: vcx,
                    cy: vcy,
                    r: 9,
                    fill: vfill
                };

                IntersectionCircles.push(circle);
                vfill = circleFillColours[0];
                vcx = vcx + 20;

            }

            vcy = vcy + 30;
            vcx = 0;
        }
    };

    /**
     * Formats and positions text elements for each individual geneset
     */
    var makeText = function() {
        bx = 0;
        by = 8;
        tx1 = -10;

        for (var i = 0; i < data.set_diagrams.length; i++){
            var set = data.set_diagrams[i];

            var text = {
                fill: circleFillColours[0],
                height: 60,
                width: 19,
                x: bx,
                y: by,
                name: set['name'],
                colour: circleFillColours[1],
                tx: tx1
            }

            setText.push(text);
            bx = bx + 20;
            by = by - 15;
            tx1 = tx1 + 17;

        }
    };

    /**
     * Formats and positions lines between set circles
     */
    /*var makeLine = function() {

        for(var i = 0; i < data.intersection_diagrams.length; i++){
            var set = data.
        }
    };

    /** public **/

    /**
     * Draws the bar graph for the Intersection Size!!!
     */
    exports.draw = function () {
        makeCircles();
        makeBars();
        makeText();

        var x = d3.scaleLinear().range([0, chartHeight]).domain([0, d3.max(Intersectionbars, function(d) { return d.height})]),
            y = d3.scaleBand().range([0, chartWidth]).domain(Intersectionbars.map(function(d) { return d.name; }));

        //Append svg to the upset area
        svg = d3.select("#upset").append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", "translate(" + (margin.left + margin.right) + "," + margin.top + ")");

        //Adding the circle diagrams
        svg.selectAll("circle")
            .data(IntersectionCircles)
            .enter().append("circle")
            .attr("transform", "translate(" + (yShift - (2.5 * xShift)) +"," + (yShift + textHeight) + ")")
            .attr("cx", function(d) { return d.cx; })
            .attr("cy", function(d) { return d.cy; })
            .attr("r", function(d) { return d.r; })
            .style("fill", function(d) { return d.fill; });

        //Adding the intersect size diagrams
        svg.selectAll("bar")
            .data(Intersectionbars)
            .enter().append("rect")
            .attr("x", function(d) { return d.x; })
            .attr("y", function(d) { return d.y; })
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + "," + ((yShift + textHeight) - 9) + ")")
            .attr("height", 18)
            .attr("width", function(d) { return x(d.height); })
            .style("fill", function(d) { return d.fill; });

        var x = d3.scaleBand().range([0, (yShift - diagramPadding)]).domain(Setbars.map(function(d) { return d.name; })).padding(0.5),
            y = d3.scaleLinear().range([(yShift - diagramPadding), 0]).domain([0, d3.max(Setbars, function(d) { return d.height})]);

        //adding the set size diagrams
        svg.selectAll("bar")
            .data(Setbars)
            .enter().append("rect")
            .attr("transform", "translate(-" + xShift + ",0)")
            .attr("class", "bar")
            .attr("width", function (d) {return d.width; })
            .attr("x", function (d) { return d.x; })
            .attr("y", function(d) { return y(d.height); })
            .attr("height", function (d) { return (yShift - diagramPadding) - y(d.height); })
            .style("fill", function (d) { return d.fill; });

        //adding the set names to the diagram
        svg.selectAll("bar")
            .data(setText)
            .enter().append("rect")
            .attr("transform", "translate(-" + xShift + "," + (yShift - xShift) + ") skewX(45)")
            .attr("x", function (d) { return d.x; })
            .attr("height", function (d) { return d.height; })
            .attr("width", function (d) { return d.width;})
            .style("fill", function (d) { return d.fill; });

        svg.selectAll("text")
            .data(setText)
            .enter().append("text")
            .attr("transform", "translate(-" + xShift + "," + (yShift - xShift) + ") rotate(45)")
            .style("font-family", "Calibri", "sans-serif")
            .style("font-size", ".6em")
            .style("color", "black")
            .text(function (d) {return d.name; })
            .attr("y", function (d) { return d.y - 10;})
            .attr("x", function (d) { return (d.tx + 15);});

        return exports;
    };

    /**
     * Setters/getters
     */
    exports.data = function (_) {
        if(!arguments.length) return data;
        data = _;
        return exports;
    };

    exports.diagramPadding = function (_) {
        if(!arguments.length) return diagramPadding;
        diagramPadding = +_;
        return exports;
    };

    exports.height = function(_) {
        if (!arguments.length) return height;
        height = +_;
        return exports;
    };

    exports.width = function(_) {
        if (!arguments.length) return width;
        width = +_;
        return exports;
    };

    exports.xShift = function(_) {
        if (!arguments.length) return xShift;
        xShift = +_;
        return exports;
    };


    exports.yShift = function(_) {
        if (!arguments.length) return yShift;
        yShift = +_;
        return exports;
    };

    return exports;
};