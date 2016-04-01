import celery.states as states
import flask
import json
import uuid

import geneweaverdb as gwdb
import toolcommon as tc

TOOL_CLASSNAME = 'BooleanAlgebra'
boolean_algebra_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

@boolean_algebra_blueprint.route('/Boolean-Algebra.html', methods=['POST'])
# @boolean_algebra_blueprint.route('/run-boolean-algebra.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        flask.flash("Warning: You need at least two GeneSets!")
        return flask.redirect('analyze')

    else:

        params = {}
        for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
            params[tool_param.name] = form[tool_param.name]
            params['at_least'] = form["BooleanAlgebra_min_sets"]

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
            },
            task_id=task_id)

        # render the status page and perform a 303 redirect to the
        # URL that uniquely identifies this run
        new_location = flask.url_for(TOOL_CLASSNAME + '.view_result', task_id=task_id)
        response = flask.make_response(tc.render_tool_pending(async_result, tool))
        response.status_code = 303
        response.headers['location'] = new_location

        return response


def run_tool_api(apikey, relation, genesets):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)

    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(':')
    if len(selected_geneset_ids) < 2:
        # TODO add nice error message about missing genesets
        # there needs to be a min of 2, is there a max?
        raise Exception('There must be at least two GeneSets selected to run this tool')

    else:
        relationEnd = relation.split(':')
        params = {}
        if len(relationEnd) > 1:
			try:
				int(relationEnd[1])
				params['at_least'] = relationEnd[1]
			except ValueError:
				params['at_least'] = '2' 				   
			for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
				if tool_param.name.endswith('_Relation'):
					params[tool_param.name] = 'Intersect at least'
        else:
			params['at_least'] = '0'    
			for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
				if tool_param.name.endswith('_Relation'):
					params[tool_param.name] = relation
					if params[tool_param.name] not in ['Union','Intersect','Except']:
						params[tool_param.name] = 'Union'

        # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

        # insert result for this run
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
            desc, 't')

        async_result = tc.celery_app.send_task(
            tc.fully_qualified_name(TOOL_CLASSNAME),
            kwargs={
                'gsids': selected_geneset_ids,
                'output_prefix': task_id,
                'params': params,
            },
            task_id=task_id)

        return task_id

@boolean_algebra_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):

    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)
    # C: May need to update path to result to the location of the json file
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)
    elif async_result.state in states.READY_STATES:
        # results are ready. render the page for the user

        # added emphgeneids for the table in the boolean algebra result html file
        emphgeneids = []

        user_id = flask.session['user_id']
        emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
        for row in emphgenes:
            emphgeneids.append(str(row['ode_gene_id']))

        return flask.render_template(
            'tool/BooleanAlgebra_result.html',
            async_result=json.loads(async_result.result),
            tool=tool,
            emphgeneids=emphgeneids)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@boolean_algebra_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task

    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })
