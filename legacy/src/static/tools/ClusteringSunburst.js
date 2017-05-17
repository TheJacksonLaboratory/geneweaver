/**
  * file: ClusteringSunburst.js
  * desc: Reimplementation of the sunburst visualization for the gene set
  *       clustering tool (the original was unmaintainable).
  * auth: TR
  */

var clusteringSunburst = function() {

    var exports = {},
        // SVG object
        svg = null,
        // SVG width
        width = 1100,
        // SVG height
        height = 900,
        // Radius of the sunburst
        radius = 0,
        // Parsed JSON object
        jsonData = '',
        // Maps species names to colors
        speciesColors = {},
        // Element ID of the div to draw in
        element = '#d3-visual',
        // Partition layout object
        partition = null,
        // Arc generator object
        arc = null,
        // Node color palette
        colors = [
            "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", 
            "#dd4477", "#66aa00", "#b82e2e", "#316395", "#994499", "#22aa99", 
            "#aaaa11", "#6633cc", "#e67300", "#8b0707", "#651067", "#329262", 
            "#5574a6", "#3b3eac"
        ];

    /** private **/

    /**
      * Maps colors to drawn nodes based on species. Each node (which
      * represents a gene set or a cluster) will get a certain color dependent
      * on its species. Clusters get their own color too.
      */
    var colorMap = function(d) {

        // This indicates the node isn't a geneset; it's either an internal node 
        // or a geneset node that has been collapsed.
        if (d.species === undefined)
            return '#bdbdbd';

        if (!(d.species in speciesColors)) {

            var cindex = Object.keys(speciesColors).length % colors.length;

            // speciesColors is a mapping of species names -> color
            speciesColors[d.species] = colors[cindex];
        }

        return speciesColors[d.species];
    }

    /**
      * Creates the d3 partition layout and arc generator for the
      * visualization.
      */
    var makeLayout = function() {

        // Generate the partition layout. Areas are drawn based on the size
        // parameter of each node object.
        partition = d3.layout.partition()
            .sort(null)
            .size([2 * Math.PI, radius * radius])
            .value(function(d) { return d.size; });

        // Arc generator for each gene set and cluster node in the layout.
        arc = d3.svg.arc()
            .startAngle(function(d) { return d.x; })
            .endAngle(function(d) { return d.x + d.dx; })
            .innerRadius(function(d) { return Math.sqrt(d.y); })
            .outerRadius(function(d) { return Math.sqrt(d.y + d.dy); });
    };

    var drawArcs = function() {

        var path = svg.datum(jsonData)
            .selectAll('path')
            .data(partition.nodes)
            .enter()
            .append('path')
            .attr('id', function(d){ return d.name; })
            .attr('d', arc)
            // Hides the inner circle
            .attr('display', function(d) { return d.depth ? null : 'none'; })
            .style('fill', colorMap)
            .style('stroke', '#222')
            //.style('opacity', opac)
            //.on('click', click)
            //.on('dblclick',dblclick)
            ;
    };

    var drawLabels = function() {

        var nodes = [];

        for (var i = 0; i < partition.nodes(jsonData).length; i++) {
            var node = partition.nodes(jsonData)[i];
            var chunks = [];
            var labelText = node.name;

            if (node.type !== 'geneset')
                continue;

            // Separate a single line into lines of 25 characters
            while (true) {

                var chunk = labelText.slice(0, 25);

                if (!chunk)
                    break;

                chunks.push(chunk);

                labelText = labelText.slice(25);
            }

            for (var j = 0; j < chunks.length; j++) {

                nodes.push({
                    x: node.x,
                    dx: node.dx,
                    y: node.y,
                    dy: node.dy,
                    ci: j,
                    text: chunks[j],
                });
            }
        };

        var labels = svg.datum(jsonData)
            .append('g')
            .selectAll('text')
            .data(nodes)
            .enter()
            .append('text')
            .attr('dx', '.30em')
            .attr('x', function(d) { return Math.sqrt(d.y + d.dy); })
            .attr('transform', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;
                var transadd = Math.sqrt(d.y + d.dy) * 2.0 + 10;
                
                if (degrees < 90)
                    degrees += (d.ci * 3.5)
                else
                    degrees -= (d.ci * 3.5)

                // Lables from -90 <-> 90 need to be shifted to the other side
                // of sunburst
                return 'rotate(' + degrees + ')' + 
                    (degrees < 90 ? '' : 'translate(' + transadd + ',0)') + 
                    (degrees < 90 ? '' : 'rotate(180)')
            })
            .style('text-anchor', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;

                return degrees < 90 ? 'start' : 'end'
            })
            .text(function(d) { return d.text; })
            ;

        /*
        var labels = svg.datum(jsonData)
            .append('g')
            .selectAll('text')
            .data(partition.nodes)
            .enter()
            .append('text')
            .attr('dx', '.30em')
            .attr('x', function(d) { return Math.sqrt(d.y + d.dy); })
            .attr('transform', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;
                var transadd = Math.sqrt(d.y + d.dy) * 2.0 + 10;
                               
                // Some extra spacing since we break up long abbreviations into
                // separate lines
                if (degrees < 90)
                    degrees = degrees - 5;
                else
                    degrees = degrees + 5;
                // Lables from -90 <-> 90 need to be shifted to the other side
                // of sunburst
                return 'rotate(' + degrees + ')' + 
                    (degrees < 90 ? '' : 'translate(' + transadd + ',0)') + 
                    (degrees < 90 ? '' : 'rotate(180)')
            })
            .style('text-anchor', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;

                return degrees < 90 ? 'start' : 'end'
            })
            // Since long abbreviations get cut off (they exceed the SVG
            // boundaries) we draw text as separate tspans of 25 characters
            // each. This code wis ripped from my own viz library for
            // offsetting long strings of text.
            .each(function(d) {

                if (d.type !== 'geneset')
                    return;

                var chunks = [];
                var labelText = d.name;

                // Separate a single line into lines of 25 characters
                while (true) {

                    var chunk = labelText.slice(0, 25);

                    if (!chunk)
                        break;

                    chunks.push(chunk);

                    labelText = labelText.slice(25);
                }

                var lastLength = 0;
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;

                for (var i = 0; i < chunks.length; i++) {

                    if (i === 0)
                        lastLength = '.30em';

                    // The rotate part doesn't actualy do anything
                    var textElem = d3.select(this)
                        .append('tspan')
                        .text(chunks[i])
                        .attr('x', function(d) { return Math.sqrt(d.y + d.dy); })
                        .attr('transform', function() { 
                            if (degrees < 90)
                                return 'rotate(' + (degrees + (i * 35)) + ')'; 
                            else
                                return 'rotate(' + (degrees - (i * 15)) + ')'; 
                        })
                        //.attr('dx', function() {
                        //    var oldLength = lastLength;
                        //    lastLength = -this.getComputedTextLength();

                        //    return oldLength;
                        //})
                        //.attr('dy', function() { return !i ? 0 : 15; })
                        .attr('dy', function() { return 15; })

                        ;
                }
            })
            //.text(function(d) { return d.type === 'geneset' ? d.name : ''; })
            ;
            */
    };

    /** public **/

    exports.draw = function() {


        svg = d3.select(element)
            .append('svg')
            .attr('width', width)
            .attr('height', height)
            .append('g')
            .attr('transform', 'translate(' + width / 2 + ',' + height * 0.55 + ')');

        radius = Math.min(width, height) / 3;

        // Removes gene nodes
        var recurse = function(node) {
            
            if (node.type === 'geneset')
                node.children = null;

            else if (node.children) 
                node.children.forEach(recurse);
        };
        recurse(jsonData);

        makeLayout();
        drawArcs();
        drawLabels();

        return exports;
    };

    exports.drawLegend = function() {

        var added = {},
            nodeStack = [jsonData],
            key = svg
                .append('g')
                // Undo the global image translate performed by draw()
                .attr('transform', 
                      'translate(' + -(width / 2) + 
                      ',' + -(height * 0.55) + ')');

        // Since the data is stored as a hierarchy we traverse each node and
        // their children
        while (nodeStack.length > 0) {

            var node = nodeStack.shift();

            if (node.children)
                nodeStack = nodeStack.concat(node.children);

            // Probably a cluster or gene node
            if (node.species === undefined)
                continue;

            if (node.species in added)
                continue;

            added[node.species] = true;

            // Abbreviate species names
            var species = node.species.split(' ');
            species = species[0][0] + '. ' + species[1];

            key.append('rect')
                .attr('x', 15)
                .attr('y', 28 * Object.keys(added).length + 10)
                .attr('width', 20)
                .attr('height', 20)
                .style('fill-opacity', 0.90)
                .style('shape-rendering', 'auto')
                .style('stroke', '#000')
                .style('stroke-width', '2px')
                .style('fill', function(d) { return colorMap(node); })
                ;

            key.append('text')
                .attr('x', 40)
                .attr('y', 29 * Object.keys(added).length + 24)
                .text(species)
            ;
        }

        // Legend element for the cluster (internal) nodes
        key.append('rect')
            .attr('x', 15)
            .attr('y', 28 * (Object.keys(added).length + 1) + 10)
            .attr('width', 20)
            .attr('height', 20)
            .style('fill-opacity', 0.90)
            .style('shape-rendering', 'auto')
            .style('stroke', '#000')
            .style('stroke-width', '2px')
            .style('fill', colorMap('cluster'))
            ;

        key.append('text')
            .attr('x', 40)
            .attr('y', 28 * (Object.keys(added).length + 1) + 24)
            .text('Cluster')
        ;

        return exports;
    };

    /** private **/

    exports.jsonData = function(_) {
        if (!arguments.length) return jsonData;
        jsonData = _;
        return exports;
    };

    exports.element = function(_) {
        if (!arguments.length) return element;
        element = _;
        return exports;
    };

    exports.width = function(_) {
        if (!arguments.length) return width;
        width = +_;
        return exports;
    };

    exports.height = function(_) {
        if (!arguments.length) return height;
        height = +_;
        return exports;
    };

    return exports;
};
