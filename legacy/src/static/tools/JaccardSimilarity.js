/**
  * file: JaccardSimilarity.js
  * desc: d3js code for visualizing jaccard similarity venn diagrams and the
  *       similarity matrix.
  * auth: TR
  */

/**
  * Jaccard similarity module. Publicly exposes setters/getters for most
  * visualization options and two functions, draw and drawLegend, for
  * drawing the venn diagram and similarity matrices.
  *
  * The only variable required to be set by this module is data, which should
  * be the object returned by the jaccard tool.
  */
var jaccardSimilarity = function() {

    var exports = {},
        // SVG object
        svg = null,
        // SVG width in pixels
        width = 1100,
        // SVG height in pixels
        height = 900,
        // Padding (in pixels) between each individual venn diagram
        diagramPadding = 100,
        // Venn diagram opacity
        opacity = 0.70,
        // Circle data for each venn diagram
        vennCircles = [],
        // Individual venn diagram text lines (jac value, p-value, etc.)
        vennText = [],
        // Row/column labels for the venn diagrams
        vennLabels = [],
        // Shift venn diagrams and their labels N pixels to the right
        xShift = 150,
        // Shift venn diagrams and their labels down N pixels
        yShift = 120,
        // Venn diagram colors: Emphasis gene green, left red, right blue
        fillColors = ['#006400', '#EE0000', '#0000BB', '#FDBB84'],
        // Data returned by the tool
        data = null;

    /** private **/

    /**
      * Uses a regex to parse a string containing a p-value. The p-value string
      * is in a format returned by the jaccard tool (e.g. p = 0.01).
      *
      * arguments
      *     str: a string containing a p-value in the form 'p = 0.1'
      *
      * returns
      *     a float of the parsed p-value. Returns 1 if nothing could be parsed.
      */
    var parsePValue = function(str) {

        var regex = new RegExp([
            /[P|p]/,    // P or p
            /\s+/,      // >= 1 spaces
            /=/,        // Equals sign
            /\s+/,      // >= 1 spaces
            // >= 1 digits or >=1 digits, a period then >= 1 digits
            /(\d+\.*\d+|\d+)/
        ].map(function(r) { return r.source; }).join(''));

        var match = regex.exec(str);

        if (!match || match.length < 2)
            return 1.0;

        return parseFloat(match[1]);
    }

    /**
      * Organizes the list of venn diagrams returned by the tool into a series
      * of rows and columns dependent on the number of genesets (e.g. four
      * genesets should return a total of 16 comparisons, so four rows and four
      * columns). Sets the final x and y coordinates for each diagram.
      */
    var positionDiagrams = function() {

        var numSets = data.genesets.length;

        for (var i = 0; i < data.venn_diagrams.length; i++) {
            var venn = data.venn_diagrams[i];

            // Zero indexed row/column numbers
            venn.column = i % numSets;
            venn.row = Math.floor(i / numSets);
            // GS IDs for the left and right genesets
            venn.gsids = [data.gs_ids[venn.row], data.gs_ids[venn.column]];

            if (venn.text.length > 2)
                venn.pvalue = parsePValue(venn.text[2].text);
            else
                venn.pvalue = '';
        }
    };

    /**
      * Transforms the venn diagram data returned by the tool into a format
      * ready for display. Calculates proper x, y postiions, radii, and colors.
      */
    var makeCircles = function() {

        for (var i = 0; i < data.venn_diagrams.length; i++) {
            var venn = data.venn_diagrams[i];

            // Each venn object has data for two circles
            for (var j = 1; j <= 2; j++) {

                // cx, cy, and radius keys
                var vcx = 'c' + j + 'x',
                    vcy = 'c' + j + 'y',
                    vr = 'r' + j;

                var circle = {
                    cx: venn[vcx] + (venn.column * diagramPadding),
                    cy: venn[vcy] + (venn.row * diagramPadding),
                    r: venn[vr],
                    fill: function() {

                        if (venn.gsids[0] == venn.gsids[1])
                            return fillColors[3];
                        else if (j === 1 && venn['emphasis1'] == 'True')
                            return fillColors[0];
                        else if (j === 2 && venn['emphasis2'] == 'True')
                            return fillColors[0];
                        else
                            return fillColors[j];
                    }(),
                    column: venn.column,
                    row: venn.row,
                    title: venn['title1'],
                    desc: venn['desc1'],
                    gsid1: venn.gsids[0],
                    gsid2: venn.gsids[1],
                    pvalue: venn.pvalue
                };

                vennCircles.push(circle);
            }
        }
    };

    /**
      * Formats and positions text elements for each individual venn diagram.
      */
    var makeText = function() {

        for (var i = 0; i < data.venn_diagrams.length; i++) {
            var venn = data.venn_diagrams[i];

            var c1x = venn['c1x'] + (venn.column * diagramPadding);
                c2x = venn['c2x'] + (venn.column * diagramPadding),
                c1y = venn['c1y'] + (venn.row * diagramPadding),
                c2y = venn['c2y'] + (venn.row * diagramPadding),
                r1 = venn.r1,
                r2 = venn.r2;

            // Distance between corcle midpoints
            var d = Math.sqrt(Math.pow((c2x - c1x), 2) +
                              Math.pow((c2y - c1y), 2));
            // Distance from the left circle midpoint to the intersection midpoint
            var a = ((r1 * r1) - (r2 * r2) + (d * d)) / (2 * d);
            var h = Math.sqrt((r1 * r1) - (a * a));
            // Intersection midpoints
            var p2x = c1x + a * (c2x - c1x) / d;
            var p2y = c1y + a * (c2y - c1y) / d;
            //
            var cd = ((r1 * r1) + (r2 * r2)) / 2;
            var c3x = c1x - r1;
            // Each venn object has an array of text objects with (usually)
            // three elements
            for (var j = 0; j < venn.text.length; j++) {

                if (j === 0)
                    var yShift = -30;
                else if (j === 1)
                    var yShift = 30;
                else
                    var yShift = 45;

                var text = {
                    //x: p2x,
                    //x: c3x,// + cd,
                    //y: p2y + yShift,
                    //subRadius: (r1 < r2) ? r1 : r2,
                    x: venn.text[j].tx + (venn.column * diagramPadding) - 40,
                    y: venn.text[j].ty + (venn.row * diagramPadding) - 20,
                    text: venn.text[j].text
                };

                vennText.push(text);
            }
        }
    };

    /**
      * Formats and positions row and column labels for the venn diagram matrix.
      */
    var makeLabels = function() {

        var gsTable = data.geneset_table;

        for (var i = 0; i < gsTable.length; i++) {

            var columnText = {
                x: (i * diagramPadding),
                y: 20,
                text: gsTable[i].text,
                isColumn: true,
                isRow: false
            };

            var rowText = {
                x: 0,
                y: (i * diagramPadding),
                text: gsTable[i].text,
                isColumn: false,
                isRow: true
            }

            vennLabels.push(columnText);
            vennLabels.push(rowText);
        }

    };

    var isClicked = (function() {
        var clicked = false;

        return function() {
            clicked = !clicked;

            return !clicked;
        };
    })();

    /** public **/

    /**
      * Draws the venn diagram matrix legend.
      */
    exports.drawLegend = function() {

        var types = [
            'X-Axis GeneSet',
            'Y-Axis GeneSet',
            'Same GeneSet',
            'Contains an Emphasis Gene',
            'GeneSet P-value > Threshold'
        ];

        var key = d3.select('#jaccard-legend')
            .append('svg')
            .attr('width', '250px')
            .attr('height', '150px')
            .append('g');

        for (var i = 0; i < types.length; i++) {

            key.append('circle')
                .attr('cx', 15)
                // 2 * diameter plus a bit more for spacing
                .attr('cy', 28 * i + 20)
                .attr('r', 10)
                .style('fill-opacity', 0.70)
                .style('shape-rendering', 'geometricPrecision')
                .style('stroke', '#000')
                .style('stroke-width', '2px')
                .style('fill', function(d) {

                    if (i === 0)
                        return fillColors[1];
                    else if (i === 1)
                        return fillColors[2];
                    else if (i === 2)
                        return fillColors[3];
                    else if (i === 3)
                        return fillColors[0];
                    else
                        return '#FFF';
                })
                ;

            key.append('text')
                .attr('x', 33)
                .attr('y', 29 * i + 24)
                .text(function() { return '= ' + types[i]; });
            ;
        }

        return exports;
    };

    /**
      * Erases the venn diagram matrix by deleting the SVG element and its
      * children nodes. Used for reseting the zoom and image.
      */
    exports.erase = function() { 
        d3.select('#jaccard').selectAll('*').remove();
        svg.remove();

        // Reset these otherwise the viz will draw duplicates
        vennCircles = [];
        vennText = [];
        vennLabels = [];

        return exports;
    };

    /**
      * Shades insignificant venn diagrams based on a p-value threshold.
      */
    exports.shadeInsignificant = function(threshold) {

        if (!threshold)
            threshold = 0.05;

        // Shades insignificant results
        d3.selectAll('circle')
            .filter(function(d) { return d != undefined; })
            .filter(function(d) { return d.pvalue > threshold; })
            .attr('fill', function(d) { return '#AAA' });

        // Restores/keeps colors on significant results
        d3.selectAll('circle')
            .filter(function(d) { return d != undefined; })
            .filter(function(d) { return d.pvalue <= threshold; })
            .attr('fill', function(d) { return d.fill; });

        return exports;
    };

    /**
      * Draws the venn diagram matrix.
      */
    exports.draw = function() {

        positionDiagrams();
        makeCircles();
        makeText();
        makeLabels();

        svg = d3.select('#jaccard')
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .call(d3.behavior.zoom().on('zoom', function() {
                svg.attr('transform', function() {
                    return 'translate(' + d3.event.translate + ')' +
                           ' scale(' + d3.event.scale + ')';
                });
            }))
            .append('g')
            //.attr('transform', 'translate(' + 50 + ',' + yShift + ')');
            .attr('transform', 'translate(50, 50)');

        var circles = svg.selectAll('circle')
            .data(vennCircles)
            .enter()
            .append('circle')
            .attr('transform', 'translate(' + xShift + ',' + yShift + ')')
            .attr('cx', function(d) { return d.cx; })
            .attr('cy', function(d) { return d.cy; })
            .attr('r', function(d) { return d.r; })
            .attr('fill', function(d) { return d.fill; })
            .style('fill-opacity', opacity)
            .style('shape-rendering', 'geometricPrecision')
            .style('stroke', '#000')
            .style('stroke-width', '1px')
            .style('stroke-opacity', 1)
            .on('mouseover', function(d) {

                // Mouse over events generate and display a tooltip with
                // intersection data
                d3.select("#jaccard")
                    .append("div")
                    .attr('id', 'jac-tooltip')
                    .attr("class", "tooltip")
                    .style('opacity', 0.9)
                    .html(d.title + '<br />' + d.desc)
                    .style('left', d3.event.pageX + 'px')
                    .style('top', d3.event.pageY + 'px');
            })
            .on('mouseout', function(d) {
                d3.select('#jac-tooltip').remove();
            })
            .on("click", function(d){

                if (d3.event.shiftKey) {
                    var row = d.row;
                    var col = d.column;

                    if (isClicked()) {

                        d3.select('#jaccard').selectAll("circle")
                            .style('stroke', 'black')
                            .style("stroke-width", 1);

                    } else {

                        // Shift click rows and columns yellow of circle selected
                        svg.selectAll('circle')
                            .filter(function (d) {
                                if ((d.row == row) || (d.column == col))
                                    return true;
                            })
                            //.style('stroke', '#FB9A99')
                            .style('stroke', '#B2DF8A')
                            .style("stroke-width", 4)

                        // Keeps the circles not in the clicked row and column black
                        svg.selectAll('circle')
                            .filter(function (d) {
                                if (!((d.row == row) || (d.column == col)))
                                    return true;
                            })
                            .style('stroke', 'black')
                            .style("stroke-width", 1);
                    }

                // User is clicking the venn diagram without shift, this will
                // open a new window for them and allow them to view the gene
                // set details (if X == Y) or the gene overlap page.
                } else {

                    // Remove GS prefix
                    var gsid1 = d.gsid1.slice(2);
                    var gsid2 = d.gsid2.slice(2);

                    if (gsid1 === gsid2)
                        window.open('/viewgenesetdetails/' + gsid1, '_blank');
                    else
                        window.open('/viewgenesetoverlap/' + gsid1 + '+' + gsid2, '_blank');
                }
            })
        ;

        var labels = svg.selectAll('text')
            .data(vennText)
            .enter()
            .append('text')
            .attr('transform', 'translate(' + xShift + ',' + yShift + ')')
            .text(function(d) { return d.text; })
            .attr('x', function(d) {
                var textWidth = this.getBoundingClientRect().width;
                //return d.x - (textWidth / 2);
                //return d.x - d.subRadius;
                return d.x;
            })
            .attr('y', function(d) {
                return d.y;
            })
            .style('color', '#000')
            .style('font-size', '11px')
            ;

        var xLabelShift = xShift - 20;
        var yLabelShift = yShift + 40;

        var labels = svg.selectAll('header-text')
            .data(vennLabels)
            .enter()
            .append('text')
            .style('color', '#000')
            .style('font-size', '10px')
            .style('font-weight', 'bold')
            //.text(function(d) { return d.text; })
            .attr('transform', function(d) {
                if (d.isColumn)
                    return 'translate(' + xLabelShift + ',' + 20 + ')'
                else
                    return 'translate(' + (-10) + ',' + yLabelShift + ')'
            })
            .attr('x', function(d) {
                var textWidth = this.getBoundingClientRect().width;
                //return d.x - (textWidth / 2);
                //return d.x - d.subRadius;
                return d.x;
            })
            .attr('y', function(d) {
                return d.y;
            })
            // The text for each row/col label is split into chunks of 20
            // characters so everything fits properly and doesnt' overlap
            .each(function(d) {

                var chunks = [];
                var labelText = d.text;

                while (true) {

                    var chunk = labelText.slice(0, 25);

                    if (!chunk)
                        break;

                    chunks.push(chunk);

                    labelText = labelText.slice(25);
                }

                for (var i = 0; i < chunks.length; i++) {

                    var textElem = d3.select(this)
                        .append('tspan')
                        .attr('x', d.x)
                        .attr('y', d.y)
                        .attr('dx', 0)
                        .attr('dy', function() { return (i * 15); })
                        .text(chunks[i]);
                }
            });

        return exports;
    };

    /** setters/getters **/

    exports.data = function(_) {
        if (!arguments.length) return data;
        data = _;
        return exports;
    };

    exports.diagramPadding = function(_) {
        if (!arguments.length) return diagramPadding;
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

/**
 * Jaccard similarity matrix module. Publicly exposes setters/getters for most
 * visualization options and another function, draw, which draws the similarity
 * matrix.
 *
 * The only variable required to be set by this module is data, which should
 * be the object returned by the jaccard tool.
 */
var jaccardSimilarityMatrix = function() {

    var exports = {},
        // Data returned by the tool
        data = null,
        // Element wrapper ID containing the drawn similarity matrix
        matrixElement = '#matrix',
        // Table element
        table = null;

    /** private **/

    /**
      * Generates the table header HTML for the similarity matrix.
      */
    var makeHeader = function() {

        var headRow = table.append('tr');
        var gsTable = data.geneset_table;

        // Empty column for geneset names
        headRow.append('th')
            .attr('valign', 'bottom')
            .attr('align', 'left');

        headRow.selectAll('header')
            .data(gsTable)
            .enter()
            .append('th')
            .attr('align', 'cetner')
            .style('text-align', 'center')
            .style('border-top', '1px solid #000')
            .style('border-left', '1px solid #000')
            .style('border-right', '1px solid #000')
            .style('border-bottom', '1px solid #000')
            .style('padding-left', '3px')
            .style('padding-right', '3px')
            .style('background-color', function(d, i) {

                if (i % 2)
                    return '#E7F0E7';
                else
                    return '#FFF';
            })
            .append('a')
            .attr('href', function(d) {
                // Removes the 'GS' prefix
                return '/viewgenesetdetails/' + d.gsID.slice(2);
            })
            .attr('target', '_blank')
            .style('color', '#2e2e2e')
            .text(function(d) { return d.gsID; });
    };

    /**
      * Creates each individual row/column element.
      */
    var makeRows = function() {

        // Iterate over each row; each row object contains n columns
        for (var i = 0; i < data.geneset_table.length; i++) {

            var dataRow = data.geneset_table[i];
            var row = table.append('tr');

            // Left side geneset IDs and names
            var rowElem = row.append('td')
                .attr('align', 'center')
                .style('border', '1px solid #000')
                .style('padding-right', '5px')
                .style('padding-left', '5px')
                .style('font-size', '12px')
                .style('font-weight', 'bold')
                ;

            rowElem.append('input')
                .attr('id', 'check-' + dataRow.gsID.slice(2))
                .attr('class', 'ui-checkbox')
                .attr('name', 'matrix-checkbox')
                .attr('type', 'checkbox')
                .style('margin-right', '3px');

            rowElem.append('a')
                .attr('href', '/viewgenesetdetails/' + dataRow.gsID.slice(2))
                .attr('target', '_blank')
                .style('color', '#2e2e2e')
                .text(dataRow.text);

            row.selectAll('row')
                .data(dataRow.entries)
                .enter()
                .append('td')
                .attr('align', 'center')
                .style('border-left', '1px solid #000')
                .style('border-right', '1px solid #000')
                .style('border-bottom', function() {
                    // Last table row has a black border, inner rows are grey
                    if (i === (data.geneset_table.length - 1))
                        return '1px solid #000';
                    else
                        return '1px solid #bbb';
                })
                .style('font-size', '11px')
                .style('padding', '0.5em')
                .style('background-color', function(d, j) {
                    // Indicates both genesets are the same
                    if (i == j)
                        return '#C7D0C7';
                    else if (j % 2)
                        return '#E7F0E7';
                    else
                        return '#FFF';
                })
                .append('a')
                .attr('target', '_blank')
                .attr('href', function(d, j) {
                    // Removes the 'GS' prefix
                    var idLeft = data.geneset_table[i].gsID.slice(2);
                    var idRight = data.geneset_table[j].gsID.slice(2);

                    // Same geneset
                    if (i === j)
                        return '/viewgenesetdetails/' + idLeft;
                    else
                        return '/viewgenesetoverlap/' + idLeft + '+' + idRight;
                })
                .style('color', function(d, j) {
                    // Same geneset
                    if (i === j)
                        return '#CC0000';
                    else
                        return '#000';
                })
                .html(function(d) { return d.jval + '<br />' + d.pval; });
        }
    };

    /**
     * Generates a link for viewing the overlap between all genesets involved
     * in the analysis.
     */
    var makeAllOverlapLink = function() {

        var gsTable = data.geneset_table;
        // All the GS IDs without their 'GS' prefix, joined together with '+'
        var gsIds = gsTable.map(function(t) {
            return t.gsID.slice(2);
        }).join('+');

        // Left side geneset IDs and names
        d3.select(matrixElement)
            .append('a')
            .attr('target', '_blank')
            .attr('href', function() {
                return '/viewgenesetoverlap/' + gsIds;
            })
            .style('color', '#006400')
            .style('font-weight', 'bold')
            .style('padding-top', '5px')
            .text('View overlap between all sets');
    };

    /** public **/

    /**
     * Draws the similarity matrix.
     */
    exports.draw = function() {

        table = d3.select('#matrix')
            .append('table');

        makeHeader();
        makeRows();
        makeAllOverlapLink();

        return exports;
    };

    /**
     * Setters/getters
     */
    exports.data = function(_) {
        if (!arguments.length) return data;
        data = _;
        return exports;
    };

    exports.matrixElement = function(_) {
        if (!arguments.length) return matrixElement;
        matrixElement = _;
        return exports;
    };

    return exports;
};

