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
var submitGSModalAjax = function(url, data) {
    $.ajax({
        type: "GET",
        url: url,
        data: data,
        success: function (data) {
            var v = JSON.parse(data);
            if (v["error"] != 'None') {
                console.log("Error returned " + v['error']);
                $("#result").html('<div class="alert alert-danger fade in">' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>' + v['error'] + '</div>');
            } else {
                console.log('no error');
                $("#result").html('<div class="alert alert-success fade in">' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>RDF Annotation Successfully Added.</div>');
            }

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
 * @param oid - the Ontology ID of the RDF Annotation
 * @param relation_onts - An array of the relationship_ontologies
 * @param modalTitle - the title of the modal
 * @returns {Function} a function that can be attached to an .on('click', or the like
 */
var openRDFModal = function(modalID, gsid, oid, relation_onts, modalTitle) {
    return function() {

        // Update the modal title if specified
        if (typeof modalTitle !== 'undefined') { $(modalID).find('.modal-title').html(modalTitle); }

        // If no genesets selected, display geneneric error modal.
        if (typeof gsid === 'undefined' || typeof oid === 'undefined') {
            showErrorModal('Something went wrong. Couldn\'t access Ontology ID, GeneSet ID or both.');
        } else {
            $(modalID).find('#gsid').html('Geneset: GS'+gsid);
            $(modalID).find('#oid').html('Ontology ID: GO:'+oid);
            /*$('#roSelect').select2({
                ajax: '/relationshipOntologies',
                dataType: 'json'
            });*/
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
var submitGSModal = function(modalID, url) {
    return function() {
        //var selected = $(modalID+' select').val().map(Number);
        var selected = $(modalID+' select').val();

        if (selected)
            selected = selected.map(Number);

        var option = JSON.stringify(selected);
        var g = $(modalID+'Value').val();
        var npn = null;

        var newNameElement = $(modalID+'NewName');

        if (newNameElement.length && newNameElement.val().length > 0) {
            npn = $(modalID+'NewName').val();
        }

        if ($.isEmptyObject(selected) && $.isEmptyObject(npn)){
            $("#result").html('<div class="alert alert-danger fade in"> ' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>No Projects Were Selected</div>');
        } else {
            var data = {"npn": npn, "gs_id": g, "option": option};
            submitGSModalAjax(url, data);
        }
    }
};