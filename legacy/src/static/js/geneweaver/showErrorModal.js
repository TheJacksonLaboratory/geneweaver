/**
 * file: showErrorModal.js
 * desc: Code to abstract modal handling to avoid duplication
 *       Requires JQuery to be loaded before this file.
 * auth: Alexander Berger
 */

/**
 * A function to display the error modal. Page must include the generic modal.
 * You must include showGenericMessage.html
 * @param {String} message      The error message to display on the modal
 */
var showErrorModal = function(message) {
    $('#showGenericModal').find('.modal-header').removeClass('bg-green').addClass('bg-red');
    $('#showGenericModal').find('.modal-title').html('Error!');
    $('#showGenericModal').find('#genericMessage').html(message);
    $('#showGenericModal').modal('show');
};