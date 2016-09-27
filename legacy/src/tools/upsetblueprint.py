import celery.states as states
import flask
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc

from decimal import Decimal
from jinja2 import Environment, meta, PackageLoader, FileSystemLoader

TOOL_CLASSNAME = 'UpSet'
upset_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

@upset_blueprint.route('/run-up-set.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    if len(selected_geneset_ids) < 2:
        flask.flash("Warning: You need at least 2 genes!")
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

    #insert result for this to run
    user_id = None

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    else:
        flask.flash("Internal error: user ID missing")
        return flask.redirect('analyze')

    # Gather emphasis gene ids and put them in parameters
    # I believe this is basically mapping the genes to their
    # respective species. This could help with the whole
    # homology thing, or not. Right now I am not completely sure
    # that this piece of code is useless, but we will find out when
    # we begin to test UpSet.
    emphgeneids = []
    user_id = flask.session['user_id']
    emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))
    params['EmphasisGenes'] = emphgeneids

    # We are now sending our params and other related stuff to a
    # Celery task. this will take it to be run by GENEWEAVER/TOOLS
    # First the result table is updated to say you know "Hey, we are
    # doing this tool fyi"
    task_id = str(uuid.uuid4())
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    desc = '{} on {} GeneSets'.format(tool.name, len(selected_geneset_ids))
    gwdb.insert_result(
        user_id,
        task_id,
        selected_geneset_ids,
        json.dumps(params),
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
    response.headers['location'] =new_location

    return response