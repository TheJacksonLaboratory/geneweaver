/**
 * Visualize the output of DBSCAN
 *
 * http://d3-legend.susielu.com/
 * */

var svg = d3.select("svg"),
    margin = 20,
    diameter = +svg.attr("width"),
    g = svg.append("g").attr("transform", "translate(" + diameter / 2 + "," + diameter / 2 + ")");

var color = d3.scaleLinear()
    .domain([-1, 5])
    .range(["hsl(152,80%,80%)", "hsl(228,30%,40%)"])
    .interpolate(d3.interpolateHcl);

var species = "Drosophila melanogaster";

var geneToSpecies = {"Arr1":species, "car":species, "veli":species, "Prp31":species, "baz":species, "CdsA":species, "Arr2":species, "Calx":species, "Cerk":species, "Pis":species};
var speciesToColorZoomout = {"Drosophila melanogaster":"rgba(255, 220, 124, 0.63)", "abc":"red"};
var speciesToColorZoomin = {"Drosophila melanogaster":"rgb(255, 220, 124)","abc":"red"};

var ordinal = d3.scaleOrdinal()
  .domain(Object.keys(speciesToColorZoomin))
  .range(Object.keys(speciesToColorZoomin).map(function(e){return speciesToColorZoomin[e]}));

var pack = d3.pack()
    .size([diameter - margin, diameter - margin])
    .padding(2);



function parse(cluster) {
    var clusters = {};
    clusters.name = "Clusters";
    clusters.children = cluster.map(function(e, i){
        var obj = {};
        obj.name = "Cluster" + i;
        obj.children = e.map(function(gene){
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
              return "#96C7DF";
          return d.children ? "#64A5C4" : focus === root ? d.data.colorZoomout : d.data.colorZoomin; })
      .on("click", function(d) {
          if (focus !== d)
              if(!d.children)
                  zoom(d.parent), d3.event.stopPropagation();
              else {
                  zoom(d), d3.event.stopPropagation();
              }

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

    //legend
    svg.append("g")
      .attr("class", "legendOrdinal")
      .attr("transform", "translate(20,20)");

    var legendOrdinal = d3.legendColor()
      .shape("path", d3.symbol().type(d3.symbolCircle).size(500)())
      .shapePadding(10)
      .scale(ordinal);

    svg.select(".legendOrdinal")
      .call(legendOrdinal);

  zoomTo([root.x, root.y, root.r * 2 + margin]);

  function zoom(d) {
    var focus0 = focus; focus = d;

    var transition = d3.transition()
        .duration(d3.event.altKey ? 7500 : 750)
        .tween("zoom", function(d) {
          var i = d3.interpolateZoom(view, [focus.x, focus.y, focus.r * 2 + margin]);
          return function(t) { zoomTo(i(t)); };
        });
    transition.selectAll("circle")
      .filter(function(d) { return !d.children; })
        .style("fill", function(d) { return d.parent === focus ? d.data.colorZoomin : d.data.colorZoomout; });
        // .append("title")
        //   .text(function(d) {
        //     return d.data.colorZoomin
        //         + "\ngene: " + d.data.name;
        //   });

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

function drawLegend() {
var quantize = d3.scaleQuantize()
  .domain([ 0, 0.15 ])
  .range(d3.range(9).map(function(i) { return "q" + i + "-9"; }));

var svg = d3.select("svg");

svg.append("g")
  .attr("class", "legendQuant")
  .attr("transform", "translate(20,20)");

var legend = d3.legendColor()
  .labelFormat(d3.format(".2f"))
  .useClass(true)
  .scale(quantize);

svg.select(".legendQuant")
  .call(legend);

}
