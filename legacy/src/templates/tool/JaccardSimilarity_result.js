   var d = {{ data | safe }}
    var count = 0;
    for(var key in d.venn_diagrams)
        if(d.venn_diagrams.hasOwnProperty(key))
            count++;
    var count_text= 0;
    var venn_d = [];
    var text_d = [];
    var gene_lab_coor = [];
     for (i = 0; i<count; i++) {
         venn_d.push([d.venn_diagrams[i].c2x,
             d.venn_diagrams[i].c2y,
             d.venn_diagrams[i].c1x,
             d.venn_diagrams[i].c1y,
             d.venn_diagrams[i].r2,
             d.venn_diagrams[i].r1]);
//                 {#        alert(d.venn_diagrams[0].text[1].text);#}
//{#             alert("i: " + i);#}
         gene_lab_coor.push([d.venn_diagrams[i].tx, d.venn_diagrams[i].ty])
         count_text= 0;
         for (var key in d.venn_diagrams[i].text) {
//{#             alert("key; " + key);#}
             if (d.venn_diagrams[i].text.hasOwnProperty(key)){
                 ++count_text;}
         }
        // alert("count: " + count_text);
         for(k=0; k <count_text; k++){
            text_d.push([d.venn_diagrams[i].text[k].text,
                d.venn_diagrams[i].text[k].tx,
                d.venn_diagrams[i].text[k].ty]);
         }
     }

     var gene_sets = [];
     gene_sets = d.genesets;
     alert (gene_lab_coor);

    var border = 1;
    var bordercolor = 'black';

    padding: {
    right: 100
    }

    var circleData = [
                        { "cx": venn_d[0][0], "cy": venn_d[0][1], "radius": venn_d[0][4], "fill" : "#66FFFF", "opacity": ".5", "cxshift" : 700, "cyshift" : 0, "label": text_d[0][0], "txshift" : text_d[0][1], "tyshift" : text_d[0][2],
                        "jval" : text_d[1][0], "jxshift" : text_d[1][1], "jyshift" : text_d[1][2], "pval" : text_d[2][0],    "pxshift" : text_d[2][1], "pyshift" : text_d[2][2], "gene_id" : gene_sets[0], "tx" : gene_lab_coor[0][0], "ty" : gene_lab_coor[0][1]},
                        { "cx": venn_d[1][0], "cy": venn_d[1][1], "radius": venn_d[1][4], "fill" : "#0000FF", "opacity": ".5", "cxshift" : 850, "cyshift" : 0, "label": text_d[3][0], "txshift" : text_d[3][1], "tyshift" : text_d[3][2]},
                        { "cx": venn_d[1][2], "cy": venn_d[1][3], "radius": venn_d[1][5], "fill" : "#FF8000", "opacity": ".5", "cxshift" : 850, "cyshift" : 0, "label": text_d[4][0], "txshift" : text_d[4][1], "tyshift" : text_d[4][2]},
                        { "cx": venn_d[2][0], "cy": venn_d[2][1], "radius": venn_d[2][4], "fill" : "#0000FF", "opacity": ".5", "cxshift" : 700, "cyshift" : 100, "label": text_d[5][0], "txshift" : text_d[5][1], "tyshift" : text_d[5][2]},
                        { "cx": venn_d[2][2], "cy": venn_d[2][3], "radius": venn_d[2][5], "fill" : "#FF8000", "opacity": ".5", "cxshift" : 700, "cyshift" : 100, "label": text_d[6][0], "txshift" : text_d[6][1], "tyshift" : text_d[6][2]},
                        { "cx": venn_d[3][0], "cy": venn_d[3][1], "radius": venn_d[3][4], "fill" : "#66FFFF", "opacity": ".5", "cxshift" : 850, "cyshift" : 100, "label": text_d[7][0], "txshift" : text_d[7][1], "tyshift" : text_d[7][2],
                         "jval" : text_d[8][0], "jxshift" : text_d[8][1], "jyshift" : text_d[8][2], "pval" : text_d[9][0],    "pxshift" : text_d[9][1], "pyshift" : text_d[9][2], "gene_id" : gene_sets[1], "tx" : gene_lab_coor[1][0], "ty" : gene_lab_coor[1][1]}] ;

     //Create the SVG Viewport
     var svgContainer = d3.select("body").append("svg")
            .attr("width",1300)
            .attr("height",1300);

    //Add circles to the svgContainer
    var circles = svgContainer.selectAll("circle")
           .data(circleData)
           .enter()
           .append("circle");

    //Add the circle attributes
    var circleAttributes = circles
            .attr("cx", function (d) { return d.cx + d.cxshift + 50; })
            .attr("cy", function (d) { return d.cy + d.cyshift + 50; })
            .attr("r", function (d) { return d.radius; })
            .style("fill", function (d) { return d.fill; })
            .style("fill-opacity", function (d) { return d.opacity })
            .attr("cxshift", function (d) { return d.cyshift;})
            .attr("cyshift", function (d) { return d.cyshift;})
            .attr("label", function (d) { return d.label;})
            .style("stroke", bordercolor)
            .attr("border", border);
//
//{#       var borderPath = svgContainer.append("rect")#}
//{#           .attr("x", 450)#}
//{#           .attr("y", 0)#}
//{#           .attr("height", 300)#}
//{#           .attr("width", 550)#}
//{#           .style("stroke", bordercolor)#}
//{#           .style("fill", "none")#}
//{#           .style("stroke-width", border);#}

    //Add the SVG Text Element to the svgContainer
    var text = svgContainer.selectAll("text")
            .data(circleData)
            .enter();

        text.append("text")
            .text(function(d){ return d.pval})
            .attr("x", function(d) { return d.cxshift + d.pxshift + 20; })
            .attr("y", function(d) { return d.cyshift+ d.pyshift + 14; });


        text.append("text")
            .text(function(d){ return d.jval})
            .attr("x", function(d) { return d.cxshift + d.jxshift + 16; })
            .attr("y", function(d) { return d.cyshift + d.jyshift + 20; });

        text.append("text")
            .text( function (d) { return d.label; })
            .attr("x", function(d) { return d.cxshift + d.txshift + 27; })
            .attr("y", function(d) { return d.cyshift+ d.tyshift + 42; });

        text.append("text")
            .text( function (d) { return d.gene_id; })
            .attr("x", function(d) { return d.tx + d.txshift + 410; })
            .attr("y", function(d) { return  d.ty + d.tyshift -230; })
            .style("font-weight", "bold");

        text.append("text")
            .text( function (d) { return d.gene_id; })
            .attr("x", function(d) { return d.ty + d.tyshift + 400; })
            .attr("y", function(d) { return  d.tx + d.txshift -280; })
            .style("font-weight", "bold");

    //Add SVG Text Element Attributes
    var textLabels = text
            .attr("font-family", "sans-serif")
            .attr("font-size", "12px")
            .attr("fill", "black");




	var urlMenu = document.getElementById("downloadType");
	urlMenu.onchange = function () {
		if(this.value!='null'){
			window.open(this.options[this.selectedIndex].value, '_blank');
		}
	}

function changeImg(sel, dl) {

	if(sel.value=='svg') {
		document.getElementById("svgFrame").src="{{ url_for('static_results', filename=async_result.parameters.output_prefix + '.svg') }}";
	}
	else if(sel.value=='png') {
		document.getElementById("svgFrame").src="{{ url_for('static_results', filename=async_result.parameters.output_prefix + '.png') }}";
	}
}

function genesetCheckboxChanged(projCheckbox, genesetCheckboxes) {
        var allChecked = true;
        genesetCheckboxes.each(function(i, gsCheckbox) {
            gsCheckbox = $(gsCheckbox);
            if(!gsCheckbox.prop('checked')) {
                allChecked = false;
                return false;
            }
        });

        projCheckbox.prop('checked', allChecked);
    }
