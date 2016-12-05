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
var upset;
upset = function () {

    var exports = {},
        // SVG object
        svg = null,
        // SVG width in pixels
        width = 1100,
        // SVG height in pixel
        height = 900,
        // Bar chart margins
        margin = {
            top: 20,
            right: 20,
            bottom: 200,
            left: 20
        },
        //Padding between each individual bar
        diagramPadding = 0.5,
        // Bar data for each intersection bar
        Intersectionbars = [],
        BackgroundRow = [],
        //Bar data for each jaccard value
        JaccardBars = [],
        //Bar data for each entropy value
        EntropyBars = [],
        //Circle data for each intersection circle
        IntersectionCircles = [],
        BackgroundColumn = [],
        //Bar data for each set size bar
        setBars = [],
        // Individual set text lines
        setText = [],
        setLine = [],
        // Padding (in pixels) between each individual diagram
        diagramPadding = 20,
        // Y-axis/X-axis labels for the bar chart
        chartLabels = [],
        // Chart dimensions
        chartWidth = +width - margin.left - margin.right,
        chartHeight = +height - margin.top - margin.bottom,
        textHeight = 50,
        // Bar chart colours: itersection. entropy, jaccard
        barFillColours = ['#800080', '#4682b4', '#FFA62F'],
        // Circle diagram colours
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
            by = 0,
            jaccard1 = 0;

        //Makes bars for the intersection size bar diagram
        //Makes bars for the entropy bar diagram
        //Makes bars for the jaccard bar diagram
        for (var i = 0; i < data.intersection_diagrams.length; i++) {
            var set = data.intersection_diagrams[i];

            var intersectgenes = [];

            for (var z = 0; z < set.genes.length; z++) {
                var line = set.genes[z];
                intersectgenes.push(new Array());
                intersectgenes[z].push(line[0]);
                intersectgenes[z].push(line[1]);
                intersectgenes[z].push(line[2]);
            }

            if (set['len'] === 2)
                jaccard1 = set['jaccard_score'];

            var jbar = {
                type: 'row' + i,
                fill: barFillColours[2],
                height: jaccard1,
                name: set['name1'],
                x: bx,
                y: by,
                genes: intersectgenes,
                desc: set['desc1'],
                entropy: set['set_entropy']
            };

            var intersectBar = {
                type: 'row' + i,
                fill: barFillColours[0],
                height: set['intersection'],
                desc: set['desc1'],
                name: set['name1'],
                x: bx,
                y: by,
                textFill: '#000000',
                genes: intersectgenes,
                entropy: set['set_entropy'],
                jaccard: jaccard1
            };

            var entropybar = {
                type: 'row' + i,
                fill: barFillColours[1],
                height: set['set_entropy'],
                name: set['name1'],
                x: bx,
                y: by,
                genes: intersectgenes,
                jaccard: jaccard1,
                desc: set['desc1']
            };

            var background = {
                type: 'row' + i,
                y: by - 9,
                x: bx - 9,
                width: chartWidth,
                height: 20,
                fill: "#006400",
                opacity: 0,
                jaccard: jaccard1,
                desc: set['desc1'],
                name: set['name1'],
                entropy: set['set_entropy'],
                genes: intersectgenes
            };

            BackgroundRow.push(background);
            Intersectionbars.push(intersectBar);
            EntropyBars.push(entropybar);
            JaccardBars.push(jbar);
            by = by + 30;
            jaccard1 = 0;
        }

        //Make bars for the set size bar diagram
        bx = 0;

        for (var j = 0; j < data.set_diagrams.length; j++) {
            set = data.set_diagrams[j];

            var setgenes = [];
            for (var t = 0; t < set.genes.length; t++)
                setgenes.push(set.genes[t]);

            var rect = {
                fill: circleFillColours[1],
                height: set['size'],
                width: 18,
                x: bx,
                desc: set['desc1'],
                name: set['name'],
                type: set['set_id'],
                genelist: setgenes
            };

            var background = {
                type: '' + set['set_id'],
                x: bx - 9,
                y: -9,
                width: 19,
                height: (30 * data.intersection_diagrams.length),
                fill: "#006400",
                opacity: 0,
                genelist: setgenes,
                desc: set['desc1'],
                name: set['name']
            };

            setBars.push(rect);
            BackgroundColumn.push(background);
            bx = bx + 20;
        }
    };

    /**
     * Transforms the circle data returned by the tool.
     */
    var makeCircles = function () {

        //Circle variables
        var vcx = 0,
            vcy = 0,
            vfill = circleFillColours[0],
            vquery = false,
            lastx = 0;
        var first = null,
            last = null,
            lx1 = null,
            lx2 = null;

        var genesets = data.genesets;
        for (var y = 0; y < data.intersection_diagrams.length; y++) {

            for (var x = 0; x < data.genesets.length; x++) {

                var intersect = data.intersection_diagrams[y];
                for (var i = 0; i < intersect.sets.length; i++) {
                    //Is this circle-set part of the intersection
                    if (genesets.indexOf("GS" + intersect.sets[i]) === x) {
                        vfill = circleFillColours[1];
                        vquery = true;

                        if (first === null && last === null) {
                            first = x;
                            last = x;
                            lx1 = vcx;
                            lx2 = vcx;
                        }
                        else if (x > last) {
                            last = x;
                            lx2 = vcx;
                        }
                    }
                }

                var circle = {
                    cx: vcx,
                    cy: vcy,
                    r: 9,
                    fill: vfill,
                    query: vquery
                };

                IntersectionCircles.push(circle);
                vfill = circleFillColours[0];
                vcx = vcx + 20;
                vquery = false;
            }

            var line = {
                x1: lx1,
                y1: vcy,
                x2: lx2,
                y2: vcy,
                height: 3,
                fill: circleFillColours[1]
            };

            setLine.push(line);
            first = null;
            last = null;
            lx1 = null;
            lx2 = null;

            vcy = vcy + 30;
            lastx = vcx;
            vcx = 0;
            if (vcy > height) {
                height = height + 100;
            }
        }
        if (lastx > 100) {
            width = width + 150;
        }
    };

    /**
     * Formats and positions text elements for each individual geneset
     */
    var makeText = function () {
        bx = 0;
        by = 8;
        tx1 = -10;

        for (var i = 0; i < data.set_diagrams.length; i++) {
            var set = data.set_diagrams[i];

            var text = {
                fill: circleFillColours[0],
                height: 60,
                width: 19,
                x: bx,
                y: by,
                name: set['name'],
                colour: circleFillColours[1],
                tx: tx1,
                type: set['set_id']
            };

            setText.push(text);
            bx = bx + 20;
            by = by - 15;
            tx1 = tx1 + 17;

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

        function tabulateSet(data, columns) {
            var table = d3.select("#upset-genes").append("table"),
                thead = table.append("thead"),
                tbody = table.append("tbody");

            //Appending header row
            thead.append("tr")
                .selectAll("th")
                .data(columns)
                .enter()
                .append("th")
                .text(function (column) {
                    return column;
                })
                .style("fill", "white");

            // create a row for each object in the data
            var rows = tbody.selectAll("tr")
                .data(data)
                .enter()
                .append("tr")
                .text(function (d) {
                    return d;
                });

            //create a cell in each row for each column
            var cells = rows.selectAll("td")
                .data(function (row) {
                    return columns.map(function (column) {
                        return {column: column, value: row[column]};
                    });
                })
                .enter()
                .append("td")
                .attr("style", "font-family: Courier")
                .html(function (d) {
                    return d.value;
                });

            return table;
        }

        function tabluateIntersect(data, columns) {
            var genesTable = d3.select("#upset-genes").append("table"),
                thead = genesTable.append("thead"),
                tbody = genesTable.append("tbody");

            thead.append("tr")
                .selectAll("th")
                .data(columns)
                .enter().append("th")
                .text(function (column) {
                    return column;
                });


            var rows = tbody.selectAll("tr").data(data).enter().append("tr");
            rows.selectAll("td")
                .data(function (d) {
                    return d;
                })
                .enter().append("td")
                .text(function (d) {
                    return d;
                });
        }

        var x = d3.scaleLinear().range([0, (chartHeight / 4)]).domain([0, d3.max(Intersectionbars, function (d) {
                return d.height
            })]),
            y = d3.scaleBand().range([0, chartWidth]).domain(Intersectionbars.map(function (d) {
                return d.name;
            }));

        //Append svg to the upset area
        svg = d3.select("#upset-graph").append("svg")
            .attr("width", width)
            .attr("height", height)
            .append("g")
            .attr("transform", "translate(50,50)");

        //Adding the circle diagrams
        svg.selectAll("circle")
            .data(IntersectionCircles)
            .enter().append("circle")
            .attr("transform", "translate(" + (yShift - (2.5 * xShift)) + "," + (yShift + textHeight) + ")")
            .attr("cx", function (d) {
                return d.cx;
            })
            .attr("cy", function (d) {
                return d.cy;
            })
            .attr("r", function (d) {
                return d.r;
            })
            .style("fill", function (d) {
                return d.fill;
            });

        svg.selectAll("line")
            .data(setLine)
            .enter().append("line")
            .attr("transform", "translate(" + (yShift - (2.5 * xShift)) + "," + (yShift + textHeight) + ")")
            .attr("x1", function (d) {
                return d.x1;
            })
            .attr("y1", function (d) {
                return d.y1;
            })
            .attr("x2", function (d) {
                return d.x2;
            })
            .attr("y2", function (d) {
                return d.y2;
            })
            .style("stroke", function (d) {
                return d.fill;
            })
            .style("stroke-width", "3px");

        //Adding background highlight
        svg.selectAll("bar")
            .data(BackgroundRow)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("transform", "translate(" + (yShift - (2.5 * xShift)) + "," + (yShift + textHeight) + ")")
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return d.y;
            })
            .attr("height", function (d) {
                return d.height;
            })
            .attr("width", function (d) {
                return d.width;
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .style("fill-opacity", 0)
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();

                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                infoTable = tabulateSet([d.entropy], ["Set Entropy"]);
                if (d.jaccard === 0)
                    infoTable = tabulateSet(["N/A"], ["Jaccard Value"]);
                else
                    infoTable = tabulateSet([d.jaccard], ["Jaccard Value"]);
                var genesTable = tabluateIntersect(d.genes, ["Genes", "Species", "Entropy"]);
            });


        //Draw intersection graph

        //Adding Axis
        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + "," + ((yShift + textHeight) - 10) + ")")
            .call(d3.axisTop(x));

        var label = svg.append("rect")
            .attr("width", (chartHeight / 4))
            .attr("height", 20)
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + "," + (yShift) + ")")
            .style("fill", "#C0C0C0");
        var label = svg.append("text")
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + ", " + (yShift) + ")")
            .attr("x", 30)
            .attr("y", 18)
            .text("Cardinality")
            .attr("font-family", "sans-serif")
            .attr("font-size", "16px")
            .attr("fill", "black");

        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + ",80)")
            .call(d3.axisBottom(x));

        //Adding the intersect size diagrams
        svg.selectAll("bar")
            .data(Intersectionbars)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return d.y;
            })
            .attr("transform", "translate(" + ((xShift * data.set_diagrams.length) + yShift) + "," + ((yShift + textHeight) - 9) + ")")
            .attr("height", 18)
            .attr("width", function (d) {
                return x(d.height);
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .style("fill-opacity", 1)
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();

                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                infoTable = tabulateSet([d.entropy], ["Set Entropy"]);
                if (d.jaccard === 0)
                    infoTable = tabulateSet(["N/A"], ["Jaccard Value"]);
                else
                    infoTable = tabulateSet([d.jaccard], ["Jaccard Value"]);
                var genesTable = tabluateIntersect(d.genes, ["Genes", "Species", "Entropy"]);
            });


        //Draw entropy
        var x = d3.scaleLinear().range([0, (chartHeight / 4)]).domain([0, d3.max(EntropyBars, function (d) {
                return d.height
            })]),
            y = d3.scaleBand().range([0, chartWidth]).domain(EntropyBars.map(function (d) {
                return d.name;
            }));

        //Adding Axis
        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + ((chartHeight / 4) + yShift)) + "," + ((yShift + textHeight) - 10) + ")")
            .call(d3.axisTop(x));

        label = svg.append("rect")
            .attr("width", (chartHeight / 4))
            .attr("height", 20)
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + ((chartHeight / 4) + yShift)) + "," + (yShift ) + ")")
            .style("fill", "#C0C0C0");
        var label = svg.append("text")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + ((chartHeight / 4) + yShift)) + ", " + (yShift) + ")")
            .attr("x", 30)
            .attr("y", 18)
            .text("Entropy")
            .attr("font-family", "sans-serif")
            .attr("font-size", "16px")
            .attr("fill", "black");

        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + ((chartHeight / 4) + yShift)) + ",80)")
            .call(d3.axisBottom(x));

        //Adding the entropy diagrams
        svg.selectAll("bar")
            .data(EntropyBars)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return d.y;
            })
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + ((chartHeight / 4) + yShift)) + "," + ((yShift + textHeight) - 9) + ")")
            .attr("height", 18)
            .attr("width", function (d) {
                return x(d.height);
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .style("fill-opacity", 1)
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();
                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                infoTable = tabulateSet([d.height], ["Set Entropy"]);
                if (d.jaccard === 0)
                    infoTable = tabulateSet(["N/A"], ["Jaccard Value"]);
                else
                    infoTable = tabulateSet([d.jaccard], ["Jaccard Value"]);
                var genesTable = tabluateIntersect(d.genes, ["Genes", "Species", "Entropy"]);
            });


        //Draw jaccard
        var x = d3.scaleLinear().range([0, (chartHeight / 3)]).domain([0, d3.max(JaccardBars, function (d) {
                return d.height
            })]),
            y = d3.scaleBand().range([0, chartWidth]).domain(JaccardBars.map(function (d) {
                return d.name;
            }));

        //Adding Axis
        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + (((chartHeight / 4) + yShift) * 2)) + "," + ((yShift + textHeight) - 10) + ")")
            .call(d3.axisTop(x));

        label = svg.append("rect")
            .attr("width", (chartHeight / 3))
            .attr("height", 20)
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + (((chartHeight / 4) + yShift) * 2)) + "," + (yShift ) + ")")
            .style("fill", "#C0C0C0");
        var label = svg.append("text")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + (((chartHeight / 4) + yShift) * 2)) + ", " + (yShift) + ")")
            .attr("x", 30)
            .attr("y", 18)
            .text("Jaccard")
            .attr("font-family", "sans-serif")
            .attr("font-size", "16px")
            .attr("fill", "black");

        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + (((chartHeight / 4) + yShift) * 2)) + ",80)")
            .call(d3.axisBottom(x));

        //Adding the jaccard diagrams
        svg.selectAll("bar")
            .data(JaccardBars)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return d.y;
            })
            .attr("transform", "translate(" + (((xShift * data.set_diagrams.length) + yShift) + (((chartHeight / 4) + yShift) * 2)) + "," + ((yShift + textHeight) - 9) + ")")
            .attr("height", 18)
            .attr("width", function (d) {
                return x(d.height);
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .style("fill-opacity", 1)
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();
                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                infoTable = tabulateSet([d.entropy], ["Set Entropy"]);
                if (d.jaccard === 0)
                    infoTable = tabulateSet(["N/A"], ["Jaccard Value"]);
                else
                    infoTable = tabulateSet([d.height], ["Jaccard Value"]);
                var genesTable = tabluateIntersect(d.genes, ["Genes", "Species", "Entropy"]);
            });

        //Draw set graph

        var x = d3.scaleBand().range([0, (yShift - diagramPadding)]).domain(setBars.map(function (d) {
                return d.name;
            })).padding(0.5),
            y = d3.scaleLinear().range([(yShift - diagramPadding), 0]).domain([0, d3.max(setBars, function (d) {
                return d.height
            })]);

        //Adding Axis
        svg.append("g")
            .attr("class", "axis")
            .attr("transform", "translate(-" + (xShift + 1) + ",0)")
            .call(d3.axisLeft(y));

        //adding the set size diagrams
        svg.selectAll("bar")
            .data(setBars)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("transform", "translate(-" + xShift + ",0)")
            .attr("width", function (d) {
                return d.width;
            })
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return y(d.height);
            })
            .attr("height", function (d) {
                return (yShift - diagramPadding) - y(d.height);
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();

                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                genesTable = tabulateSet(d.genelist, ["Genes"]);
            });

        //adding the set names to the diagram
        var names = svg.selectAll("bar")
            .data(setText)
            .enter();

        names.append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("transform", "translate(-" + xShift + "," + (yShift - xShift) + ") skewX(45)")
            .attr("x", function (d) {
                return d.x;
            })
            .attr("height", function (d) {
                return d.height;
            })
            .attr("width", function (d) {
                return d.width;
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .on("mouseover", mouseover)
            .on("mouseout", mouseout);

        names.append("text")
            .attr("transform", "translate(-" + xShift + "," + (yShift - xShift) + ") rotate(45)")
            .style("font-family", "Calibri", "sans-serif")
            .style("font-size", ".6em")
            .style("color", "black")
            .text(function (d) {
                return d.name;
            })
            .attr("y", function (d) {
                return d.y - 10;
            })
            .attr("x", function (d) {
                return (d.tx + 15);
            });

        //Adding background highlight
        svg.selectAll("bar")
            .data(BackgroundColumn)
            .enter().append("rect")
            .attr("class", function (d) {
                return d.type;
            })
            .attr("transform", "translate(" + (yShift - (2.5 * xShift)) + "," + (yShift + textHeight) + ")")
            .attr("x", function (d) {
                return d.x;
            })
            .attr("y", function (d) {
                return d.y;
            })
            .attr("height", function (d) {
                return d.height;
            })
            .attr("width", function (d) {
                return d.width;
            })
            .style("fill", function (d) {
                return d.fill;
            })
            .style("fill-opacity", 0)
            .on("mouseover", mouseover)
            .on("mouseout", mouseout)
            .on("click", function (d) {
                d3.selectAll("table").remove();
                var infoTable = tabulateSet([d.name], ["Gene Set"]);
                infoTable = tabulateSet([d.desc], ["Set Size"]);
                genesTable = tabulateSet(d.genelist, ["Genes"]);
            });

        function mouseover(clase) {
            svg.selectAll("." + this.getAttribute("class"))
                .style("fill", "#006400")
                .style("fill-opacity", function (d) {
                    return (this.getAttribute("fill-opacity") + 0.3);
                });
        }

        function mouseout(clase) {
            svg.selectAll("." + this.getAttribute("class"))
                .style("fill", function (d) {
                    return d.fill;
                })
                .style("fill-opacity", function (d) {
                    return d.opacity;
                });
        }

        return exports;
    };

    /**
     * Setters/getters
     */
    exports.data = function (_) {
        if (!arguments.length) return data;
        data = _;
        return exports;
    };

    exports.diagramPadding = function (_) {
        if (!arguments.length) return diagramPadding;
        diagramPadding = +_;
        return exports;
    };

    exports.height = function (_) {
        if (!arguments.length) return height;
        height = +_;
        return exports;
    };

    exports.width = function (_) {
        if (!arguments.length) return width;
        width = +_;
        return exports;
    };

    exports.xShift = function (_) {
        if (!arguments.length) return xShift;
        xShift = +_;
        return exports;
    };


    exports.yShift = function (_) {
        if (!arguments.length) return yShift;
        yShift = +_;
        return exports;
    };

    return exports;
};