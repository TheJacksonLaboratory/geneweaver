// specify file to load with AJAX
var param_strings1 = location.pathname.substr(19);
var param_strings = param_strings1.replace(".html", "")

var graph_url = '/results/' + param_strings + '.graphml';
var xml = '';
$.get(graph_url, function(data) { xml=data; load_cytoscape(); });

var current_hi_genes = {};
var cached_gene_info = {};
var div_id = "PhenomeMap_cyt";
var vis = {}, vis_style={};
var augment = .25;

var selected_genesets=[], selected_geneset_genes=[], selected_genes=[];

var enlarged_view = false;

// maximum number of genes allowed to be listed in each node when using the
// "show gene names" option
MAX_TOP_GENES = 20

function updateGeneList() {
	selected_genes=[];
	geneopts='';
	for( gene_sym in current_hi_genes ) {
		geneopts+='<option>'+gene_sym+'</option>';
		for( gene_id in current_hi_genes[gene_sym] ) {
			selected_genes.push(gene_id);
		}
	}
	$('#geneList').html(geneopts);

	vis.updateNodeStyles();
};
/*
$(document).ready(function() {
    // fetch projects
    $('#projList').load('/index.php?ajax_req=analyze&cmd=toolprojects');

    $('#projList').bind('change', function() {
      pj_ids = $('#projList').val().join(",");
      $.get('/index.php?ajax_req=analyze&cmd=genes&pj_ids='+pj_ids, function(data) {
        cached_gene_info = $.parseJSON(data);
        genesetopts='';
        for( gs_id in cached_gene_info.genesets ) {
          genesetopts+='<option value='+gs_id+'>GS'+gs_id+': '+cached_gene_info.genesets[gs_id].gs_name+'</option>';
        }
        $('#genesetList').html(genesetopts);
        $('#genesetList option').attr('selected', 'selected');
        $('#genesetList').trigger('change');
        });
      });



});
*/

function load_cytoscape() {
    // check that both the document has loaded and that our AJAX request is done
    //if(document.readyState !== "complete" || !xml || load_cytoscape.loaded)
        //return;
    if( !xml ) return;
    load_cytoscape.loaded = true; // sanity check: ensure only called once

//Set up visual style
    var borderColorMapper = {
        attrName: "borderColor",
        entries: [ { attrValue: "black", value: "#000000" },
            { attrValue: "orange", value: "#FF9933"},
            { attrValue: "red", value: "#FF0000" } ]
    };
    var colorMapper = {
        attrName: "color",
        entries: [ { attrValue: "black", value: "#000000" },
            { attrValue: "blue", value: "#3366CC" },
            { attrValue: "green", value: "#CCFFCC" },
            { attrValue: "purple", value: "#CCCCFF" } ]
    };

    vis_style = {
        nodes: {
            borderColor: { discreteMapper: borderColorMapper },
            color: { discreteMapper: colorMapper },
            tooltipText: "${tooltip}",
            shape: "RECTANGLE",
            size: "auto",
            borderWidth: 1,
            opacity: 1
        },
        edges: {
            color: { discreteMapper: colorMapper }
        },
        global: {
            tooltipDelay: 500
        }
    };

    var theLayout= { name: "Tree",
        options: { depthSpace: 200,
            breadthSpace: 250,
            subtreeSpace: 225 }
    };

    var draw_opt = {
        network: xml,
        edgeLabelsVisible: true,
        nodeTooltipsEnabled: true,
        visualStyle: vis_style,
        layout: theLayout
    };


    var options = {
        // where you have the Cytoscape Web SWF
        swfPath: "../../static/js/CytoscapeWeb",
        // where you have the Flash installer SWF
        flashInstallerPath: "../../static/js/playerProductInstall"
    };



    // init and draw
    vis = new org.cytoscapeweb.Visualization(div_id, options);
    var genes_to_nodes = { };
    var mesh_to_nodes = {}; // term id => term string
    var meshterm_to_ids = {}; // string(term) => comma-separated list of ids
    /////////////////////////////////////
    // Added by EJB
    var proj_to_nodes = {}; //proj_id => proj name string
    var projterm_to_ids = {}; //proj names => comma seperated list of ids
    //
    ////////////////////////////////////


    vis.ready(function(){
        //Hide desired nodes
        vis.filter("nodes", function(node){
            return node.data.color != "invisible";
        }, true);

        vis.zoomToFit();
        //vis.panEnabled(true);

        //Populate genes_to_nodes ( map gene_id => [node ids] )
        // Also populate mesh_to_nodes (map mesh_id => [node ids]),
        // and map proj_to_nodes (map proj_id => [node ids])
        var nodes = vis.nodes();
        var node_coordinates = [];
        for(var i = 0; i < nodes.length; ++i) {
            var data = nodes[i].data;
            var id = data.id;
            // multiply by 1.1 to separate the nodes horizontally a bit
            node_coordinates.push({ id: id, x: data.x*1.1, y: data.y*1.1 });
            if(data.genes){
                var genes = data.genes.split(',');
                for(var j = 0; j < genes.length; ++j) {
                    var x = genes_to_nodes[genes[j]];
                    if(!x)
                        genes_to_nodes[genes[j]] = [id];
                    else
                        x.push(id);
                }
            }
        }

        vis.layout({
            name: "Preset",
            options: { fitToScreen: true, points: node_coordinates }
        });

        //////////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////////
        //////////////////////////////////////////////////////////////
        vis.updateNodeStyles = function() {
            var highlighted_nodes = {};

            new_opacity=1.0;

            for( i=0; i<selected_genes.length; i++) {
                gene_id=selected_genes[i];

                var gnodes = genes_to_nodes[gene_id];
                for(var j in gnodes){
                    if(!(gnodes[j] in highlighted_nodes)){
                        highlighted_nodes[gnodes[j]] = {
                            borderColor: "blue",
                            color: "orange",
                            borderWidth: 4,
                            opacity: new_opacity};
                    }
                }
            }

            //nodes = vis.nodes();
            new_opacity=0.2;
            for( i=0; i<selected_geneset_genes.length; i++) {
                gene_id=selected_geneset_genes[i];

                var gnodes = genes_to_nodes[gene_id];

                for(var j in gnodes){
                    //This section colors nodes.
//                    nid=gnodes[j];
//                    var ratio = (gnodes.length)/selected_genesets.length;
//                    if (ratio > 1) { ratio = 1; }
//                    cl = d3.interpolateLab("#F3F781","#DF3A01")(ratio);
//                        highlighted_nodes[nid] = {color: cl};
//
                    nid=gnodes[j];
                    //var ratio = nodes[nid].data.value / selected_genesets.length * (1 - new_opacity);
                    var ratio = 1.0 / selected_genesets.length * (1 - new_opacity);
                    if(nid in highlighted_nodes){
                        highlighted_nodes[nid]['opacity'] += ratio;
                    } else {
                        highlighted_nodes[nid] = {opacity: new_opacity + ratio};
                    }
                    if( highlighted_nodes[nid]['opacity'] > 1.0 )
                        highlighted_nodes[nid]['opacity'] = 1.0;
                }
            }


            vis_style.nodes.opacity = new_opacity;
            vis.visualStyle( vis_style );
            vis.visualStyleBypass( {nodes: highlighted_nodes} );
        };

        $('#genesetList').bind('change', function() {
            selected_genesets=[];
            selected_geneset_genes=[];
            gsOptions = $('#genesetList option');
            for( i=0; i<gsOptions.length; i++) {
                if( gsOptions[i].selected ) {
                    gs_id=gsOptions[i].value;
                    selected_geneset_genes = selected_geneset_genes.concat(cached_gene_info.genesets[gs_id].genes);
                    selected_genesets.push(gs_id);
                }
            }

            vis.updateNodeStyles();
        });


        //Add Gene to Genes of Interest
        document.getElementById("addButton").onclick = function() {
            genequ = document.getElementById("geneInput").value;

            $.get('/index.php?ajax_req=analyze&cmd=genes&gene='+genequ, function(data) {
                new_gene_info = $.parseJSON(data);
                for( gene_sym in new_gene_info.genesyms ) {
                    current_hi_genes[gene_sym] = new_gene_info.genesyms[gene_sym];
                }
                updateGeneList();
            });
        };


    });

		//////////////////////////////////////////////////////////////

		//Open Node's URL
		function openLink(event){
			var evt = event.target;
            console.log(evt.data);
			window.open( evt.data.URL );
		}
        // Disable double click since there's no easy way to get the GSIDs in
        // this old viz format.
		//vis.addListener("dblclick", "nodes", openLink );

		//Zoom with mouse **
		vis.addListener("dblclick", function(e){
				var current_zoom = vis.zoom();
				vis.panBy( e.mouseX-($('#'+vis.containerId).width()/2.0), e.mouseY-($('#'+vis.containerId).height()/2.0) );
				vis.zoom( current_zoom += augment );
		});

    vis.draw(draw_opt);

};

//Find selected items in a given (HTML) multiselect box
function obtainSelected( optArray ){
    selectedObj = [];
    for(var i in optArray ){
        var theOpt = optArray[i];
        if( theOpt.selected ){
            selectedObj.push( theOpt.value );
        }
    }
    return selectedObj;
}               

