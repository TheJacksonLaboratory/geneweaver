/**
 * file: shareAddGenesetsModals.js
 * desc: Code to abstract modal handling to avoid duplication
 *       Requires JQuery to be loaded before this file.
 * auth: Alexander Berger
 */


/**
 * A function to display the error modal. Page must include the generic modal.
 * @param {String} message      The error message to display on the modal
 */
var showErrorModal = function(message) {
    $('#showGenericModal').find('.modal-header').removeClass('bg-green').addClass('bg-red');
    $('#showGenericModal').find('.modal-title').html('Error!');
    $('#showGenericModal').find('#genericMessage').html(message);
    $('#showGenericModal').modal('show');
}

/**
 * Submit the modal information for 'Share w Group' and 'Add t' via AJAX
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
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">' +
                    '</button>Geneset(s) submitted successfully.</div>');
                if (v["is_guest"] == 'True') {
                    $("#guest_warning").html('<div class="alert alert-danger fade in">' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">' +
                    '</button>Now using GeneWeaver with a guest account.</div>');
                }
            }

        },
        error: function (jqXHR, textStatus, errorThrown ) {

            $(document).trigger("add-alerts", [{
                'message': "An Error (" + jqXHR + ") occurred while submitting the geneset(s)",
                'priority': 'danger'
            }]);
        }

    });
}

/**
 * Open a geneset modal and update selected genesets label
 * @param  {String} modalID     The ID of the modal to open
 * @param  {Object} or {Array}  A collection of genesets to add
 *                                if Object, will use keys to build array
 * @param  {String} modalTitle  Title to replace default modal title with
 */
var openGSModal = function(modalID, genesets, modalTitle) {
    return function() {

        // If not an array, get gs_ids from Object.keys
        if (!Array.isArray(genesets)){
            genesets = Object.keys(genesets);
        }

        // Update the modal title if specified
        if (typeof modalTitle !== 'undefined') {
            $(modalID).find('.modal-title').html(modalTitle);
        }

        // If no genesets selected, display geneneric error modal.
        if (genesets.length === 0) {
            showErrorModal('You must first select Genesets to add.');
        } else {
            var gsString = genesets.map(function(s){ return 'GS' + s; }).join(', ');
            $(modalID).find(modalID+'-label').html(gsString);
            $(modalID).find(modalID+'Value').val(genesets.join(','));
            $(modalID).modal('show');
        }
    }
}

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

        var newNameElement = $(modalID+'NewName')

        if (newNameElement.length && newNameElement.val().length > 0) {
            npn = $(modalID+'NewName').val();
        }

        if ($.isEmptyObject(selected) && $.isEmptyObject(npn)){
            $("#result").html('<div class="alert alert-danger fade in"> ' +
                    '<button type="button" class="close" data-dismiss="alert" aria-hidden="true">x' +
                    '</button>No Projects Were Selected</div>');
        } else {
            var data = {"npn": npn, "gs_id": g, "option": option}
            submitGSModalAjax(url, data);
        }
    }
}
