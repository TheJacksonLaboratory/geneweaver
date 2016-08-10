/**
 * file: PhenomeMap.js
 * desc: d3js code for visualizing the HiSim graph. 
 */

//global variable containing the JSON data and the d3.force object
var g = {
    data: null,
    force: null
};

//dictionary of species & colors. Multiple Species defaults to gray.
var color_dict = {};

color_dict["Multiple Species"] = "#636363";

// Color palette for the nodes
var COLORS = [
    "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", 
    "#dd4477", "#66aa00", "#b82e2e", "#316395", "#994499", "#22aa99", 
    "#aaaa11", "#6633cc", "#e67300", "#8b0707", "#651067", "#329262", 
    "#5574a6", "#3b3eac"
];

//initialization
//$(function () {
var doThings = function(graphData) {

    g.data = graphData;

    var width = '900',
        height = '700',
        r = 6;

    //Create a sized SVG surface within viz, with zooming and panning capability:
    var svg = d3.select('#viz2')
        .append('svg')
        .attr('width', width)
        .attr('height', height)
        .attr('viewBox', function() {return '0 0 ' + width + ' ' + height;})
        .call(d3.behavior.zoom()
            .on('zoom', function () {
                svg.attr('transform', 'translate(' + d3.event.translate + ')' + 'scale(' + d3.event.scale + ')')
            }))
        .append('g');

    g.link = svg.selectAll('path.link'),
    g.node = svg.selectAll('.node');

    // d3 sliders for charge, charge distance, link strength, link distance, 
    // and gravity, respectively. Currently not working due to some unknown bug
    // in the slider.js library. 
    var charge_slider = d3.slider()
        .axis(true)
        .min(0)
        .max(100)
        .step(.1)
        .value(40)
        .on('slide', function (e, v) {
            g.force.start();
        })
        ;

    var cd_slider = d3.slider()
        .axis(true)
        .min(0)
        .max(100)
        .step(.1)
        .value(30)
        .on('slide', function (e, v) {
            g.force.chargeDistance(v / .1);
            g.force.start();
        });

    var ls_slider = d3.slider()
        .axis(true)
        .min(1)
        .max(100)
        .step(.1)
        .value(30)
        .on('slide', function (e, v) {
            g.force.start();
        });

    var ld_slider = d3.slider()
        .axis(true)
        .min(1)
        .max(100)
        .step(.1)
        .value(40)
        .on('slide', function (e, v) {
            g.force.start();
        });

    var gravity_slider = d3.slider()
        .axis(true)
        .min(0)
        .max(100)
        .step(.1)
        .value(20)
        .on('slide', function (e, v) {
            g.force.gravity(Math.pow((v / 10), 2) / 100)
            g.force.start();
        });

    d3.select("#charge_slider")
        .call(charge_slider);

    d3.select("#ls_slider")
        .call(ls_slider);

    d3.select("#ld_slider")
        .call(ld_slider);

    d3.select("#gravity_slider")
        .call(gravity_slider);

    d3.select("#cd_slider")
        .call(cd_slider)

    // Graph force layout
    g.force = d3.layout.force()
        .nodes(g.data.nodes)
        .links(getLinks(g.data.nodes))

        // The linkDistance is proportional to difference in depths to 
        // prevent crowding
        .linkDistance(function (link) {
            return ((link.target.depth - link.source.depth) * ld_slider.value());
        })

        // linkStrength is also proportional to distance
        .linkStrength(function (link) {
            return 1 / ((link.target.depth - link.source.depth) * ls_slider.value() / 20);
        })

        // Deeper nodes have a stronger charge to force a more spread-out, 
        // triangular tree shape
        .charge(function (d) {
            return (-charge_slider.value() * ((d.depth + 1) * 10));
        })
        .size([width, height])
        .on("tick", tick);

    var nodes = flatten(g.data.nodes);

    // Initialize positions of tree elements to reduce tangling caused 
    // by random initialization
    initializeLayout(nodes);

    // Names of genes, genesets, and species that can be used to highlight
    // nodes and pathways.
    var select2_data = extract_select2_data();

    $("#search").select2({
        data: select2_data,
        containerCssClass: "search"
    });

    //Draw the graph:
    //Note that this method is invoked again
    //when clicking nodes:
    update();

    // Species legend
    var legend = d3.select('#legend')
        .append('svg')
        .attr('width', '300')
        .attr('height', function () {
            return ((Object.keys(color_dict).length) * 20 + 10);
        })
        .selectAll('circle')
        .data(Object.keys(color_dict))
        .enter()
        .append('g')
        .attr('class', 'node');

    legend.append('circle')
        .attr('r', 4.5)
        .style('fill', function (d) {
            return color_dict[d];
        })
        .style('stroke', function (d) {
            return color_dict[d];
        })
        .style('stroke-width', '3')
        .style('fill-opacity', '.5')
        .attr('cy', function (d) {
            return 10 + 20 * Object.keys(color_dict).indexOf(d);
        })
        .attr('cx', 20);

    legend.append('text')
        .text(function (d) {
            return d;
        })
        .attr('dy', function (d) {
            return 14 + 20 * Object.keys(color_dict).indexOf(d);
        })
        .attr('dx', '30')
        .attr('text-anchor', 'start')
        .style('font', '12px sans-serif')
        .style('fill', 'black');
};


//invoked once at the start,
//and again when from 'click' method
//which expands and collapses a node.
function update() {

    var width = 960,
        height = 500,
        padding = 15;

    //iterate through original nested data, and get one dimensional array of nodes.
    var nodes = flatten(g.data.nodes);

    //Each node extracted above has an array of children id's.
    //from them, we can use a custom getLinks() layout function in order
    //to build a links selection.
    var links = getLinks(nodes);

    // pass both of those sets to the graph layout engine, and restart it
    g.force.nodes(nodes)
        .links(links)
        .start();

    //-------------------
    // create a subselection, wiring up data, using a function to define
    //how it's supposed to know what is appended/updated/exited
    g.link = g.link.data(links);

    //Build new links by adding new svg lines:
    g.link.enter()
        .insert('line', '.node')
        .attr('class', 'link');

    // create a subselection, wiring up data, using a function to define
    //how it's suppossed to know what is appended/updated/exited
    g.node = g.node.data(nodes, function (d) { return d.id; });

    //Get rid of old nodes:
    g.node.exit().remove();
    g.link.exit().remove();

    //-------------------
    //create new nodes by making grouped elements that contain circles and text:
    var nodeEnter = g.node.enter()
        .append('g')
        .attr('class', 'node')
        .on('click', click)
        .on('mousedown', function (d) {
            d3.event.stopPropagation();
        })
        .call(g.force.drag);

    //circle within the single node group:
    nodeEnter.append('circle')
        .attr('r', 4.5);
    //nodeEnter.append('rect')
    //    .attr('width', 200)
    //    .attr('height', 100)
    //    ;

    //Set link color based on search results
    g.link.style('stroke', function (d) {
        if (d.source.found && d.target.found)
            return 'red';
        else
            return '#ccc';
    });

    //text within the single node group:
    nodeEnter.append('text')
        .style('font-family', 'Helvetica, Arial, sans-serif')
        .style('font-size', '12px')
        .attr('dy', '-.2em')
        .attr('dx', '1em')
        .attr('text-anchor', 'start')
        .text(function (d) {
            if (d.children.length > 0 || d._children)
                return;
            else
                return d.Genesets.length <= 3 ? d.Genesets : d.Genesets.length + ' sets...';
        });

    nodeEnter.append('text')
        .style('font-family', 'Helvetica, Arial, sans-serif')
        .style('font-size', '12px')
        .attr('dy', '1em')
        .attr('dx', function (d) {
            return (d.children.length > 0) ? '-1em' : '1em';
        })
        .attr('text-anchor', function (d) {
            return (d.children.length > 0) ? 'end' : 'start';
        })
        .text(function (d) {
            if (d.children.length > 0 || d._children)
                return;
            else
                return d.Abbreviations[0];
        });

    //mouseover information for each node
    nodeEnter.select('circle')
        .append('svg:title')
        .text(function (d) {
            return d.tooltip;
        });

    //All nodes, do the following:
    g.node.select('circle')
        .style('fill', function (d) { return colorMap(d); })
        .style('stroke', function (d) { return colorMap(d); })
        .style('fill-opacity', opacity);

    g.node.selectAll("text").attr("fill", textColor);
    g.force.start();

    d3.selectAll("circle")
        .attr("r", function (d) {
            return (d.weight >= 3 ? 4.5 * Math.sqrt(d.weight) : 4.5);
        });
}

/**
 * Maps species to the appropriate color in our color palette array.
 *
 * arguments
 *      d: some object
 *
 * returns
 *      a string of the hex color code
 */
function colorMap(d) {

    if (d.species.length > 1) {

        return "#636363";

    } else if (!(d.species in color_dict)) {

        var cindex = Object.keys(color_dict).length % COLORS.length;

        color_dict[d.species] = COLORS[cindex];
    }

    return color_dict[d.species];
}

//Change opacity based on number of children
function opacity(d) {
    return d._children ? "1" // collapsed package
            :
            d.children.length > 0 ? ".55" // expanded package
                    :
                    "0"; // leaf node
}

//Changes text color for emphasis
function textColor(d) {
    if (d.emphasis) {
        return '#CC0000';
    }
    else return 'default';
}

// $("#tooltip").mousemove(function (e) {
//find X & Y coordinates
//   x = e.clientX,
//         y = e.clientY;

//Set tooltip position according to mouse position
// tooltipSpan.style.top = (y + 20) + 'px';
// tooltipSpan.style.left = (x + 20) + 'px';
// });


// Invoked from 'update'.
// The original source data is not the usual nodes + edge list,
// but rather an adjacency list of nodes and their children.
// We need a list of nodes + links for the force layout engine.
// So returns a list of all nodes under the root.
function flatten(data) {
    var nodes = [];
    //checks to see which nodes have no parents. these are the only nodes we will recurse on,
    //to make sure we cover the entire tree with minimum redundancy. Worth a O(n) operation once
    //to save up to n extra recursive calls, and prevents collapsed children from showing up when they
    //shouldn't
    for (var i = 0, len = data.length; i < len; i++) {
        data[i].orphan = true;
    }
    for (var i = 0, len = data.length; i < len; i++) {
        if (data[i]._children) {
            for (var j = 0, jlen = data[i]._children.length; j < jlen; j++) {
                getNodeByID(data, data[i]._children[j]).orphan = false;
            }
        }
        else {
            for (var j = 0, jlen = data[i].children.length; j < jlen; j++) {
                getNodeByID(data, data[i].children[j]).orphan = false;
            }
        }
    }

    //recursively get each node's children and it's children's children. does not
    //look at collapsed children or their children.
    function recurse(node) {
        if (!getNodeByID(nodes, node.id)) {
            nodes.push(node);
        }
        if (node.children.length > 0) {
            for (var i = 0, count = node.children.length; i < count; i++) {
                var nextNode = getNodeByID(data, node.children[i]);
                recurse(nextNode);
            }
        }
    }

    //recurse on orphans only
    for (var i = 0, len = data.length; i < len; i++) {
        if (data[i].orphan) {
            recurse(data[i]);
        }
    }
    return nodes;
}

//nodes are identified in the children arrays by their ID, so we need
//this function to access the nodes.
function getNodeByID(nodes, wanted_id) {
    for (var i = 0; i < nodes.length; i++) {
        if (nodes[i].id == wanted_id) {
            return nodes[i];
        }
    }
}

//gets the array of link objects for the force diagram to use
function getLinks(nodes) {
    var links = [];
    for (var i = 0; i < nodes.length; i++) {
        var n = nodes[i];
        for (var j = 0; j < n.children.length; j++) {
            var link = {
                source: n,
                target: getNodeByID(nodes, n.children[j])
            };
            if (link.source.found && link.target.found) {
                link.class = "found";
            }
            links.push(link);
        }
    }
    return links;
}

/**
 * Manually positions the nodes into columns to create a hierarchical
 * structure. Required since the force graph layout will attempt to make its
 * own arrangement. Each column is ordered by the number of set intersections,
 * higher order intersections on the left and decreasing to the right.
 *
 */
function initializeLayout(nodes) {

    var nextdepths = [0];
    var previous = [-1];

    for (var i = 0; i < nodes.length; i++) {

        while (nodes[i].depth > nextdepths.length - 1) {
            nextdepths.push(0);
            previous.push(-1);
        }

        if (previous[nodes[i].depth] >= 0) {

            prevNode = getNodeByID(nodes, previous[nodes[i].depth]);
            prevNode.below = nodes[i].id;
            nodes[i].above = prevNode.id;
        }

        previous[nodes[i].depth] = nodes[i].id;
        nodes[i].x = nodes[i].depth * 100 + 100;
        nodes[i].y = nextdepths[nodes[i].depth] * 20 + 100;

        nextdepths[nodes[i].depth]++;
    }
}


//Collapses nodes upon click, unless they're being dragged.
//essentially switches the "active" children array with the
// "hidden" _children array.
function click(d) {
    if (d3.event.defaultPrevented) return; // ignore drag
    if (d.children.length > 0) {
        d._children = d.children;
        d.children = [];
        nodes = flatten(g.data.nodes);
        initializeLayout(nodes);
    } else if (d._children) {
        d.children = d._children;
        d._children = null;
        nodes = flatten(g.data.nodes);
        initializeLayout(nodes);
    }
    else {
        var paths = [];
        for (var i = 0; i < d.Genesets.length; i++) {
            paths = paths.concat(searchTree(d.Genesets[i]));
        }
        openPaths(paths);
    }
    //
    update();
}


//searches on a string sent in from the dropdown
function searchTree(search) {
    console.log("SEARCH STRING : " + search);
    path = [];
    for (var i = 0; i < g.data.nodes.length; i++) {
        g.data.nodes[i].found = false;
        if (g.data.nodes[i].Genesets.indexOf(search) >= 0
                || g.data.nodes[i].Genes.indexOf(search) >= 0
                || g.data.nodes[i].species.indexOf(search) >= 0) {
            path.push(g.data.nodes[i]);
        }
    }
    return path;
}

//Exctracts the data to search on
//TODO: there is an edge case where sometimes bootstrapping can have a childless node not at the bottom of the
//  tree. this function assumes that the bottom of the tree is the level at which the first leaf node is found.
//  Need to change this algorithm to get information from each leaf node regardless of depth.
function extract_select2_data() {
    var index = 0;
    var data = g.data.nodes;
    var leaves = [];
    var leaf = data[0];
    while (leaf.children.length > 0) {
        leaf = getNodeByID(data, leaf.children[0]);
    }
    var leafdepth = leaf.depth;
    for (var i = 0; i < data.length; i++) {
        if (data[i].depth == leafdepth) {
            if (leaves.indexOf(data[i].Genesets[0]) < 0) {
                leaves.push(data[i].Genesets[0]);
            }
            for (var j = 0; j < data[i].Genes.length; j++) {
                if (leaves.indexOf(data[i].Genes[j]) < 0) {
                    leaves.push(data[i].Genes[j]);
                }
            }
            for (var j = 0; j < data[i].species.length; j++) {
                if (leaves.indexOf(data[i].species[j]) < 0) {
                    leaves.push(data[i].species[j]);
                }
            }
        }
    }
    leaves.sort();
    console.log(leaves);
    leavesArr = [];
    for (var i = 0; i < leaves.length; i++) {
        leavesArr.push({"id": ++index, "text": leaves[i]});
    }
    return leavesArr;
}

//Find the searched path and expand the collapsed nodes
function openPaths(paths) {
    for (var i = 0; i < paths.length; i++) {
        //if (!paths[i].orphan) {//i.e. not root
        paths[i].found = true;
        if (paths[i]._children) { //if children are hidden: open them, otherwise: don't do anything
            paths[i].children = paths[i]._children;
            paths[i]._children = null;
        }
    }
    update();
}


//attaching the search functionality to the search div tag
$("#search").on("select2-selecting", function (e) {
    var roots = [];
    var paths = [];

    paths = searchTree(e.object.text);
    console.log(paths);
    if (typeof(paths) !== "undefined") {
        openPaths(paths);
    }
    else {
        alert(e.object.text + " not found!");
    }
});


//event handler for every time the force layout engine
//says to redraw everything: keeps each node in its respective column
function tick() {
    g.node.attr("transform", function (d) {
        //collide(d);
        d.x = d.depth * 200 + 100;
        //d.y = d.depth * 100 + 100;
        return ("translate(" + d.x + "," + d.y + ")");
    });

    //redraw position of every link within the link set:
    g.link
        .attr("x1", function (d) {
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
}

//retrieves statistics on the graph generated
function loadStats(graphStats) {
    //var result = {{ async_result|tojson }};
    var result = graphStats;
    var stats_url = '/results/' + result.parameters.output_prefix + '.el.profile';
    $.get(stats_url, function (data) {
        var lines = data.split('\n');
        lines = lines.slice(Math.max(lines.length - 8, 1), lines.length - 2);
        if (lines.length != 6) {
            $('#stats').append('Not available.');
            return;
        }
        values = [];
        $.each(lines, function (i, v) {
            values.push(v.split(':')[1].trim());
        });
        stats_table = $('<table></table>');
        stats_table.append(
                '<tr><td><b>Number of genes:</b></td><td>' + values[0] + '</td></tr>'
                + '<tr><td><b>Number of genesets:</b></td><td>' + values[1] + '</td></tr>'
                + '<tr><td><b>Number of bicliques:</b></td><td>' + values[3] + '</td></tr>'
                + '<tr><td><b>Number of edges:</b></td><td>' + values[2] + '</td></tr>'
                + '<tr><td><b>Max edge biclique size:</b></td><td>' + values[4] + '</td></tr>'
                + '<tr><td><b>Max vertex biclique size:</b></td><td>' + values[5] + '</td></tr>'
        );
        stats_table.find('td').css('padding', 0);
        $('#stats').append(stats_table);
    });
}

// Code for viewing the old hisim graph. Works, but needs size and
// orientation adjustments, or should be plugged into cytoscape.
//$('#old-hisim').on('click', function(event) {

//    var runhash = '{{async_result.parameters.output_prefix}}';
//    var fp = '/results/' + runhash + '.svg';

//    d3.xml(fp, "image/svg+xml", function(error, xml) {
//        if (error) {

//            console.log(fp);
//            console.log(error);
//            return;
//        }

//        var oldsvg = xml.documentElement;
//        oldsvg.setAttribute('width', '900');
//        oldsvg.setAttribute('height', '700');
//
//        $('#viz2 > svg').toggle();
//        $('#viz2').append(xml.documentElement);
//    });
//});

$('.download-image').on('click', function(event) {

    // Prevent the button from doing anything (i.e. reloading the page)
    event.preventDefault();

    var dlurl = '/downloadResult';
    // Removes 'dl-' from the id string
    var filetype = event.target.id.slice(3);
    var isOld = event.target.id.slice(0, 2) == 'ol' ? true : false;

    // Gives our SVG a white background color prior to conversion.
    // This actually changes the image the user is seeing, but they
    // shouldn't be able to notice.
    d3.select('svg')
        .insert('rect', 'g')
        .attr('width', '100%')
        .attr('height', '100%')
        .attr('fill', 'white');

    var html = d3.select("svg")
        .attr("version", 1.1)
        .attr("xmlns", "http://www.w3.org/2000/svg")
        .node().parentNode.innerHTML;

    if (isOld) {
        //var runhash = '{{async_result.parameters.output_prefix}}';
        var runhash = d3.select('#lol-hack').node().innerHTML;
        var fp = runhash + '.svg';
        var oldver = fp;

    } else {
       var oldver = '';
    }

    $.post(dlurl, {svg: html, filetype: filetype, oldver: oldver}).done(function(data) {

        if (filetype == 'png')
            var png = 'data:image/png;base64,' + data;

        else if (filetype == 'pdf')
            var png = 'data:application/pdf;base64,' + data;

        else
            var png = 'data:xml/svg;base64,' + data;

        var a = document.createElement("a");
        a.download = 'result.' + filetype;
        a.href = png;

        document.body.appendChild(a);

        a.click();
    });
});
