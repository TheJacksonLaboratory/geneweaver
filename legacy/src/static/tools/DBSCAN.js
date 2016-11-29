/**
 * Visualize the output of DBSCAN
 *
 * */

// Define colors for different species
// When zooming in, color becomes solid
var speciesToColorZoomout ={"Mus musculus":"rgba(17,91,127,0.5)","Homo sapiens":"rgba(160,168,228,0.5)","Rattus norvegicus":"rgba(79,91,182,0.5)","Danio rerio":"rgba(29,42,138,0.5)","Drosophila melanogaster":"rgba(151,230,186,0.5)","Macaca mulatta":"rgba(65,188,118,0.5)","Caenorhabditis elegans":"rgba(13,143,70,0.5)","Saccharomyces cerevisiae":"rgba(255,215,168,0.5)","Gallus gallus":"rgba(255,178,88,0.5)","Canis familiaris":"rgba(201,116,18,0.5)"};
var speciesToColorZoomin = {"Mus musculus":"rgb(17,91,127)","Homo sapiens":"rgb(160,168,228)","Rattus norvegicus":"rgb(79,91,182)","Danio rerio":"rgb(29,42,138)","Drosophila melanogaster":"rgb(151,230,186)","Macaca mulatta":"rgb(65,188,118)","Caenorhabditis elegans":"rgb(13,143,70)","Saccharomyces cerevisiae":"rgb(255,215,168)","Gallus gallus":"rgb(255,178,88)","Canis familiaris":"rgb(201,116,18)"};
var geneToCluster = {};

// Define properties for svg used by clustersInCirclesSVG
var svg = d3.select("#clustersInCirclesSVG"),
    margin = 20,
    diameter = +svg.attr("width"),
    g = svg.append("g").attr("transform", "translate(" + diameter / 2 + "," + diameter / 2 + ")");

var pack = d3.pack()
    .size([diameter - margin, diameter - margin])
    .padding(2);

//Parse the cluster to a format which d3 code can accept
//Basiclly root - cluster layer - gene layer(leaf)
function parse(cluster, geneToSpecies) {
    var clusters = {};
    clusters.name = "Clusters";
    clusters.children = cluster.map(function(e, i){
        var obj = {};
        obj.name = "Cluster" + i;
        obj.children = e.map(function(gene){
            geneToCluster[gene] = i;
            var geneObj = {};
            geneObj.name = gene;
            geneObj.size = 1;
            geneObj.colorZoomin = speciesToColorZoomin[geneToSpecies[gene]];
            geneObj.colorZoomout = speciesToColorZoomout[geneToSpecies[gene]];
            return geneObj
        });
        return obj;
    });
    return clusters;
}
//parse the json to a node-link format
//used for the second versio of visualization
//TODO if gene is not in any of the clusters
function parse2(edges, genes) {
    var graph = {};
    graph.nodes = genes.map(function(gene){
        var node = {};
        node.id = gene;
        node.group = geneToCluster[gene];
        return node;
    });
    graph.links = edges.map(function(edge){
        var link = {};
        link.source = edge[0];
        link.target = edge[1];
        link.value = 1;
        return link;
    });
    return graph;
}
//Main function to draw svg
function drawClusters(root) {
  //get the root
  root = d3.hierarchy(root)
      .sum(function(d) { return d.size; })
      .sort(function(a, b) { return b.value - a.value; });

  //set focus, will be used for zooming function
  var focus = root,
      nodes = pack(root).descendants(),
      view;

  var circle = g.selectAll("circle")
    .data(nodes)
    .enter().append("circle")
      .attr("class", function(d) { return d.parent ? d.children ? "node" : "node node--leaf" : "node node--root"; })
      .style("fill", function(d) {
          //set color for the largest circle(root)
          if(!d.parent)
              return "#96C7DF";
          //if d has children, then d is cluster layer, else d is in gene layer.
          //at gene layer, when the focus is root, it is at zoom out mode, otherwise zoom in mode
          return d.children ? "#64A5C4" : focus === root ? d.data.colorZoomout : d.data.colorZoomin; })
      //set onClick function to the circle, which is the zoom function
      .on("click", function(d) {
          if (focus !== d)
              if(!d.children)
                  zoom(d.parent), d3.event.stopPropagation();
              else {
                  zoom(d), d3.event.stopPropagation();
              }

      });
  //change the text when zooming between cluster and gene's name
  var text = g.selectAll("text")
    .data(nodes)
    .enter().append("text")
      .attr("class", "label")
      .style("fill-opacity", function(d) { return d.parent === root ? 1 : 0; })
      .style("display", function(d) { return d.parent === root ? "inline" : "none"; })
      .on("click", function(d) {
          //make the gene clickable--url will redirect to a search gene page
          if(!d.children) {
              var url = "/search/?searchbar=" + d.data.name + "&pagination_page=1&searchGenes=yes";
              location.href = url;
              d3.event.stopPropagation();  }})
      .text(function(d) {
          return d.data.name; });

  var node = g.selectAll("circle,text");

    svg
      .style("background", "white")
      .on("click", function() { zoom(root); });

  //zoom function
  zoomTo([root.x, root.y, root.r * 2 + margin]);

  function zoom(d) {
    var focus0 = focus; focus = d;

    var transition = svg.transition()
        .duration(d3.event.altKey ? 7500 : 750)
        .tween("zoom", function(d) {
          var i = d3.interpolateZoom(view, [focus.x, focus.y, focus.r * 2 + margin]);
          return function(t) { zoomTo(i(t)); };
        });
    transition.selectAll("circle")
      .filter(function(d) { return !d.children; })
        .style("fill", function(d) { return d.parent === focus ? d.data.colorZoomin : d.data.colorZoomout; });

    transition.selectAll("text")
      .filter(function(d) { return d.parent === focus || this.style.display === "inline"; })
        .style("fill-opacity", function(d) { return d.parent === focus ? 1 : 0; })
        .on("start", function(d) { if (d.parent === focus) this.style.display = "inline"; })
        .on("end", function(d) { if (d.parent !== focus) this.style.display = "none"; });
  }

  function zoomTo(v) {
    var k = diameter / v[2]; view = v;
    node.attr("transform", function(d) { return "translate(" + (d.x - v[0]) * k + "," + (d.y - v[1]) * k + ")"; });
    circle.attr("r", function(d) { return d.r * k; });
  }
};
//draw second version of visualization
var svg2 = d3.select("#clustersInWiresSVG"),
    width = +svg2.attr("width"),
    height = +svg2.attr("height");

var color1 = d3.scaleOrdinal(d3.schemeCategory20);

var simulation = d3.forceSimulation()
    .force("link", d3.forceLink().distance(10).strength(0.5))
    .force("charge", d3.forceManyBody())
    .force("center", d3.forceCenter(width / 2, height / 2));

function drawConnections(graph) {

  var tooltip = d3.select("body")
        .append("div")
        .style("position", "absolute")
        .style("z-index", "10")
        .style("visibility", "hidden");

  var nodes = graph.nodes,
      nodeById = d3.map(nodes, function(d) { return d.id; }),
      links = graph.links,
      bilinks = [];

  links.forEach(function(link) {
    var s = link.source = nodeById.get(link.source),
        t = link.target = nodeById.get(link.target),
        i = {}; // intermediate node
    nodes.push(i);
    links.push({source: s, target: i}, {source: i, target: t});
    bilinks.push([s, i, t]);
  });

  var link = svg2.selectAll(".link")
    .data(bilinks)
    .enter().append("path")
      .attr("class", "link");

  var node = svg2.selectAll(".node")
    .data(nodes.filter(function(d) { return d.id; }))
    .enter()
      .append("circle")
      .attr("class", "node")
      .attr("r", 8)
      .attr("fill", function(d) { return color1(d.group); })
      .on("mouseover", function(d){return tooltip.style("visibility", "visible").text(d.id);})
      .on("mousemove", function(){return tooltip.style("top",
    (d3.event.pageY-10)+"px").style("left",(d3.event.pageX+10)+"px");})
      .on("mouseout", function(){return tooltip.style("visibility", "hidden");})
      .call(d3.drag()
          .on("start", dragstarted)
          .on("drag", dragged)
          .on("end", dragended));

  node.append("text")
      .attr("dx", 1)
      .attr("dy", ".35em");

  simulation
      .nodes(nodes)
      .on("tick", ticked);

  simulation.force("link")
      .links(links);

  function ticked() {
    link.attr("d", positionLink);
    node.attr("transform", positionNode);
  }
}

function positionLink(d) {
  return "M" + d[0].x + "," + d[0].y
       + "S" + d[1].x + "," + d[1].y
       + " " + d[2].x + "," + d[2].y;
}

function positionNode(d) {
  return "translate(" + d.x + "," + d.y + ")";
}

function dragstarted(d) {
  if (!d3.event.active) simulation.alphaTarget(0.3).restart();
  d.fx = d.x, d.fy = d.y;
}

function dragged(d) {
  d.fx = d3.event.x, d.fy = d3.event.y;
}

function dragended(d) {
  if (!d3.event.active) simulation.alphaTarget(0);
  d.fx = null, d.fy = null;
}

//draw legend
var svg3 = d3.select("#speciesLegend");
function drawLegend() {

    var key = svg3.append('g');

    Object.keys(speciesToColorZoomout).forEach(function(name, i){
        if(i < 5) {
            key.append('circle')
                .attr('cx', 15)
                .attr('x', 15)
                .attr('cy', 28 * i + 20)
                .attr('y', 28 * i + 20)
                .attr('r', 10)
                .style('fill-opacity', 0.90)
                .style('shape-rendering', 'geometricPrecision')
                .style('stroke', '#000')
                .style('stroke-width', '2px')
                .style('fill', speciesToColorZoomout[name]);

            key.append('text')
                .attr('x', 33)
                .attr('y', 29 * i + 24)
                .text('= ' + name);
        }
        else {
            key.append('circle')
                .attr('cx', 300)
                .attr('x', 300)
                .attr('cy', 28 * (i - 5) + 20)
                .attr('y', 28 * (i - 5) + 20)
                .attr('r', 10)
                .style('fill-opacity', 0.90)
                .style('shape-rendering', 'geometricPrecision')
                .style('stroke', '#000')
                .style('stroke-width', '2px')
                .style('fill', speciesToColorZoomout[name]);

            key.append('text')
                .attr('x', 318)
                .attr('y', 29 * (i - 5) + 24)
                .text('= ' + name);
        }

    });

};