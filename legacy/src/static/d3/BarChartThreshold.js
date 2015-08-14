/**
 * Created by baker on 8/12/15.
 */

// This barchart is designed primarily to chart the geneset values of
// genesets for thresholds

var InitChart = {
    draw: function (b,t,m,a) {
        var threshold1 = t;
        var threshold2 = m;
        var barData = b;
        var amts = a;

        var vis = d3.select('#threshold'),
            WIDTH = 800,
            HEIGHT = 300,
            MARGINS = {
                top: 20,
                right: 10,
                bottom: 20,
                left: 50
            },
            xRange = d3.scale.ordinal().rangeRoundBands([MARGINS.left, WIDTH - MARGINS.right], 0.1).domain(barData.map(function (d) {
                return d.x;
            })),


            yRange = d3.scale.linear().range([HEIGHT - MARGINS.top, MARGINS.bottom]).domain([0,
                d3.max(barData, function (d) {
                    return d.y;
                })
            ]),

            //xAxis = d3.svg.axis()
            //    .scale(xRange)
            //    .tickSize(5)
            //    .tickSubdivide(true),

            yAxis = d3.svg.axis()
                .scale(yRange)
                .tickSize(5)
                .orient("left")
                .tickSubdivide(true);


        //vis.append('svg:g')
        //    .attr('class', 'x axis')
        //    .attr('transform', 'translate(0,' + (HEIGHT - MARGINS.bottom) + ')')
        //    .call(xAxis);


        vis.append('svg:g')
            .attr('class', 'y axis')
            .attr('transform', 'translate(' + (MARGINS.left) + ',0)')
            .call(yAxis);


        vis.selectAll('rect')
            .data(barData)
            .enter()
            .append('rect')
            .attr('x', function (d) {
                return xRange(d.x);
            })
            .attr('y', function (d) {
                return yRange(d.y);
            })
            .attr('width', xRange.rangeBand())
            .attr('height', function (d) {
                return ((HEIGHT - MARGINS.bottom) - yRange(d.y));
            })

            .attr('fill', function (d) {

                var topy = d3.max(barData, function (d) {
                    return d.y;
                });

                maxrangey = threshold2 != 0 ? threshold2 : topy;

                if (d.y >= threshold1 && d.y <= maxrangey) {
                    return '#00CC00'
                }
                else {
                    return '#D3D3D3'
                }
            })

            .on('mouseover',function(d){
                newX =  parseFloat(d3.select(this).attr('x')) - 10;
				newY =  parseFloat(d3.select(this).attr('y')) - 5;

					tooltip
						.attr('x', newX)
						.attr('y', newY)
						.text(d.gsid+': '+ d.abr)
						.transition(200)
						.style('opacity', 1);


                d3.select(this)
                    .attr('fill','red');

            })
            .on('mouseout',function(d){
                tooltip
                    .transition(200)
                    .style('opacity', 0);
                d3.select(this)
                    .attr('fill', function (d) {
                        var topy = d3.max(barData, function (d) {
                            return d.y;
                        });

                        maxrangey = threshold2 != 0 ? threshold2 : topy;

                        if (d.y >= threshold1 && d.y <= maxrangey) {
                            return '#00CC00'
                        }
                        else {
                            return '#D3D3D3'
                        }
                    });
            });



        //Tooltip
	    tooltip = vis.append('text')
            .style('opacity', 0)
            .style('font-family', 'sans-serif')
            .style('font-weight', 'bold')
            .style('font-size', '13px');

        $("#slider").on("slide", function(e) {
            var m = e.value[0];
            vis.append("rect")
                .attr('x', function () {
                    //alert(vis.xRange(d.z));
                    return m + MARGINS.left;
                })
                .attr('y', function () {
                    return MARGINS.bottom;
                })
                .attr('width', xRange.rangeBand())
                .attr('height', function () {
                    return HEIGHT-MARGINS.bottom;
                })
                .attr('fill', "#OOOOOO")

        });


    }
};
