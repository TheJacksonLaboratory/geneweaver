/*
 *      Created by Melissa 9/17/15
 *      Modifed by Kevin 9/20/15
 */

<!-- Everything below here is for the cord plot -->

    var margin = {top: 50, right: 20, bottom: 50, left: 50};
    var width = 900 - margin.left - margin.right,
            height = 900 - margin.top - margin.bottom,
            outerRadius = Math.min(width, height) / 2 - 50,
            innerRadius = outerRadius - 24;

    var formatPercent = d3.format(".1%");

    var arc = d3.svg.arc()
            .innerRadius(innerRadius)
            .outerRadius(outerRadius);

    var layout = d3.layout.chord()
            .padding(.04)
            .sortSubgroups(d3.descending)
            .sortChords(d3.ascending);

    var path = d3.svg.chord()
            .radius(innerRadius);

    var svg = d3.select("body").append("svg")
            .attr("width", width + margin.left + margin.right)
            .attr("height", height + margin.top + margin.bottom)
            .append("g")
            .attr("id", "circle")
            //.attr("transform", "translate(" + width / 2 + "," + height / 2 + ")");
            .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

    svg.append("circle")
            .attr("r", outerRadius);

    d3.csv("../../static/cities.csv", function(cities) {
        d3.json("../../static/matrix.json", function(matrix) {

            // Compute the chord layout.
            layout.matrix(matrix);

            // Add a group per neighborhood.
            var group = svg.selectAll(".group")
                    .data(layout.groups)
                    .enter().append("g")
                    .attr("class", "group")
                    .on("mouseover", mouseover);

            // Add a mouseover title.
            group.append("title").text(function(d, i) {
                return cities[i].name + ": " + formatPercent(d.value) + " of origins";
            });

            // Add the group arc.
            var groupPath = group.append("path")
                    .attr("id", function(d, i) { return "group" + i; })
                    .attr("d", arc)
                    .style("fill", function(d, i) { return cities[i].color; });

            // Add a text label.
            var groupText = group.append("text")
                    .attr("x", 0)
                    .attr("dy", 0)
			.attr("transform", function(d) {
			    var c = arc.centroid(d),
			    	x = c[0],
			    	y = c[1],
			        // pythagorean theorem for hypotenuse
			        h = Math.sqrt(x*x + y*y);
				    return "translate(" + (x/h * 400) +  ',' +
				       (y/h * 400) +  ")";
				})
			.attr("text-anchor", function(d) {
    				// are we past the center?
    					return (d.endAngle + d.startAngle)/2 > Math.PI ?
        				"end" : "start";
				})
			.text(function(d,i) { return cities[i].name; });

//            groupText.append("textPath")
//                    .attr("xlink:href", function(d, i) { return "#group" + i; })
//                    //.attr("transform","rotate(-180)")
//                    .text(function(d, i) { return cities[i].name; });

            // Remove the labels that don't fit. :(
//            groupText.filter(function(d, i) { return groupPath[0][i].getTotalLength() / 2 - 16 < this.getComputedTextLength(); })
//                    .remove();

            // Add the chords.
            var chord = svg.selectAll(".chord")
                    .data(layout.chords)
                    .enter().append("path")
                    .attr("class", "chord")
                    .style("fill", function(d) { return cities[d.source.index].color; })
                    .attr("d", path);

            // Add an elaborate mouseover title for each chord.
            chord.append("title").text(function(d) {
                return cities[d.source.index].name
                        + " → " + cities[d.target.index].name
                        + ": " + formatPercent(d.source.value)
                        + "\n" + cities[d.target.index].name
                        + " → " + cities[d.source.index].name
                        + ": " + formatPercent(d.target.value);
            });

            function mouseover(d, i) {
                chord.classed("fade", function(p) {
                    return p.source.index != i
                            && p.target.index != i;
                });
            }
        });
    });