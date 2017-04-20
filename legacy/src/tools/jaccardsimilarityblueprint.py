import celery.states as states
import flask
import json
import uuid
import geneweaverdb
import geneweaverdb as gwdb
import toolcommon as tc
from decimal import Decimal
from jinja2 import Environment, meta, PackageLoader, FileSystemLoader

TOOL_CLASSNAME = 'JaccardSimilarity'
jaccardsimilarity_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

#class result():
#    async_result=''
#r = result()

@jaccardsimilarity_blueprint.route('/run-jaccard-similarity.html', methods=['POST'])
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
        

    if len(selected_geneset_ids) < 2:
        flask.flash(('You need to select at least 2 genesets as input for '
                    'this tool.'))

        return flask.redirect('analyze')

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
        flask.flash('Please log in to run the tool.')

        return flask.redirect('analyze')

    # Gather emphasis gene ids and put them in paramters
    emphgeneids = []
    user_id = flask.session['user_id']
    emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))
    params['EmphasisGenes'] = emphgeneids

   
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
        },
        task_id=task_id)

    # render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    response = flask.make_response(tc.render_tool_pending(async_result, tool))
    response.status_code = 303
    response.headers['location'] = new_location

    return response

def run_tool_api(apikey, homology, pairwiseDeletion, genesets, p_Value):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)
    
    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(':')
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least two genesets selected to run this tool')

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_PairwiseDeletion'):
            params[tool_param.name] = pairwiseDeletion
            if(params[tool_param.name] != 'Enabled'):
                params[tool_param.name] = 'Disabled'
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = 'Excluded'
            params[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                params[homology_str] = 'Included'
                params[tool_param.name] = 'Included'
        if tool_param.name.endswith('_' + 'p-Value'):
            params[tool_param.name] = p_Value
            if p_Value not in ['1.0','0.5','0.10','0.05','0.01']:
                params[tool_param.name] = '1.0'
    
    
    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)


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
        },
        task_id=task_id)


    return task_id

@jaccardsimilarity_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)


    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    else:
        flask.flash('Please log in to view your results')

        return flask.redirect('analyze')

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        data = async_result.result
        json.dumps(data, indent=4)
        # results are ready. render the page for the user
        return flask.render_template(
            'tool/JaccardSimilarity_result.html',
            data = data,
            async_result=json.loads(async_result.result),
            tool=tool, list=gwdb.get_all_projects(user_id))
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)

@jaccardsimilarity_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    if not async_result.info:
        async_result.info = {}

    if not async_result.info['message']:
        async_result.info['message'] = 'Working...'

    if not async_result.info['percent']:
        async_result.info['percent'] = None

    if async_result.state == states.PENDING:
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

@jaccardsimilarity_blueprint.route('/geneset_intersection/<gsID_1>/<gsID_2>/<i>.html')
def geneset_intersection(gsID_1, gsID_2, i):
    user_id = flask.session.get('user_id')
    if user_id:
        geneset1 = gwdb.get_geneset(gsID_1[2:], user_id)
        geneset2 = gwdb.get_geneset(gsID_2[2:], user_id)
        genesets = [geneset1, geneset2]
        intersect_genes = {}
        temp_genes = gwdb.get_gene_sym_by_intersection(gsID_1[2:], gsID_2[2:])
        for j in range(0, len(temp_genes[0])):
            intersect_genes[temp_genes[0][j]] = gwdb.if_gene_has_homology(temp_genes[1][j])
        list=gwdb.get_all_projects(user_id)
    else:
        geneset1 = geneset2 = None

    return flask.render_template(
        "geneset_intersection.html", async_result=json.loads(async_result.result),
        index=i, genesets=genesets, gene_sym=intersect_genes, list=list)

