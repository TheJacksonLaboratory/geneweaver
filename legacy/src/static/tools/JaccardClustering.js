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
        width = 1100,
        height = 900,
        // Path to tool generated JSON data
        jsonPath = '',
        // Parsed JSON object
        jsonData = '',
        // Node color palette
        colors = [
            "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", 
            "#dd4477", "#66aa00", "#b82e2e", "#316395", "#994499", "#22aa99", 
            "#aaaa11", "#6633cc", "#e67300", "#8b0707", "#651067", "#329262", 
            "#5574a6", "#3b3eac"
        ]
        ;

    /** private **/

    /** public **/

    /*
     * Setters/getters
     */
    exports.jsonPath = function(_) {
        if (!arguments.length) return jsonPath;
        jsonPath = _;
        return exports;
    };

    return exports;
};

// Color palette for the nodes
var COLORS = [
    "#3366cc", "#dc3912", "#ff9900", "#109618", "#990099", "#0099c6", 
    "#dd4477", "#66aa00", "#b82e2e", "#316395", "#994499", "#22aa99", 
    "#aaaa11", "#6633cc", "#e67300", "#8b0707", "#651067", "#329262", 
    "#5574a6", "#3b3eac"
];

color_dict = {};

force = null;
jsonData = null;

//$(document).ready(visualize());

//$("select#visualizationType").change(function(){
//    visualize();
//});

/**
 * Generates the species key for the given visualization.
 */
var visualizeKey = function(nodes) {

    var added = {};

    for (var i = 0; i < nodes.length; i++) {

        if (nodes[i].species === undefined)
            continue;

        if (nodes[i].species in added)
            continue;

        added[nodes[i].species] = true;

        var species = nodes[i].species.split(' ');
        species = species[0][0] + '. ' + species[1];

        var key = d3.select("#d3-legend")
            .append("div")
            .attr("class", "key");

        key.append('span')
            .style('width', '20px')
            .style('height', '20px')
            .style('border', 'solid 2px #000')
            .style('background-color', 
                function() { return colorMap(nodes[i]); 
            });

        key.append('p')
            .style('font-weight', 'bold')
            .text(species);
    }
};

/**
 * Generates the force tree version of the clustering visualization.
 */
var visualizeForceTree = function(svg, jsonPath) {

    var root = null;
    link = svg.selectAll(".link");
    node = svg.selectAll(".node");
    var width = svg.attr('width');
    var height = svg.attr('height');

    //d3.json("{{ cluster_data }}", function (error, json) {
    d3.json(jsonPath, function (error, json) {

        if (error) 
            throw error;

        root = json;
        jsonData = json;

        k = Math.sqrt(json.length / (width * height));

        //var force = d3.layout.force()
        force = d3.layout.force()
            .linkDistance(function (d) {
                return d.target.level == 0 ? 150 : 50;
            })
            .charge(-50)
            .linkDistance(60)
            .gravity(0.02)
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

        var elements = flatten(json);

        //Collapse genes into genesets by default
        for (var n in elements) {
            if (elements[n].type == "geneset") {
                collapse(elements[n]);
            }
        }

        visualizeKey(elements);
        update(json);
    });

    function update(root) {
    //var update = function(root) {

        var nodes = flatten(root);
        var links = d3.layout.tree().links(nodes);
        var treeHeight = root.height;
        //var link = svg.selectAll(".link");
        //var node = svg.selectAll(".node");

        // Restart the force layout.
        force.nodes(nodes)
            .links(links)
            .start();

        link = link.data(links, function (d) {
            return d.target.id;
        });

        link.exit().remove();

        link.enter()
            .insert("line", ".node")
            .style('stroke', '#555')
            .style('stroke-width', '2px')
            .style("opacity", opac);

        node = node.data(nodes, function (d) {
            return d.id;
        });

        node.exit().remove();

        var nodeEnter = node.enter()
            .append("g")
            .attr("class", "node")
            .on("click", click)
            .call(force.drag);

        nodeEnter.append("circle")
            .attr("r", radius)
            //.attr("class", species)
            .attr('shape-rendering', 'auto')
            .style('stroke', '#000')
            .style('stroke-width', '1.5px')
            .style('fill', function(d) { return colorMap(d); })
            .style("opacity", opac);

        nodeEnter.append("text")
            .attr("dy", dist)
            .attr("dx", dist)
            .text(label);

        node.on("mouseover", mouseover);
        node.on("mouseout", mouseout);
        node.on("dblclick", dblclick);
    }

    function tick() {

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
    }

    function dist(d) {
        return -1 * (radius(d) + 5)
    }

    function radius(d) {
        if (d.type === 'collapsed-cluster')
            return d.size * 2;

        if (d.size)
            return d.size;

        return 0;
    }

    // Toggle children on click.
    function click(d) {

        console.log('shit');

        // Ignores drag events
        if (d3.event.defaultPrevented) 
            return;

        if (d.genes) {

            if (d.g_index >= d.genes.length) {
                
                d.children = null;
                d.g_index = 0;

            } else if (d.g_index + 10 < d.genes.length) {
            
                d.children = d.genes.slice(d.g_index, d.g_index + 10);
                d.g_index += 10;

            } else {

                d.children = d.genes.slice(d.g_index);
                d.g_index = d.genes.length;
            }

        } else {

            if (d.children) {

                d.type = 'collapsed-cluster';
                d._children = d.children;
                d.children = null;

            } else {

                d.type = 'cluster';
                d.children = d._children;
                d._children = null;
            }

            var nodeSelected = d3.select(this);

            //nodeSelected.select("circle").attr("class", species);
        }

        update(jsonData);
    }

    // Toggle children on click.
    function collapse(d) {
        if (d.children) {
            d.genes = d.children;
            d.g_index = 0;
            d.children = null;
        }
    }

    function mouseover(d) {

        if (d.type == "cluster") {
            var nodeSelected = d3.select(this);
            nodeSelected.select("circle").attr("r", d.size + 10);
            nodeSelected.select("text").attr("dy", "0.5em");
            nodeSelected.select("text").attr("dx", "0em");
            nodeSelected.select("text").text(d.jaccard_index.toPrecision(2));
        }
        else if (d.type == "geneset") {
            var nodeSelected = d3.select(this);
            nodeSelected.select("text").text(d.info);
        }
        else {
            var nodeSelected = d3.select(this);
            nodeSelected.select("circle").attr("r", d.size * 2);
            nodeSelected.select("text").text(d.name);
        }
    }

    function mouseout(d) {

        var nodeSelected = d3.select(this);
        nodeSelected.select("circle").attr("r", radius);
        nodeSelected.select("text").attr("dy", dist);
        nodeSelected.select("text").attr("dx", dist);
        nodeSelected.select("text").text(label);
    }

    // Returns a list of all nodes under the root.
    function flatten(root) {
        var nodes = [], i = 0;

        var recurse = function(node) {
            
            if (node.children) 
                node.children.forEach(recurse);

            if (!node.id) 
                node.id = ++i;

            nodes.push(node);
        };

        recurse(root);

        return nodes;
    }
};

function visualize(jsonPath) {

    $("div#d3-visual").empty();

    var width = document.getElementById("d3-container").offsetWidth;
    var height = document.getElementById("d3-container").offsetWidth / 1.5;

    var svg = d3.select("#d3-visual")
        .append("svg")
        .attr("width", width)
        .attr("height", height);

    if ($("select#visualizationType").val() == "forceTree") {

        visualizeForceTree(svg, jsonPath);

    } else if ($("select#visualizationType").val() == "sunburst") {
        var radius = Math.min(width, height) / 3;

        var x = d3.scale.linear()
            .range([0, 2 * Math.PI]);

        var y = d3.scale.linear()
            .range([0, radius]);

        var color = d3.scale.category20c();

        var svg = d3.select("#d3-visual").append("svg")
            .attr("width", width)
            .attr("height", height)
          .append("g")
            .attr("transform", "translate(" + width / 2 + "," + (height / 2 + 10) + ")");

        var partition = d3.layout.partition()
            .value(function(d) { return d.size; });

        var arc = d3.svg.arc()
            .startAngle(function(d) { return Math.max(0, Math.min(2 * Math.PI, x(d.x))); })
            .endAngle(function(d) { return Math.max(0, Math.min(2 * Math.PI, x(d.x + d.dx))); })
            .innerRadius(function(d) { return Math.max(0, y(d.y)); })
            .outerRadius(function(d) { return Math.max(0, y(d.y + d.dy)); });

        d3.json(jsonPath, function(error, root) {
          var g = svg.selectAll("g")
              .data(partition.nodes(root))
            .enter().append("g")
                  .on("mouseover", mouseover)
            .on("mouseout", mouseout);

          var path = g.append("path")
                  .attr("id", function(d){return d.name})
            .attr("d", arc)
            .attr("class", species)
            .attr("opacity",opac)
            .on("click", click)
            .on("dblclick",dblclick);

          var text = g.append("text")
            .attr("transform", function(d) { return "rotate(" + computeTextRotation(d) + ")"; })
            .attr("x", function(d) { return y(d.y + d.dy +.4); })
            .attr("dx", "6") // margin
            .attr("dy", ".35em") // vertical-align
            .text(label);

          function click(d) {
            // fade out all text elements
            text.transition().attr("opacity", 0);

            path.transition()
              .duration(750)
              .attrTween("d", arcTween(d))
              .each("end", function(e, i) {
                  // check if the animated element's data e lies within the visible angle span given in d
                  if (e.x >= d.x && e.x < (d.x + d.dx)) {
                    // get a selection of the associated text element
                    var arcText = d3.select(this.parentNode).select("text");
                    // fade in the text element and recalculate positions
                    arcText.transition().duration(750)
                      .attr("opacity", 1)
                      .attr("transform", function() { return "rotate(" + computeTextRotation(e) + ")" })
                      .attr("x", function(d) { return y(d.y +.25); });
                  }
              });
          }
        });

        d3.select(self.frameElement).style("height", height + "px");

        // Interpolate the scales!
        function arcTween(d) {
          var xd = d3.interpolate(x.domain(), [d.x, d.x + d.dx]),
              yd = d3.interpolate(y.domain(), [d.y, 1]),
              yr = d3.interpolate(y.range(), [d.y ? 20 : 0, radius]);
          return function(d, i) {
            return i
                ? function(t) { return arc(d); }
                : function(t) { x.domain(xd(t)); y.domain(yd(t)).range(yr(t)); return arc(d); };
          };
        }

        function computeTextRotation(d) {
          return (x(d.x + d.dx / 2) - Math.PI / 2) / Math.PI * 180;
        }

        function mouseover(d) {
            if (d.type == "cluster") {
                var nodeSelected = d3.select(this);
                nodeSelected.select("text")
                        .attr("x", function(d) { return y(d.y-.01); })
                        .text(d.jaccard_index.toPrecision(2));
            }
            else if (d.type == "geneset") {
                var nodeSelected = d3.select(this);
                var nodeName = d.name;
                svg.selectAll("text").transition().attr("opacity",function(d){return d.name != nodeName ? .2 : 1});
            }
            else if(d.type == "gene"){
                var nodeSelected = d3.select(this);
                var nodeName = d.name;
                nodeSelected.select("text").text(d.name);
                svg.selectAll("text").transition().attr("opacity",function(d){return d.name != nodeName ? .2 : 1});
            }
        }

        function mouseout(d) {
            var nodeSelected = d3.select(this);
            nodeSelected.select("text").text(label);
            svg.selectAll("text").transition().attr("opacity",1);
        }
    } else {
        var margin = {top: 80, right: 0, bottom: 10, left: 80},
                width = height;

        var x = d3.scale.ordinal().rangeBands([0, width]),
            z = d3.scale.linear().domain([0, 4]).clamp(true),
            c = d3.scale.category10().domain(d3.range(10));

        var svg = d3.select("#d3-visual").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .style("margin-left", -margin.left + "px")
          .append("g")
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

        $(".visualControl-container").append('<label for="order">Sort by:</label>')
                .append('<select id="order" class="form-control tooltip-enabled"><select>');
        $("#order").append('<option id="name" value="name">Alphabetic Order</option>')
                .append('<option id="count" value="count" selected="selected">Jaccard Similarity</option>');

        d3.json(jsonPath, function(miserables) {
          var matrix = [],
              nodes = miserables.nodes,
              n = nodes.length;

          // Compute index per node.
          nodes.forEach(function(node, i) {
            node.index = i;
            node.count = 0;
            matrix[i] = d3.range(n).map(function(j) { return {x: j, y: i, z: 0}; });
          });

          // Convert links to matrix; count character occurrences.
          miserables.links.forEach(function(link) {
            matrix[link.source][link.target].z += link.value;
            matrix[link.target][link.source].z += link.value;
            matrix[link.source][link.source].z += link.value;
            matrix[link.target][link.target].z += link.value;
            nodes[link.source].count += link.value;
            nodes[link.target].count += link.value;
          });

          // Precompute the orders.
          var orders = {
            name: d3.range(n).sort(function(a, b) { return d3.ascending(nodes[a].name, nodes[b].name); }),
            count: d3.range(n).sort(function(a, b) { return nodes[b].count - nodes[a].count; }),
            group: d3.range(n).sort(function(a, b) { return nodes[b].group - nodes[a].group; })
          };

          // The default sort order.
          x.domain(orders.name);

          svg.append("rect")
              .attr("class", "background")
              .attr("width", height)
              .attr("height", height);

          var row = svg.selectAll(".row")
              .data(matrix)
            .enter().append("g")
              .attr("class", "row")
              .attr("transform", function(d, i) { return "translate(0," + x(i) + ")"; })
              .each(row);

          row.append("line")
              .attr("x2", width);

          row.append("text")
              .attr("x", -6)
              .attr("y", x.rangeBand() / 2)
              .attr("dy", ".32em")
              .attr("text-anchor", "end")
              .text(function(d, i) { return nodes[i].name; });

          var column = svg.selectAll(".column")
              .data(matrix)
            .enter().append("g")
              .attr("class", "column")
              .attr("transform", function(d, i) { return "translate(" + x(i) + ")rotate(-90)"; });

          column.append("line")
              .attr("x1", -width);

          column.append("text")
              .attr("x", 6)
              .attr("y", x.rangeBand() / 2)
              .attr("dy", ".32em")
              .attr("text-anchor", "start")
              .text(function(d, i) { return nodes[i].name; });

          function row(row) {
            var cell = d3.select(this).selectAll(".cell")
                .data(row.filter(function(d) { return d.z; }))
                .enter().append("g")
                    .attr("id","label")
                .append("rect")
                .attr("class", "cell")
                .attr("x", function(d) { return x(d.x); })
                .attr("width", x.rangeBand())
                .attr("height", x.rangeBand())
                .style("fill-opacity", function(d) { return z(d.z); })
                .style("fill", function(d) { return nodes[d.x].group == nodes[d.y].group ? c(nodes[d.x].group) : null; })
                .on("mouseover", mouseover)
                .on("mouseout", mouseout);
          }



          function mouseover(p) {
            d3.selectAll(".row text").classed("active", function(d, i) { return i == p.y; });
            d3.selectAll(".column text").classed("active", function(d, i) { return i == p.x; });
          }

          function mouseout() {
            d3.selectAll("text").classed("active", false);
          }

            function showLabel(d) {
                var nodeSelected = d3.select(this);
                nodeSelected.select("text").text(d.value);
            }

          d3.select("#order").on("change", function() {
            clearTimeout(timeout);
            order(this.value);
          });

          function order(value) {
            x.domain(orders[value]);

            var t = svg.transition().duration(2500);

            t.selectAll(".row")
                .delay(function(d, i) { return x(i) * 4; })
                .attr("transform", function(d, i) { return "translate(0," + x(i) + ")"; })
              .selectAll(".cell")
                .delay(function(d) { return x(d.x) * 4; })
                .attr("x", function(d) { return x(d.x); });

            t.selectAll(".column")
                .delay(function(d, i) { return x(i) * 4; })
                .attr("transform", function(d, i) { return "translate(" + x(i) + ")rotate(-90)"; });
          }

          var timeout = setTimeout(function() {
            order("count");
            d3.select("#order").property("selectedIndex", 1).node().focus();
          }, 5000);
        });

    }
}

function label(d) {
    return d.type == "geneset" ? d.name : '';
}

function opac(d) {
    // Internal node opacity is a function of the jaccard coefficient between
    // two genesets. Nice, but they can be difficult to see. Leaving this here
    // in case we want to reenable it.
    //if (d.name) {
    //    return d.name == "root" ? "0"
    //            : d.type == "geneset" ? 1
    //            : d.type == "gene" ? .4
    //            : d.jaccard_index + .08;
    //}
    //return d.source.name == "root" ? "0"
    //        : d.source.type == "geneset" ? .2
    //        : d.source.jaccard_index + .08;

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

function colorMap(d) {

    // This indicates the node isn't a geneset; it's either an internal node 
    // or a geneset node that has been collapsed.
    if (d.species === undefined)
        return '#0099FF';

    if (!(d.species in color_dict)) {

        var cindex = Object.keys(color_dict).length % COLORS.length;

        color_dict[d.species] = COLORS[cindex];
    }

    return color_dict[d.species];
}

function species(d) {
    if (d.species) {
        var _species;

        if (d.species == "Macaca mulatta") {
            _species = "monkey"
        }
        else if (d.species == "Canis familiaris") {
            _species = "dog"
        }
        else if (d.species == "Mus musculus") {
            _species = "mouse"
        }
        else if (d.species == "Rattus norvegicus") {
            _species = "rat"
        }
        else if (d.species == "Drosophila melanogaster") {
            _species = "fly"
        }
        else if (d.species == "Danio rerio") {
            _species = "zebrafish"
        }
        else if (d.species == "Caenorhabditis elegans") {
            _species = "nematode"
        }
        else if (d.species == "Gallus gallus") {
            _species = "chicken"
        }
        else if (d.species == "Saccharomyces cerevisiae") {
            _species = "yeast"
        }
        else if (d.species == "Homo sapiens") {
            _species = "human"
        }

        if (!$("#" + _species + "_key").length) {
            var key = d3.select("#d3-legend").append("div")
                    .attr("id", _species + "_key")
                    .attr("class", "key");

            key.append("rect")
                    .attr("class", _species)
                    .style("width", "20px")
                    .style("height", "20px");

            key.append("p").text(_species);
        }

        return _species
    }
    else if (d.type) {
        return d.type;
    }
    else if (d.source.type == "geneset") {
        return "link " + species(d.source);
    }
    else {
        return "link " + d.source.type;
    }
}

function dblclick(d) {
    if (d.type == 'geneset') {
        window.open("/viewgenesetdetails/" + d.id);
    }
}
