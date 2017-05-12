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

        var labels = svg.datum(jsonData)
            .append('g')
            .selectAll('text')
            //.data(function() { 
            //    console.log(partition.nodes);
            //    partition.nodes.filter(function(d) { 
            //    return d.type === 'geneset';
            //})})
            .data(partition.nodes)
            .enter()
            .append('text')
            .attr('dx', '.30em')
            //.attr('dy', '.31em')
            //.attr('y', function(d) { return (((d.x + d.dx) / 2) - Math.PI / 2) / Math.PI * 180; })
            //.attr('y', function(d) { return d.x; })
            .attr('x', function(d) { return Math.sqrt(d.y + d.dy); })
            .attr('transform', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;

                return 'rotate(' + degrees + ')' + 
                    (degrees < 180 ? '' : 'translate(' + ((radius * 2) + 10) + ',0)') + 
                    (degrees < 180 ? '' : 'rotate(180)')
            })
            .style('text-anchor', function(d) {
                var degrees = ((d.x + d.dx / 2) - Math.PI / 2)  / Math.PI * 180;

                console.log(d);
                return degrees < 180 ? 'start' : 'end'
            })
            .text(function(d) { return d.type === 'geneset' ? d.name : ''; })
            ;
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

        while (nodeStack.length > 0) {

            var node = nodeStack.shift();

            if (node.children)
                nodeStack = nodeStack.concat(node.children);

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
