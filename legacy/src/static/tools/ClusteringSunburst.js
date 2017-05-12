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
        // Parsed JSON object
        jsonData = '',
        // Maps species names to colors
        speciesColors = {},
        // Element ID of the div to draw in
        element = '#d3-visual',
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
            return '#0099FF';

        if (!(d.species in speciesColors)) {

            var cindex = Object.keys(speciesColors).length % colors.length;

            // speciesColors is a mapping of species names -> color
            speciesColors[d.species] = colors[cindex];
        }

        return speciesColors[d.species];
    }

    /** public **/

    exports.draw = function() {

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

          var g = svg.selectAll("g")
              .data(partition.nodes(jsonData))
            .enter().append("g")
                  .on("mouseover", mouseover)
            .on("mouseout", mouseout);

          var path = g.append("path")
                  .attr("id", function(d){return d.name})
            .attr("d", arc)
            .attr("fill", colorMap)
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
