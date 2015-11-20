# Team Triclique
# Author: Clarissa Jordan
# Date created: 09/08/2015

import celery.states as states
import flask
import json
import uuid
import os.path

from geneweaverdb import *
import toolcommon as tc
from edgelist import *
from decimal import Decimal

TOOL_CLASSNAME = 'TricliqueViewer'
triclique_viewer_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)
#RESULTS_PATH = 'Users/group5admin/Documents/geneweaver/results/'

# Melissa 9/14/15 Removed .html from route URI
@triclique_viewer_blueprint.route('/run-triclique-viewer', methods=['POST'])
def run_tool():

    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_project_ids = tc.selected_project_ids(form)
    selected_geneset_ids = tc.selected_geneset_ids(form)

    # Used only when rerunning the tool from the results page
    if 'genesets' in form:
        add_genesets = form['genesets'].split(' ')
        edited_add_genesets = [gs[2:] for gs in add_genesets]
        selected_geneset_ids = selected_geneset_ids + edited_add_genesets

    # gather the params into a dictionary
    homology_str = 'Homology'
    method_str   = 'Methods'
    params1 = {homology_str: None}
    params2 = {method_str: None}
    for tool_param in get_tool_params(TOOL_CLASSNAME, True):
        params1[tool_param.name] = form[tool_param.name]
        if tool_param.name.endswith('_' + homology_str):
            params1[homology_str] = form[tool_param.name]
        elif tool_param.name.endswith('_' + method_str):
            params2[method_str] = form[tool_param.name]

    if params1[homology_str] != 'Excluded':
        params1[homology_str] = 'Included'
    if params2[method_str] != 'Jaccard Overlap':
        params2[method_str] = 'ExactGeneOverlap'
        #if len(selected_geneset_ids) != 2:
        if len(selected_project_ids) != 2:
            flask.flash("Warning: You must select exactly 2 projects!")
            return flask.redirect('analyze')
    else:
        if len(selected_project_ids) < 3:
            flask.flash("Warning: You must select at least 3 projects!")
            return flask.redirect('analyze')

    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run
    user_id = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        flask.flash("Internal error: user ID missing")
        return flask.redirect('analyze')

    task_id = str(uuid.uuid4())
    tool = get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params1),
        tool.name,
        desc,
        desc)

    # Will run Dr. Baker's graph-generating code here, and it will be stored in the results directory
    if params2[method_str] == 'ExactGeneOverlap':
        print "Exact gene overlap"
        outOfBounds = create_kpartite_file_from_gene_intersection(task_id, RESULTS_PATH, selected_project_ids[0], selected_project_ids[1], homology=True)
    #TODO: get threshold from user
    else:
        print "Jaccard"
        # Warn the user if the projects selected are too large
        if len(selected_geneset_ids) > 50:
            flask.flash("Warning: Selecting too many genesets will not return results in a timely fashion")
            return flask.redirect('analyze')
        outOfBounds = create_kpartite_file_from_jaccard_overlap(task_id, RESULTS_PATH, selected_project_ids, 0.001)

    if outOfBounds == -1:
        flask.flash("Warning: The genesets for the projects you chose had no intersection")
        return flask.redirect('analyze')
    if outOfBounds == -2:
        flask.flash("Warning: These genesets are too large for timely analysis.")
        return flask.redirect('analyze')
    #print "task_id",task_id
    #print "Wrote file in the results directory"

    async_result = tc.celery_app.send_task(
        tc.fully_qualified_name(TOOL_CLASSNAME),
        kwargs={
            'gsids': selected_geneset_ids,
            'output_prefix': task_id,
            'params': params2,
        },
        task_id=task_id)
    # print "results path: ", RESULTS_PATH

    # render the status page and perform a 303 redirect to the
    # URL that uniquely identifies this run
    new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
    response = flask.make_response(tc.render_tool_pending(async_result, tool))
    response.status_code = 303
    response.headers['location'] = new_location

    return response


@triclique_viewer_blueprint.route('/run-triclique-viewer-api.html', methods=['POST'])
def run_tool_api(apikey, homology, supressDisconnected, minDegree, genesets ):
    '''
    # TODO need to check for read permissions on genesets

    user_id = get_user_id_by_apikey(apikey)

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}

    for tool_param in get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_' + 'SupressDisconnected'):
		    params[tool_param.name] = supressDisconnected
		    if supressDisconnected not in ['On','Off']:
				params[tool_param.name] = 'On'
        if tool_param.name.endswith('_' + 'MinDegree'):
		    params[tool_param.name] = minDegree
		    if minDegree not in ['Auto','1','2','3','4','5','10','20']:
		        params[tool_param.name] = 'Auto'
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = 'Excluded'
            params[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                params[homology_str] = 'Included'
                params[tool_param.name] = 'Included'
    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)


    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(":")
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least two genesets selected to run this tool')


    # insert result for this run

    task_id = str(uuid.uuid4())
    tool = get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    insert_result(
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
    '''

    # Need to also modify this function

    task_id = str(uuid.uuid4())
    return task_id


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError

@triclique_viewer_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = get_tool(TOOL_CLASSNAME)

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        # Check to see if we are using Exact Gene Overlap or Jaccard
        jfile_name = RESULTS_PATH + '/' + task_id + '.mkcj'
        efile_name = RESULTS_PATH + '/' + task_id + '.mkc'
        if os.path.isfile(efile_name):
            create_json_from_triclique_output(task_id, RESULTS_PATH)
        if os.path.isfile(jfile_name):
            create_json_from_triclique_output_jaccard(task_id, RESULTS_PATH)
        # Open files and pass via template
        f = open(RESULTS_PATH + '/' + task_id + '.json', 'r')
        json_results = f.readline()
        f.close()
        g = open(RESULTS_PATH + '/' + task_id + '.csv', 'r')
        csv_results = ''
        for line in g:
            line = line[:-1]
            line = line + '\t'
            csv_results += line
            #print csv_results
        g.close()
        # Need json.loads
        # Need safe
        # Look into json floats (application.py for function)
        # results are ready. render the page for the user
        return flask.render_template(
            'tool/TricliqueViewer_result.html',
            async_result=json.loads(async_result.result),
            task_id=task_id,
            json_results=json.dumps(json_results, default=decimal_default),
            csv_results=csv_results,
            tool=tool)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)

@triclique_viewer_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })
