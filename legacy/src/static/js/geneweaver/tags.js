/**
 * file: tags.js
 * desc: Code for dynamically generating species and attribution tags. 
 *       Requires JQuery to be loaded before this file. 
 * auth: TR
 */

/**
 * Generates attribution tags using a list of colors generated from ColorBrewer
 * scales. Each attribution tag (the HTML span) should have the class:
 * att-ATTRIBUTION-LABEL, where the ATTRIBUTION-LABEL is derived from the
 * gs_abbreviation column in the attribution table. This function generates the
 * tags and alters each attribution span element.
 *
 * arguments
 *      attribs: an object mapping attribution IDs -> to their labels
 *
 * returns
 *
 */
var makeAttributionTags = function(attribs) {
    // Two, combined color Brewer palettes
    var colors = [
        'rgb(228,26,28)', 'rgb(55,126,184)', 'rgb(77,175,74)',
        'rgb(152,78,163)', 'rgb(255,127,0)', 'rgb(255,255,51)',
        'rgb(166,86,40)', 'rgb(247,129,191)', 'rgb(153,153,153)',
        'rgb(102,194,165)', 'rgb(252,141,98)', 'rgb(141,160,203)',
        'rgb(231,138,195)', 'rgb(166,216,84)', 'rgb(255,217,47)',
        'rgb(229,196,148)', 'rgb(179,179,179)'
    ];

    if (!attribs)
        return;

    for (var key in attribs) {
        attrib = attribs[key];

        $('.att-' + attrib).attr('class', 'group_name att-' + attrib);
        $('.att-' + attrib).css('background-color', colors.shift());
        $('.att-' + attrib).css('margin', '-5px 0 0 5px');
        $('.att-' + attrib).html(attrib.toUpperCase());
    }
};

/**
 * Generates all species tags using the given list of species. Each species tag
 * element should have the class sp-tag-SPID, where SPID is the species ID
 * present in the species table. 
 * 
 * arguments
 *      splist: a list of tuples; (sp_id, sp_name)
 */
var makeSpeciesTags = function(splist) {

    var colors = [
        '#fae4db', '#f9fac5', '#b5faf5', '#fae3e9', '#f5fee1', '#f4dfff',
        '#78c679', '#41b6c4', '#7bccc4', '#8c96c6', '#fc8d59'
    ];
    var borders = [
        '#eeb44f', '#d7c000', '#44fcf7', '#fca5b7', '#8fcb0a', '#b4d1fb',
        '#41ab5d', '#1d91c0', '#4eb3d3', '#8c6bb1', '#ef6548'
    ];

    if (!splist)
        return;

    for (var i = 0; i < splist.length; i++) {

        var spid = splist[i][0];
        var spname = splist[i][1];

        if (!spname)
            continue;

        // Elissa mentioned we shouldn't use common, pleb names for species
        // (and that monkey isn't technically a species), so we properly abbreviate
        // the species name.
        spname = spname.split(' ');

        if (spname.length === 1)
            continue;

        // Mus musculus and Macaca mulatta have the same abbreviation, so the
        // latter is abbreviated to M. mul instead of Mm.
        if (spname[1].slice(0, 3) == 'mul')
            spname = spname[0][0].toUpperCase() + '.' + 'mul' + '.';
        else
            spname = spname[0][0].toUpperCase() + spname[1][0].toLowerCase() + '.';

        $('.sp-tag-' + spid).attr('class', 'group_name sp-tag-' + spid);
        $('.sp-tag-' + spid).css('background-color', colors.shift());
        $('.sp-tag-' + spid).css('border', '1px solid');
        $('.sp-tag-' + spid).css('border-color', borders.shift());
        $('.sp-tag-' + spid).css('margin', '-5px 0 0 5px');
        $('.sp-tag-' + spid).html(spname);
    }
};

