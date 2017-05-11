/**
 * file: JaccardClustering.js
 * desc: d3js code for drawing the force directed clustering visualization.
 * auth: Capstone jaccard clustering team
 *       TR
 */

var jaccardClustering = function() {

    var exports = {},
        // SVG object
        svg = null,
        // SVG width
        width = 1100,
        // SVG height
        height = 900,
        // Parsed JSON object
        jsonData = '',
        // Data node objects returned by the clustering tool
        nodes = null
        // Force directed layout object
        layout = null,
        // Repulsion/attraction between nodes in the layout
        charge = -50,
        // Distance between nodes in the layout
        linkDistance = 60,
        // Layout gravity
        gravity = 0.02,
        // Element ID of the div to draw in
        element = '#d3-visual',
        // Maps species names to colors
        speciesColors = {},
        // Node color palette
        colors = [
            "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", 
            "#dd4477", "#66aa00", "#b82e2e", "#316395", "#994499", "#22aa99", 
            "#aaaa11", "#6633cc", "#e67300", "#8b0707", "#651067", "#329262", 
            "#5574a6", "#3b3eac"
        ];

    /** private **/

    /**
      * Flattens the dendogram into a list of nodes.
      */
    var flatten = function(root) {

        var flatNodes = [], 
            i = 0;

        var recurse = function(node) {
            
            if (node.children) 
                node.children.forEach(recurse);

            if (!node.id) 
                node.id = ++i;

            flatNodes.push(node);
        };

        recurse(root);

        return flatNodes;
    }

    /**
      * Returns the label for geneset nodes and an empty string for all others
      * (i.e. collapsed/internal/root nodes).
      */
    var getNodeLabel = function(d) { return d.type == 'geneset' ? d.name : ''; };

    /**
      * Returns an opacity value that's dependent on the node or edge type
      * provided.
      */
    var getOpacity = function(d) {
        // We're dealing with nodes
        if (d.name) {

            if (d.type === 'geneset')
                return 1;

            // Probably an internal node
            return 0.8;
            
        // We're dealing with edges
        } else {

            // An invisible root node exists and we don't show the edge for it.
            if (d.source.name === 'root')
                return 0;

            return 1;
        }

        return 0.8;
    }

    /**
      * Calculates the radius for a given node based on its type. Collapsed
      * cluster nodes are twice as big as the initial cluster node.
      */
    var getRadius = function(d) {

        if (d.type === 'collapsed-cluster')
            return d.size * 2;

        if (d.size)
            return d.size;

        return 0;
    }

    /**
      * Calculates the proper node label position for the given node.
      */
    var getPosition = function(d) { return -1 * (getRadius(d) + 5) };

    /**
      * Controls single mouse clicking behavior. Nothing happens if a gene set
      * node is clicked. Cluster nodes are collapsed and collpased clusters
      * expanded when they are clicked.
      */
    var onClick = function(d) {

        // Ignores drag events
        if (d3.event.defaultPrevented) 
            return;

        if (d.type === 'geneset')
            return;

        // The node is a cluster node and we set it to collapsed, which hides
        // all of its children.
        if (d.children) {

            d.type = 'collapsed-cluster';
            d._children = d.children;
            d.children = null;

        // The node is a collapsed cluster node and we expand it
        } else {

            d.type = 'cluster';
            d.children = d._children;
            d._children = null;
        }

        updateLayout();
    }

    /**
      * Controls right click behavior. Takes the user to the 
      * /viewgenesetdetails page when a gene set node is clicked.
      * node is clicked. (Collapsed) Cluster nodes take the user to the
      * /viewgenesetoverlap page.
      */
    var onRightClick = function(d) {

        // Prevent the stupid context menu from popping up
        d3.event.preventDefault();

        if (d.type === 'geneset') {
            window.open('/viewgenesetdetails/' + d.id, '_blank');

        // This is a cluster or collapsed cluster node.
        } else {

            var children = [];

            var getChildren = function(node) {
                
                if (node.children) 
                    node.children.forEach(getChildren);

                // Get hidden children too (only needed for collpased clusters)
                if (node._children) 
                    node._children.forEach(getChildren);

                // Otherwise cluster IDs get added. This actually won't break
                // the overlap page (they're ignored if they don't exist) but
                // it may add misc. gene sets to the overlap results.
                if (node.type === 'geneset')
                    children.push(node.id);
            };

            getChildren(d);

            window.open('/viewgenesetoverlap/' + children.join('+'), '_blank');
        }
    }

    /**
      * Controls visualization behavior when the mouse hovers over a node.
      * On gene set nodes, the labels are changed to gene set names.
      * Cluster nodes display the jaccard value or clustering coefficient or
      * whatever the hell that value is.
      */
    var mouseover = function(d) {

        var nodeSelected = d3.select(this);

        if (d.type == "cluster") {

            nodeSelected.select("circle").attr("r", d.size + 10);
            nodeSelected.select("text").attr("dy", "0.5em");
            nodeSelected.select("text").attr("dx", "0em");
            nodeSelected.select("text").text(d.jaccard_index.toPrecision(2));

        } else if (d.type == "geneset") {

            nodeSelected.select("text").text(d.info);

        } else {

            nodeSelected.select("circle").attr("r", d.size * 2);
            nodeSelected.select("text").text(d.name);
        }
    }

    /**
      * Controls visualization behavior when the mouse stops hovering over a 
      * node. On gene set nodes, the labels are changed back from gene set 
      * names to abbreviations.
      * Cluster nodes no longer display value.
      */
    var mouseout = function(d) {

        var nodeSelected = d3.select(this);

        nodeSelected.select("circle").attr("r", getRadius);
        nodeSelected.select("text").attr("dy", getPosition);
        nodeSelected.select("text").attr("dx", getPosition);
        nodeSelected.select("text").text(getNodeLabel);
    }

    /**
      * Maps colors to drawn nodes based on species. Each node (which
      * represents a gene set or a cluster) will get a certain color dependent
      * on its species. Clusters get their own color too.
      */
    var colorMap = function(d) {

        // This indicates the node isn't a geneset; it's either an internal node 
        // or a geneset node that has been collapsed.
        if (d.species === undefined)
            return '#0099FF';

        if (!(d.species in speciesColors)) {

            var cindex = Object.keys(speciesColors).length % colors.length;

            // speciesColors is a mapping of species names -> color
            speciesColors[d.species] = colors[cindex];
        }

        return speciesColors[d.species];
    }

    /**
      * Updates currently drawn nodes and edges based on user input (e.g.
      * clicking nodes).
      */
    var updateLayout = function() {

        var nodes = flatten(jsonData);
        var links = d3.layout.tree().links(nodes);
        var treeHeight = jsonData.height;

        // Restart the force layout.
        layout.nodes(nodes)
            .links(links)
            .start();

        link = link.data(links, function (d) { return d.target.id; });

        link.exit().remove();

        link.enter()
            .insert('line', '.node')
            .style('stroke', '#555')
            .style('stroke-width', '2px')
            .style('opacity', getOpacity);

        node = node.data(nodes, function (d) { return d.id; });

        // Removes the node from the SVG
        node.exit().remove();

        var nodeEnter = node.enter()
            .append('g')
            .attr('class', 'node')
            .on('click', onClick)
            .call(layout.drag);

        nodeEnter.append('circle')
            .attr('r', getRadius)
            .attr('shape-rendering', 'auto')
            .style('stroke', '#000')
            .style('stroke-width', '1.5px')
            .style('fill', function(d) { return colorMap(d); })
            .style('opacity', getOpacity);

        nodeEnter.append('text')
            .attr('dy', getPosition)
            .attr('dx', getPosition)
            .text(getNodeLabel);

        node.on('mouseover', mouseover);
        node.on('mouseout', mouseout);
        node.on('contextmenu', onRightClick);
    };

    /**
      * Generates the force tree version of the clustering visualization.
      */
    var makeLayout = function() {

        link = svg.selectAll(".link");
        node = svg.selectAll(".node");

        layout = d3.layout.force()
            .linkDistance(function (d) {
                return d.target.level == 0 ? 150 : 50;
            })
            .charge(charge)
            .linkDistance(linkDistance)
            .gravity(gravity)
            .size([width, height])
            .on("tick", function tick() {

                link.attr("x1", function (d) {
                    return d.source.x;
                })
                .attr("y1", function (d) {
                    return d.source.y;
                })
                .attr("x2", function (d) {
                    return d.target.x;
                })
                .attr("y2", function (d) {
                    return d.target.y;
                });

                node.attr("transform", function (d) {
                    return "translate(" + d.x + "," + d.y + ")";
                });
            });

        nodes = flatten(jsonData);

        // Get rid of gene set genes cause they're fucking useless
        for (var n in nodes) {

            var cnode = nodes[n];

            if (cnode.type == "geneset") {

                cnode.children = null;
                cnode.genes = null;
            }
        }
    };


    /** public **/
    
    /**
      * Draws the node color key.
      */
    exports.drawLegend = function() {

        var added = {};
        var key = svg
            .append('g');

        for (var i = 0; i < nodes.length; i++) {

            if (nodes[i].species === undefined)
                continue;

            if (nodes[i].species in added)
                continue;

            added[nodes[i].species] = true;

            // Abbreviate species names
            var species = nodes[i].species.split(' ');
            species = species[0][0] + '. ' + species[1];

            key.append('circle')
                .attr('cx', 15)
                .attr('x', 15)
                .attr('cy', 28 * Object.keys(added).length + 20)
                .attr('y', 28 * Object.keys(added).length + 20)
                .attr('r', 10)
                .style('fill-opacity', 0.90)
                .style('shape-rendering', 'geometricPrecision')
                .style('stroke', '#000')
                .style('stroke-width', '2px')
                .style('fill', function(d) { return colorMap(nodes[i]); })
                ;

            key.append('text')
                .attr('x', 33)
                .attr('y', 29 * Object.keys(added).length + 24)
                .text(species)
            ;
        }

        // Legend element for the cluster (internal) nodes
        key.append('circle')
            .attr('cx', 15)
            .attr('x', 15)
            .attr('cy', 28 * (Object.keys(added).length + 1) + 20)
            .attr('y', 28 * (Object.keys(added).length + 1) + 20)
            .attr('r', 6)
            .style('fill-opacity', 0.90)
            .style('shape-rendering', 'geometricPrecision')
            .style('stroke', '#000')
            .style('stroke-width', '2px')
            .style('fill', '#0099FF')
            ;

        key.append('text')
            .attr('x', 33)
            .attr('y', 29 * (Object.keys(added).length + 1) + 23)
            .text('Cluster')
        ;

        return exports;
    };

    /**
      * Draws the force directed cluster graph.
      */
    exports.drawGraph = function() {

        svg = d3.select(element)
            .append('svg')
            .attr('width', width)
            .attr('height', height);

        makeLayout();
        updateLayout();

        return exports;
    };

    /* setters/getters */
    
    exports.jsonData = function(_) {
        if (!arguments.length) return jsonData;
        jsonData = _;
        return exports;
    };

    exports.charge = function(_) {
        if (!arguments.length) return charge;
        charge = +_;
        return exports;
    };

    exports.linkDistance = function(_) {
        if (!arguments.length) return linkDistance;
        linkDistance = +_;
        return exports;
    };

    exports.gravity = function(_) {
        if (!arguments.length) return gravity;
        gravity = +_;
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

