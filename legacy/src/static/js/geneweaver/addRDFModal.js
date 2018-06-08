/**
 * file: addRDFModal.js
 * desc: Code to abstract modal handling to avoid duplication
 *       Requires JQuery to be loaded before this file.
 * auth: Alexander Berger
 */
/*var showErrorModal = function(message) {
    $('#showGenericModal').find('.modal-header').removeClass('bg-green').addClass('bg-red');
    $('#showGenericModal').find('.modal-title').html('Error!');
    $('#showGenericModal').find('#genericMessage').html(message);
    $('#showGenericModal').modal('show');
};*/

$.getScript("/static/js/geneweaver/showErrorModal.js");

/**
 * Submit the RDF Annotation
 * @param {String} url  The url to which the ajax call will be made
 * @param {Object} data The data which will be submitted via ajax
 */
var submitModalAjax = function(url, data) {
    $.ajax({
        type: "POST",
        url: url,
        data: data,
        traditional: true,
        success: function (data) {
            var v = data;
            if (v["error"]) {
                console.log("Error returned " + v['error']);
                $("#result").html('<div class="alert alert-danger fade in">' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>' + v['error'] + '</div>');
            } else {
                $("#result").html('<div class="alert alert-success fade in">' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>RDF Annotation Successfully Added.</div>');
            }
            $('#annotation-list').DataTable().ajax.reload();
            $("#tree").dynatree("getTree").reload();

            checkedOnts = [];
            disableActionButtons(true);

        },
        error: function (jqXHR, textStatus, errorThrown ) {

            $(document).trigger("add-alerts", [{
                'message': "An Error (" + jqXHR + ") occurred while adding RDF annotation",
                'priority': 'danger'
            }]);
        }

    });
};

/**
 * A function to open the RDF modal
 * @param modalID - the ID of the modal to open
 * @param gsid - the Geneset ID of the RDF Annotation
 * @param oids - the Ontology ID of the RDF Annotation
 * @param relation_onts - An array of the relationship_ontologies
 * @param modalTitle - the title of the modal
 * @returns {Function} a function that can be attached to an .on('click', or the like
 */
var openRDFModal = function(modalID, gsid, oids, relation_onts, modalTitle) {
    return function() {

        if (!Array.isArray(oids)) { oids = [oids]; }

        // Update the modal title if specified
        if (typeof modalTitle !== 'undefined') { $(modalID).find('.modal-title').html(modalTitle); }

        // If no genesets selected, display geneneric error modal.
        if (typeof gsid === 'undefined' || typeof oids === 'undefined') {
            showErrorModal('Something went wrong. Couldn\'t access Ontology ID, GeneSet ID or both.');
        } else if (oids.length < 1) {
            showErrorModal('Please select at least one Ontology to add an RO Term to.')
        } else {
            var gs_id_el = $(modalID).find('#gsid'),
                ont_ids_label = $(modalID).find('#addRDFOntologies-label'),
                ont_ids_label_string = oids.join(', '),
                rdf_message = $(modalID).find('addRDFMessage');
            gs_id_el.html('Geneset: GS'+gsid);
            gs_id_el.data('gs_id', gsid);
            ont_ids_label.html(ont_ids_label_string);
            ont_ids_label.data('ont_id', oids);
            rdf_message.html('Annotation will be added to the following Ontologies for geneset with ID: '+gsid);
            $('#roSelect').select2({
                data: relation_onts,
                placeholder: 'Relationship Ontology',
                allowClear: true,
                width: '100%'
            });
            $(modalID).modal('show');
            $(modalID).find('input').focus();
        }
    }
};

/**
 * Collect data from modal for ajax call, or display error if needed
 * @param  {String} modalID     The ID of the modal to submit
 * @param  {String} url         The url to which the ajax call will be made
 */
var submitRDFModal = function(modalID, url) {
    return function() {
        //var selected = $(modalID+' select').val().map(Number);
        var gs_id = $(modalID).find('#gsid').data('gs_id'),
            ont_ids = $(modalID).find('#addRDFOntologies-label').data('ont_id'),
            ro_ont_id = $('#roSelect').val();

        var data = {'gs_id': gs_id, 'ont_ids': ont_ids, 'ro_ont_id': ro_ont_id};
        submitModalAjax(url, data);
    }
};

