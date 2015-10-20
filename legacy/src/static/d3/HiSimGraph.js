 //Notes:
        // STILL VERY MUCH IN PROGRESS
        // Initially borrowed from http://bl.ocks.org/mbostock/1093130
        //      with heavy modification. Creates a DAG and displays it in a tree
        //      shaped manner, where each child node can have multiple parents.
        //Notes:
        // * Each dom element is using
        //   children to store refs to expanded children
        //   _children to store refs to collapsed children


        //root
        var g = {
            data: null,
            force: null
        };


        //initializa
        $(function () {

            //use a global var for the data:
            g.data = data;
            /*
            var data = (function () {
                var json = null;
                $.ajax({
                    "async": false,
                    "global": false,
                    "url": "../../../../results.TestOutput.hisim.json",
                    "dataType": "json",
                    "success": function (data) {
                     json = data;
                    }
                });
                return json;
            } );
            */

            console.log("DATA = " + JSON.stringify(data));
            var width = 960,
                    height = 1000;

            var r = 6,
                    fill = d3.scale.category20();

            var diagonal = d3.svg.diagonal()
                .projection(function(d) { return [d.y, d.x]; });


            //Create a sized SVG surface within viz:
            var svg = d3.select("#viz2")
                    .append("svg")
                    .attr("width", width)
                    .attr("height", height);

            g.link = svg.selectAll("path.link"),
                    g.node = svg.selectAll(".node");


            //Create a graph layout engine:
            g.force = d3.layout.force()
                    .nodes(g.data.nodes)
                    .links(getLinks(g.data.nodes))
                    .linkDistance(function (link) {
                        //console.log("LINK DISTANCE OUTPUT HERE: " + JSON.stringify(link));
                        //return 50;
                        return ((link.target.depth - link.source.depth) * 40);
                    })
                    .linkStrength(function (link) {
                        return 1 / ((link.target.depth - link.source.depth) * 2);
                    })
                    .charge(-130)
                    .chargeDistance(80)
                    .gravity(0.05)
                    .size([width, height])
                //that invokes the tick method to draw the elements in their new location:
                    .on("tick", tick);


            //Initialize positions of tree elements to reduce tangling caused by random initialization
            nodes = flatten(g.data.nodes);
            var nextdepths = [0];
            for (i = 0; i < nodes.length; i++) {
                while(nodes[i].depth > nextdepths.length - 1){
                    nextdepths.push(0);
                }
                //if(nodes[i].depth == 0){
                //    nodes[i].fixed = true;
                //}
                nodes[i].x = nodes[i].depth * 100 + 50;
                nodes[i].y = nextdepths[nodes[i].depth] * 20 + 100;
                nextdepths[nodes[i].depth]++;
            }


            //Draw the graph:
            //Note that this method is invoked again
            //when clicking nodes:
            update();


        });


        //invoked once at the start,
        //and again when from 'click' method
        //which expands and collapses a node.

        function update() {
            var width = 960,
                    height = 500;

            //iterate through original nested data, and get one dimension array of nodes.
            var nodes = flatten(g.data.nodes);
            console.log(nodes.length + " nodes to draw");
            for (i = 0; i < nodes.length; i++) {
                console.log("NODE " + nodes[i].id + ": " + nodes[i].children);
            }





            //Each node extracted above has a children attribute.
            //from them, we can use a tree() layout function in order
            //to build a links selection.

            var links = getLinks(nodes);
            //console.log(links.length + " links to draw");
            //console.log(JSON.stringify(g.force.links()));
            for (i = 0; i < links.length; i++) {
                //console.log(JSON.stringify(links[i])) + "distance: ";
                //console.log("LINK " + i + ": " + links[i].source + "\t" + links[i].target);
            }

            // pass both of those sets to the graph layout engine, and restart it
            g.force.nodes(nodes)
                    .links(links)
                    .start();
            //-------------------
            // create a subselection, wiring up data, using a function to define
            //how it's supposed to know what is appended/updated/exited

                                    //console.log("G.LINK (before): \n" + JSON.stringify(g.link));

            g.link = g.link.data(links);

                                                ///console.log("G.LINK (middle): \n" + JSON.stringify(g.link));

            //Get rid of old links:
            g.link.exit().remove();


             /*var diagonal = d3.svg.diagonal()
                .projection(function(d) { return [d.y, d.x]; });*/

            //Build new links by adding new svg lines:
            g.link
                    .enter()
                    .insert("line", ".node")
                    .attr("class", "link");


              /*g.link
                    .enter()
                    .insert("path", "g")
                    .attr("class", "link")
                    .attr("d", function(d) {
                        console.log(d);
                        var o = {x: d.source.x, y: d.source.y};
                        return diagonal({source: o, target: o});
                    });*/

            // create a subselection, wiring up data, using a function to define
            //how it's suppossed to know what is appended/updated/exited
            g.node = g.node.data(nodes, function (d) {
                return d.id;
            });
            //Get rid of old nodes:
            g.node.exit().remove();
            //-------------------
            //create new nodes by making groupd elements, that contain circls and text:
            var nodeEnter = g.node.enter()
                    .append("g")
                    .attr("class", "node")
                    .on("click", click)
                    .call(g.force.drag);
            //circle within the single node group:
            nodeEnter.append("circle")
                     .attr("r", 4.5);

            //text within the single node group:
            nodeEnter.append("text")
                    .attr("dy", "-2em")
                    .attr("dx", function(d) { return (d.children.length > 0) ? "-1em" : "1em"; })
                    .attr("text-anchor", function(d) { return (d.children.length > 0) ? "end" : "start"; })
                    .style('color', textColor)
                    .text(function (d) {
                        return d.name;
                    });
            //All nodes, do the following:
            g.node.select("circle")
                    .style("fill", color) //calls delegate
                    .style("stroke", outerRingColor);
            //-------------------

            //g.node.fontcolor(textColor)
            g.node.select("text").attr("fill",textColor);

        }


        // Invoked from 'update'.
        // The original source data is not the usual nodes + edge list,
        // but rather an adjacency list of nodes and their children.
        // We need a list of nodes + links for the force layout engine.
        // So returns a list of all nodes under the root.
        function flatten(data) {
            var nodes = [];
            function recurse(node) {
                if (!getNodeByID(nodes, node.id)) nodes.push(node);
                if (node.children.length > 0) {
                    for (var i = 0, count = node.children.length; i < count; i++) {
                        var nextNode = getNodeByID(data, node.children[i]);
                        recurse(nextNode);
                    }
                }
            }

            for(var i = 0, len = data.length; i < len; i++){
                if(data[i].depth == 0) {
                    recurse(data[i]);
                }
            }


            return nodes;
        }


        function getNodeByID(nodes, wanted_id) {

            for (var i = 0; i < nodes.length; i++) {
                if (nodes[i].id == wanted_id) {
                    return nodes[i];
                }
            }
        }


        function getLinks(nodes) {

            var links = [];
            for (var i = 0; i < nodes.length; i++) {
                var n = nodes[i];
                for (var j = 0; j < n.children.length; j++) {
                    var link = {
                        //source: n
                        //target: getNodeByID(nodes, n.children[j])

                        source: n,
                        target: getNodeByID(nodes, n.children[j])
                    };
                    //console.log("node: " + n.id + "\n\tchildren: " + n.children[j]);
                    //console.log(link.source + "\t" + link.target);
                    links.push(link);
                }
            }

            return links;
        }



        //Invoked from 'update'
        //Return the color of the node
        //based on the children value of the
        //source data item: {name=..., children: {...}}
        function color(d) {
            return d._children ? "#3182bd" // collapsed package
                    :
                    d.children.length > 0 ? "#c6dbef" // expanded package
                            :
                            "#ffffff"; // leaf node
        }


        function outerRingColor(d) {
            if (d.emphasis) {
                return "#33AD33";
            }
            else return "default";
        }

        function textColor(d) {
            if (d.emphasis) {
                return '#CC0000';
            }
            else return 'default';
        }


        function click(d) {
            if (d3.event.defaultPrevented) return; // ignore drag
            if (d.children.length > 0) {
                console.log("collapsing node " + d.name + " (" + d.id + ")");
                d._children = d.children;
                d.children = [];
                console.log("children: " + d.children);
                console.log("_children:" + d._children);
            } else if (d._children){
                console.log("expanding node " + d.name + " (" + d.id + ")");
                d.children = d._children;
                d._children = null;
                console.log("children: " + d.children);
                console.log("_children:" + d._children);
            }
            nodes = flatten(g.data.nodes);
            var nextdepths = [0];
            for (i = 0; i < nodes.length; i++) {
                while(nodes[i].depth > nextdepths.length - 1){
                    nextdepths.push(0);
                }
                //if(nodes[i].depth == 0){
                //    nodes[i].fixed = true;
                //}
                nodes[i].py = nextdepths[nodes[i].depth] * 20 + 100;
                nodes[i].y = nextdepths[nodes[i].depth] * 20 + 100;
                nextdepths[nodes[i].depth]++;
            }
            //
            update();
        }

        //event handler for every time the force layout engine
        //says to redraw everything:
        function tick() {

            g.node.attr("transform", function (d) {
                d.x = d.depth * 200 + 50;
                return ("translate(" + d.x + "," + d.y + ")");
            });
            //redraw position of every link within the link set:

            g.link.attr("x1", function (d) {
                        return d.source.x;Cap
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
            //same for the nodes, using a functor:


        }



        var data = {
            "nodes": [
                {"id": 0, "name": "flare", "children": [1], "depth": 0, "emphasis": true},                  //0
                {"id": 1, "name": "analytics", "children": [2, 7, 13], "depth": 1},              //1
                {"id": 2, "name": "cluster", "children": [3, 4, 5, 6, 15], "depth": 2},                //2
                {"id": 3, "name": "AgglomerativeCluster", "children": [], "depth": 3},   //3
                {"id": 4, "name": "CommunityStructure", "children": [], "depth": 3},     //4
                {"id": 5, "name": "HierarchicalCluster", "children": [], "depth": 3},    //5
                {"id": 6, "name": "MergeEdge", "children": [], "depth": 3},              //6
                {"id": 7, "name": "graph", "children": [8, 9, 10, 11, 12, 15], "depth": 2},                  //7
                {"id": 8, "name": "BetweennessCentrality", "children": [], "depth": 3},  //8
                {"id": 9, "name": "LinkDIstance", "children": [], "depth": 3},           //9
                {"id": 10, "name": "MaxFlowMinCut", "children": [], "depth": 3},          //10
                {"id": 11, "name": "ShortestPaths", "children": [], "depth": 3},          //11
                {"id": 12, "name": "SpanningTree", "children": [], "depth": 3},           //12
                {"id": 13, "name": "optimization", "children": [14, 15], "depth": 2},           //13
                {"id": 14, "name": "AspectRatioBanker", "children": [], "depth": 3},       //14
                {"id": 15, "name": "TestLeaf", "children": [], "depth": 3, "emphasis": true}       //14
            ]
        };