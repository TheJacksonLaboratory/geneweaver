import flask
import celery.states as states
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc

# BITBUCKET IS DUMB
# NO. IT'S REALLY DUMB

TOOL_CLASSNAME = 'JaccardClustering'
jaccardclustering_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

@jaccardclustering_blueprint.route('/JaccardClustering.html', methods=['POST'])
def run_tool():

     # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    # Used only when rerunning the tool from the results page
    if 'genesets' in form:
        add_genesets = form['genesets'].split(' ')
        edited_add_genesets = [gs[2:] for gs in add_genesets]
        selected_geneset_ids = selected_geneset_ids + edited_add_genesets


    if len(selected_geneset_ids) < 3:
        flask.flash("Warning: You need at least 3 genes!")
        return flask.redirect('analyze')

    # info dictionary
    gs_dict = {}


    # retrieve gene symbols
    gene_symbols = {}

    for gs_id in selected_geneset_ids:
        raw = gwdb.get_genesymbols_by_gs_id(gs_id)
        symbol_list = []

        for sym in raw:
            symbol_list.append(sym[0])

        gene_symbols[gs_id] = symbol_list

    # retrieve gs names and abbreviations
    gene_set_names = {}
    gene_set_abbreviations = {}
    species_info = {}

    for gs_id in selected_geneset_ids:
        raw = gwdb.get_gsinfo_by_gs_id(gs_id)
        gene_set_names[gs_id] = raw[0][0]
        gene_set_abbreviations[gs_id] = raw[0][1]
        species_info[gs_id] = gwdb.get_species_name_by_sp_id(raw[0][2])

    gs_dict["gene_symbols"] = gene_symbols
    gs_dict["gene_set_names"] = gene_set_names
    gs_dict["gene_set_abbr"] = gene_set_abbreviations
    gs_dict["species_info"] = species_info

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        params[tool_param.name] = form[tool_param.name]
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = form[tool_param.name]
    if params[homology_str] != 'Excluded':
        params[homology_str] = 'Included'

    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run
    user_id = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        flask.flash("Internal error: user ID missing")
        return flask.redirect('analyze')

    task_id = str(uuid.uuid4())
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
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
        task_id=task_id)

    # render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    response = flask.make_response(tc.render_tool_pending(async_result, tool))
    response.status_code = 303
    response.headers['location'] = new_location

    return response


#@jaccardclustering_blueprint.route('/api/tool/JaccardClustering.html', methods=['GET'])
def run_tool_api(apikey, homology, method, genesetsPassed):

    user_id = gwdb.get_user_id_by_apikey(apikey)
    # TODO need to check for read permissions on genesets

    # gather the params into a dictionary
    homology_str = 'Homology'
    paramsAPI = {homology_str: None}

    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_' + 'Method'):
		    paramsAPI[tool_param.name] = method
		    if method not in ['Ward', 'Single', 'McQuitty', 'Average', 'Complete', 'Heatmap']:
				paramsAPI[tool_param.name] = 'Ward'
        if tool_param.name.endswith('_' + homology_str):
            paramsAPI[homology_str] = 'Excluded'
            paramsAPI[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                paramsAPI[homology_str] = 'Included'
                paramsAPI[tool_param.name] = 'Included'


    # pull out the selected geneset IDs
    selected_geneset_ids = genesetsPassed.split(":")
    if len(selected_geneset_ids) < 3:
        # TODO add nice error message about missing genesets
        raise Exception('There must be at least three genesets selected to run this tool')


    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run

    task_id = str(uuid.uuid4())
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(paramsAPI),
        tool.name,
        desc,
        desc)

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': paramsAPI,
        },
        task_id=task_id)

	# TODO SOON return file istead of just name of file
    return task_id


@jaccardclustering_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    # really debug here
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    path_to_result = '/results/'+task_id+'.json'

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        # results are ready. render the page for the user
        return flask.render_template(
            'tool/JaccardClustering_result.html',
            async_result=json.loads(async_result.result),
            tool=tool,
            cluster_data=path_to_result)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)

@jaccardclustering_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })