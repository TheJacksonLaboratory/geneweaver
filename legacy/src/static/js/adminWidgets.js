function genesets_per_tier() {
    $.ajax({
        type: "GET",
        url: "../admin/genesetspertier",
        success: function(return_data) {
            //alert(return_data);
            var array = JSON.parse(return_data);
            //alert(array.1);	
	     
            var data = [0,1,40,2];

            var margin = {
                    top: 30,
                    right: 0,
                    bottom: 0,
                    left: 30
                },
                width = 420,
                barHeight = 20,
                height = barHeight * data.length;

            var x = d3.scale.linear()
                .domain([0, d3.max(data)])
                .range([0, width]);

            var xAxis = d3.svg.axis()
                .scale(x)
                .orient("top")
                .tickSize(-height);

            var chart = d3.select(".chart")
                .attr("width", width + margin.left + margin.right)
                .attr("height", height + margin.top + margin.bottom)
                .append("g")
                .attr("transform", "translate(" + margin.left + "," + margin.top + ")");

            chart.append("g")
                .attr("class", "bars")
                .selectAll("rect")
                .data(data)
                .enter().append("rect")
                .attr("y", function(d, i) {
                    return i * barHeight;
                })
                .attr("height", barHeight - 1)
                .attr("width", x);

            chart.append("g")
                .attr("class", "axis")
                .call(xAxis)
                .select(".tick line")
                .style("stroke", "#000");
        }
    });
}
