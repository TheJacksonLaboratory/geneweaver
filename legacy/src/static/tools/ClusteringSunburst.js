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
      * Retrieves all the children of the given node.
      */
    var getChildren = function(node) {

        var children = [];

        var recurse = function(n) {
            
            children.push(n);

            if (n.children) 
                n.children.forEach(recurse);
        };

        recurse(node);

        return children;
    };

    /**
      * Maps colors to drawn nodes based on species. Each node (which
      * represents a gene set or a cluster) will get a certain color dependent
      * on its species. Clusters get their own color too.
      */
    var colorMap = function(d) {

        // This indicates the node isn't a geneset; it's probably a cluster.
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
      * Handles mouse hover events when a user places the mouse on one of the
      * drawn arcs. When a user hovers over a cluster, all nodes within that
      * cluster are highlighted and the clustering coefficient (jaccard) is
      * displayed in the middle of the sunburst.
      */
    var mouseover = function(d) {

        if (d.type === 'cluster') {

            svg.append('text')
                .attr('id', 'cluster-text')
                .attr('x', 0)
                .attr('y', 15)
                .style('font-size', '12px')
                .style('font-family', "'Open Sans', sans-serif")
                .style('font-weight', '400')
                .style('color', '#666')
                .style('background-color', '#666')
                .style('text-anchor', 'middle')
                //.style('text-decoration', 'underline')
                .text('Jaccard Similarity')
                ;

            svg.append('text')
                .attr('id', 'cluster-text')
                .attr('x', 0)
                .attr('y', 0)
                .style('font-size', '40px')
                .style('font-family', "'Open Sans', sans-serif")
                .style('font-weight', '400')
                .style('background-color', '#666')
                .style('color', '#666')
                .style('text-anchor', 'middle')
                .text(function() { return d.jaccard_index.toPrecision(2); })
                ;

            var children = getChildren(d);
            var co = {};

            // Get all the children under the current cluster and put their
            // names into an object for easy retrieval.
            for (var i = 0; i < children.length; i++)
                co[children[i].name] = children[i].name;

            // Lowers the opacity for all drawn arcs in the viz except for
            // those that are children of the current cluster.
            for (var i = 0; i < children.length; i++) {

                svg.selectAll('path')
                    .filter(function(d) { return !(d.name in co); })
                    .style('opacity', function(d){
                        return 0.3;
                    });
            }
        }
    };

    /**
      * Handles hover events when the mouse leaves the boundaries of a drawn
      * arc. When a user's mouse leaves an arc boundary the entire viz is reset
      * to its defaults.
      */
    var mouseout = function(d) {

        if (d.type === 'cluster') {

            svg.selectAll('#cluster-text').remove();

            svg.selectAll('path')
                .style('opacity', 1.0);
        }
    };

    /**
      * Controls right click behavior. Takes the user to the 
      * /viewgenesetdetails page when a gene set node is clicked.
      * Cluster nodes take the user to the /viewgenesetoverlap page.
      */
    var onRightClick = function(d) {

        // Prevent the stupid context menu from popping up
        d3.event.preventDefault();

        if (d.type === 'geneset') {
            window.open('/viewgenesetdetails/' + d.id, '_blank');

        // This is a cluster or collapsed cluster node.
        } else {

            var children = getChildren(d);
            var ids = [];

            // Get the GSIDs for all geneset nodes within this cluster
            for (var i = 0 ; i < children.length; i++)
                if (children[i].type === 'geneset')
                    ids.push(children[i].id);

            window.open('/viewgenesetoverlap/' + ids.join('+'), '_blank');
        }
    }

    /**
      * Creates the d3 partition layout and arc generator for the
      * visualization.
      */
    var makeLayout = function() {

        // Generate the partition layout. Areas are drawn based on the size
        // parameter of each node (geneset) object.
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
            .style('stroke', '#fff')
            .style('stroke-width', '2px')
            .on('mouseover', mouseover)
            .on('mouseout', mouseout)
            .on('contextmenu', onRightClick)
            ;
    };

    /**
      * Splits a signle line of text into several lines based on words and
      * characters per line. The returned set of lines have a max character
      * limit of 25 which also takes word boundaries into account (so lines
      * don't end in the middle of a word).
      */
    var chunkifyText = function(text) {

        var lines = [],
            line = '';

        text = text.split(' ');

        for (var i = 0; i < text.length; i++) {

            var word = text[i];

            // The characters of this line plus the next word exceed 25, so we
            // start a new line
            if (line.length > 0 && (line.length + word.length) > 25) {

                lines.push(line);

                line = '';
            }

            // Last word in the string, add the remaining characters to the
            // line list
            if (i === (text.length - 1)) {

                line += word;

                lines.push(line);

            } else {

                line += word + ' ';
            }
        }

        // Some labels might just be a bunch of characters with no spaces, in
        // this case we just slice it up into several lines of 25 characters
        // each.
        if (lines.length === 1 && lines[0].length > 25) {

            line = lines[0];
            lines = [];

            while (true) {

                var chunk = line.slice(0, 25);

                if (!chunk)
                    break;

                lines.push(line);

                line = line.slice(25);
            }
        }

        return lines;
    };

    var drawLabels = function() {

        var nodes = [];

        // Since long abbreviations get cut off (they exceed the SVG
        // boundaries) we draw the labels as separate text objects spanning
        // 25 characters (or less) each.
        for (var i = 0; i < partition.nodes(jsonData).length; i++) {

            var node = partition.nodes(jsonData)[i],
                chunks = [],
                labelText = node.name;

            if (node.type !== 'geneset')
                continue;

            chunks = chunkifyText(labelText);

            for (var j = 0; j < chunks.length; j++) {

                // Each of the label coordinates. ci keeps track of the line
                // number.
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
                
                // Adjust so each label line looks like it's on a separate line
                if (degrees < 90)
                    degrees += (d.ci * 3.5)
                else
                    degrees -= (d.ci * 3.5)

                // Lables from -90 <-> 90 degrees need to be shifted to the 
                // other side of sunburst
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
