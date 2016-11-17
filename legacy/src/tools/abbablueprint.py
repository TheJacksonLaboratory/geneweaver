import celery.states as states
import flask
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc
from collections import defaultdict, OrderedDict

TOOL_CLASSNAME = 'ABBA'
abba_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)


@abba_blueprint.route('/run-abba.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)

    params = {}
    if ('ABBA_InputGenes' not in form or not form['ABBA_InputGenes']) and len(selected_geneset_ids) < 1:
        # TODO add nice error message about missing genesets
        flask.flash("Warning: You need to have input or/and at least a GeneSet selected!")
        return flask.redirect('analyze')

    params['ABBA_InputGenes'] = form.getlist("ABBA_InputGenes")
    if 'ABBA_IgnHom' in form:
        params['ABBA_IgnHom'] = form['ABBA_IgnHom']
    if 'ABBA_ShowInter' in form:
        params['ABBA_ShowInter'] = form['ABBA_ShowInter']
    if 'ABBA_MinGenes' in form:
        params['ABBA_MinGenes'] = form['ABBA_MinGenes']
    if 'ABBA_MinGenesets' in form:
        params['ABBA_MinGenesets'] = form['ABBA_MinGenesets']
    if 'ABBA_Tierset' in form:
        params['ABBA_Tierset'] = form['ABBA_Tierset']
    if 'ABBA_RestrictOption' in form:
        params['ABBA_RestrictOption'] = form['ABBA_RestrictOption']    
    if 'ABBA_RestrictSpecies' in form:
        params['ABBA_RestrictSpecies'] = form.getlist('ABBA_RestrictSpecies')

    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run
    user_id = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        projects = gwdb.get_all_projects(user_id)
        projectDict = OrderedDict()
        for proj in projects:
            projectDict[proj.project_id] = {'id': proj.project_id, 'name': proj.name, 'count': proj.count}
        params['UserProjects'] = projectDict

        params['UserId'] = user_id
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
            'params': params
        },
        task_id=task_id)

    # render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    response = flask.make_response(tc.render_tool_pending(async_result, tool))
    response.status_code = 303
    response.headers['location'] = new_location

    return response


@abba_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    # Gather emphasis gene ids and put them in parameters
    emphgeneids = []
    user_id = flask.session.get('user_id')
    emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(int(row['ode_gene_id']))
    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        # results are ready. render the page for the user
        return flask.render_template(
            'tool/ABBA_result.html',
            async_result=json.loads(async_result.result),
            tool=tool, emphgeneids=emphgeneids)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@abba_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })
