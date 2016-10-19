/**
 * Visualize the output of DBSCAN
 * There is great example I found at
 * https://bl.ocks.org/mbostock/7607535
 * */

var svg = d3.select("svg"),
    margin = 20,
    diameter = +svg.attr("width"),
    g = svg.append("g").attr("transform", "translate(" + diameter / 2 + "," + diameter / 2 + ")");

var color = d3.scaleLinear()
    .domain([-1, 5])
    .range(["hsl(152,80%,80%)", "hsl(228,30%,40%)"])
    .interpolate(d3.interpolateHcl);

var pack = d3.pack()
    .size([diameter - margin, diameter - margin])
    .padding(2);

function parse(cluster) {
    var clusters = {};
    clusters.name = "Clusters"
    clusters.children = cluster.map(function(e, i){
        var obj = {};
        obj.name = "Cluster" + i;
        obj.children = e.map(function(gene){
            var geneObj = {};
            geneObj.name = gene;
            geneObj.size = 1;
            return geneObj
        });
        return obj;
    });
    return clusters;
}

function draw(root) {
  root = d3.hierarchy(root)
      .sum(function(d) { return d.size; })
      .sort(function(a, b) { return b.value - a.value; });

  var focus = root,
      nodes = pack(root).descendants(),
      view;

  var circle = g.selectAll("circle")
    .data(nodes)
    .enter().append("circle")
      .attr("class", function(d) { return d.parent ? d.children ? "node" : "node node--leaf" : "node node--root"; })
      .style("fill", function(d) {
          if(!d.parent)
              return "rgba(117, 220, 205, 0.49)";
          return d.children ? color(d.depth) : null; })
      .on("click", function(d) {
          if (focus !== d)
              if(!d.children)
                  zoom(d.parent), d3.event.stopPropagation();
              else
                  zoom(d), d3.event.stopPropagation();
      });

  var text = g.selectAll("text")
    .data(nodes)
    .enter().append("text")
      .attr("class", "label")
      .style("fill-opacity", function(d) { return d.parent === root ? 1 : 0; })
      .style("display", function(d) { return d.parent === root ? "inline" : "none"; })
      .on("click", function(d) {
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

  zoomTo([root.x, root.y, root.r * 2 + margin]);

  function zoom(d) {
    var focus0 = focus; focus = d;

    var transition = d3.transition()
        .duration(d3.event.altKey ? 7500 : 750)
        .tween("zoom", function(d) {
          var i = d3.interpolateZoom(view, [focus.x, focus.y, focus.r * 2 + margin]);
          return function(t) { zoomTo(i(t)); };
        });

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
