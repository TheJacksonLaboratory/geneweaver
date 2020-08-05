from itertools import chain
import json
import os
import sys
import uuid

import celery.states as states
import flask

import geneweaverdb as gwdb
import tools.toolcommon as tc


TOOL_CLASSNAME = 'MSET'
mset_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)
HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']

SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
                 'Canis familiaris']

BACKGROUND_NAMES = ["CTD", "NIF", "ABA", "GWAS", "DRG", "GO", "MP", "HP", "MESH", "KEGG", "MSigDB", "PC", "OMIM",
                 "GTex", "Entrez", "Ensembl Gene", "Ensembl Protein", "Ensembl Transcript", "Unigene",
                 "Gene Symbol", "Unannotated", "MGI", "HGNC", "RGD", "ZFIN", "FlyBase", "Wormbase", "SGD",
                 "miRBase", "CGNC"]


@mset_blueprint.route('/MSET.html', methods=['POST'])
def run_tool():

    user = flask.g.user
    if not user:
        flask.flash('Please log in to run the tool')
        return flask.redirect('/analyze')

    form = flask.request.form
    number_of_trials = form.get('MSET_NumberofTrials', 5000)
    selected_geneset_ids = tc.selected_geneset_ids(form)
    alt_genesets = form.get('genesets')
    if alt_genesets:
        alt_genesets = alt_genesets.split(' ')
        selected_geneset_ids = alt_genesets if len(alt_genesets) == 2 else selected_geneset_ids

    try:
        group_1_gsid = selected_geneset_ids[0]
        group_2_gsid = selected_geneset_ids[1]
    except IndexError:
        flask.flash("Error: Please select two distinct gene sets.")
        return flask.redirect('/analyze')

    # Make sure we don't have too many genesets
    if len(selected_geneset_ids) > 2:
        flask.flash("Error: Please select at most two gene sets before running MSET.")
        return flask.redirect('/analyze')

    # Try running the MSET tool with the args provided
    try:
        async_result, task_id, tool = run_tool_exec(group_1_gsid, group_2_gsid, number_of_trials, user.user_id)
    except ValueError as e:
        flask.flash(e.message)
        return flask.redirect('/analyze')

    # Render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    try:
        response = flask.make_response(tc.render_tool_pending(async_result, tool))
    except Exception as e:
        sys.stderr.write(str(e))
        raise Exception('Problem generating flask response')
    response.status_code = 303
    response.headers['location'] = new_location

    return response


@mset_blueprint.route('/api/tool/run-MSET.html', methods=['GET'])
def run_tool_api(apikey, num_samples, geneset_1, geneset_2):

    user_id = gwdb.get_user_id_by_apikey(apikey)

    # Try running the MSET tool with the args provided
    try:
        async_result, task_id, tool = run_tool_exec(geneset_1, geneset_2, num_samples, user_id)
    except ValueError as e:
        flask.flash(e.message)
        return flask.redirect('/analyze')

    return task_id


def run_tool_exec(gs_1, gs_2, num_samples, user_id):
    species = gwdb.get_all_species()
    selected_geneset_ids = [gs_1, gs_2]
    group_1_gsid = gs_1
    group_2_gsid = gs_2

    group_1 = gwdb.get_geneset(group_1_gsid, user_id)
    group_2 = gwdb.get_geneset(group_2_gsid, user_id)

    # We can't use deleted genesets
    if group_1 is None or group_2 is None:
        raise ValueError("Error: Problem accessing one or both of the selected genesets")

    # Genesets can't use microarray identifiers
    if group_1.gene_id_type > 0 or group_2.gene_id_type > 0:
        raise ValueError("Warning: MSET cannot currently utilize microarray gene identifiers. Please select a different geneset.")

    # Genesets need to be the same species
    if not group_1 and group_2 or group_1.sp_id != group_2.sp_id:
        raise ValueError("Warning: MSET cannot currently perform analysis across species. Please only use genesets from the same species.")

    # Determine which background file represents each group
    gene_id_types = {item['gdb_id']: item['gdb_name'] for item in gwdb.get_gene_id_types(group_1.sp_id)}
    try:
        group_1_bg_file = gene_id_types[abs(group_1.gene_id_type)].replace(' ', '') +\
                          species[group_1.sp_id].replace(' ', '') +\
                          'BG.txt'
        group_2_bg_file = gene_id_types[abs(group_2.gene_id_type)].replace(' ', '') +\
                          species[group_2.sp_id].replace(' ', '') +\
                          'BG.txt'
    except KeyError:
        raise ValueError("Error: Geneweaver couldn't determine the background for selected gene sets.")

    # The gs_dict is used to store geneset data crucial to running MSET
    gs_dict = {
        'group_1_gsid': group_1_gsid,
        'group_2_gsid': group_2_gsid,
        'group_1_genes': [gid[0] for gid in gwdb.get_genesymbols_by_gs_id(group_1_gsid)],
        'group_1_background': group_1_bg_file,
        'group_2_genes': [gid[0] for gid in gwdb.get_genesymbols_by_gs_id(group_2_gsid)],
        'group_2_background': group_2_bg_file,
        'sp_id': group_1.sp_id,
        'species': species[group_2.sp_id]
    }


    task_id = str(uuid.uuid4())
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    # Create a good description of the tool run
    desc = '{} ({}) '.format(tool.name, num_samples)
    desc += 'on GeneSets {} and {}'.format('GS:{}'.format(group_1.geneset_id), 'GS:{}'.format(group_2.geneset_id))

    params = {'MSET_NumberofSamples': num_samples,
              'user_id': user_id}

    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params),
        tool.name,
        desc,
        desc)

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': params,
            'gs_dict': gs_dict,
        },
        task_id=task_id
    )
    return async_result, task_id, tool

@mset_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    user = flask.g.user
    if not user:
        flask.flash('Please log in to view your results')
        return flask.redirect('/analyze')

    if async_result.state == states.FAILURE:
        async_result = json.loads(async_result.result)
        if async_result['error']:
            flask.flash(async_result['error'])
        else:
            flask.flash('An unkown error occurred. Please contact a GeneWeaver admin.')
        return flask.redirect('/analyze')
    elif async_result.state not in states.READY_STATES:
        return tc.render_tool_pending(async_result, tool)

    async_result = json.loads(async_result.result)

    results = {'error': None, 'message': None}

    # Return if results not available
    mset_output = async_result.get("mset_data")
    if not mset_output:
        flask.flash('An error occurred with the request, and your results are not available. '
                    'Please contact a GeneWeaver administrator for help or try again. {}'.format(async_result.get('error', [])))
        rurl = flask.request.referrer if 'MSET-result' not in flask.request.referrer else '/analyze'
        return flask.redirect(rurl)

    ## MSET Histogram
    if async_result.get("mset_hist"):
        hist_data = async_result.get("mset_hist")
        hist_amounts = [int(k) for k in hist_data.keys()]
        min_val = min([min(hist_amounts), int(mset_output["List 1/2 Intersect"])])
        max_val = max([max(hist_amounts), int(mset_output["List 1/2 Intersect"])])
        density_data = [{'intersectSize': k, 'frequency': float(hist_data.get(str(k), 0))}
                        for k in range(min_val, max_val+2)]
        density_data.sort(key=lambda elem: elem['intersectSize'])
        results['density_data'] = density_data
        del async_result['mset_hist']

    ## MSET Results
    group_1_gsid = async_result["parameters"]["gs_dict"].get("group_1_gsid")
    group_2_gsid = async_result["parameters"]["gs_dict"].get("group_2_gsid")
    mset_results = {
        'p_value': mset_output['P-Value'],
        'universe_size': int(mset_output["Universe Size"]),
        'group_1_in_universe': int(mset_output["List 1 / Universe"]),
        'group_2_in_universe': int(mset_output["List 2 / Universe"]),
        'selected_intersect_size': mset_output["List 1/2 Intersect"],
        'method': mset_output["Method"],
        'num_trials': mset_output["Num Trials"],
        'trials_gt_int': mset_output["Trials gt intersect"],
        'alternative': mset_output["Alternative"],
        'group_1_gsid': group_1_gsid,
        'group_2_gsid': group_2_gsid,
        'group_1': gwdb.get_geneset(group_1_gsid, user.user_id).name if group_1_gsid else None,
        'group_2': gwdb.get_geneset(group_2_gsid, user.user_id).name if group_2_gsid else None,
        'geneset': gwdb.geneset_intersection_values_for_mset(group_1_gsid, group_2_gsid) if group_1_gsid and group_2_gsid else [],
        'sp_id': async_result["parameters"]["gs_dict"].get("sp_id"),
        'species': async_result["parameters"]["gs_dict"].get("species")
    }
    results.update(mset_results)
    del async_result['mset_data']

    return flask.render_template(
        'tool/MSET_result.html',
        tool=tool,
        colors=HOMOLOGY_BOX_COLORS,
        species_names=SPECIES_NAMES,
        async_result=json.dumps(async_result),
        runhash=task_id,
        **results
    )

@mset_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    if async_result.state == states.PENDING:
        ## We haven't given the tool enough time to setup
        if not async_result.info:
            progress = None
            percent = None
        else:
            progress = async_result.info['message']
            percent = async_result.info['percent']

    elif async_result.state == states.FAILURE:
        progress = 'Failed'
        percent = ''

    else:
        progress = 'Done'
        percent = ''


    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
        'progress': progress,
        'percent': percent
    })


