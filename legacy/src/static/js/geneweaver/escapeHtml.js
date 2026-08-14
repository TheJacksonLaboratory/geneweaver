/**
 * HTML-escaping for text that is about to be injected as markup.
 *
 * Upload results (missing gene identifiers, score-type warnings, batch parse
 * errors) echo values straight from the user's file, and they are rendered with
 * jQuery `.html()` -- the bsAlerts plugin does `.html(r.message)`, and the batch
 * templates set `.html(...)` directly. Without escaping, an identifier such as
 * `<img src=x onerror=alert(1)>` in an uploaded file executes as script when the
 * result is shown back to the uploader.
 *
 * Escape each user-supplied fragment, then join with whatever trusted markup the
 * message needs (`<br />`, `<strong>`), so the separators still render.
 */
(function (window, $) {
    'use strict';

    /**
     * Escape a single value for safe inclusion in an HTML string.
     * Uses the browser's own text-to-HTML conversion rather than a regex, so it
     * cannot be defeated by an encoding the regex did not anticipate.
     *
     * @param {*} value - any value; non-strings are coerced.
     * @returns {string} the value with HTML metacharacters escaped.
     */
    function gwEscapeHtml(value) {
        if (value === null || value === undefined) {
            return '';
        }
        return $('<div>').text(String(value)).html();
    }

    /**
     * Escape every element of an array and join them with trusted separator
     * markup.
     *
     * @param {Array} values - user-supplied strings.
     * @param {string} separator - trusted markup, e.g. '<br />' or ', '.
     * @returns {string} escaped, joined HTML.
     */
    function gwEscapeHtmlJoin(values, separator) {
        if (!values || !values.length) {
            return '';
        }
        return $.map(values, gwEscapeHtml).join(separator);
    }

    window.gwEscapeHtml = gwEscapeHtml;
    window.gwEscapeHtmlJoin = gwEscapeHtmlJoin;
}(window, jQuery));
