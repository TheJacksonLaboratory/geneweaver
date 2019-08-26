import celery.states as states
import flask
import json
import uuid
import operator
import config
import os
import geneweaverdb as gwdb
import toolcommon as tc
from decimal import Decimal
from collections import OrderedDict

TOOL_CLASSNAME = 'BooleanAlgebra'
boolean_algebra_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)
RESULTS_PATH = config.get('application', 'results')


class BooleanResultError(Exception):
    """ Exception returned when boolean results have a problem """
    pass


@boolean_algebra_blueprint.route('/Boolean-Algebra.html', methods=['POST'])
# @boolean_algebra_blueprint.route('/run-boolean-algebra.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)

    if len(selected_geneset_ids) < 2:
        flask.flash(('You need to select at least 2 genesets as input for '
                    'this tool.'))

        return flask.redirect('analyze')
    
    if 'BooleanAlgebra_Relation' not in form:
        flask.flash(('You need to select a boolean algebra relation for '
                    'this tool.'))

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
            flask.flash('Please log in to run the tool.')

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
        raise Exception('there must be at least two GeneSets selected to run this tool')

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
                    if params[tool_param.name] not in ['Union', 'Intersect', 'Except']:
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


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


def get_results(async_result, tool):
    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise BooleanResultError('error while processing: ' + tool.name)

    elif async_result.state == states.FAILURE:
        results = json.loads(async_result.result)

        if results['error']:
            raise BooleanResultError(results['error'])
        else:
            raise BooleanResultError('An unknown error occurred. Please contact a GeneWeaver admin.')

    elif async_result.state in states.READY_STATES:
        results = json.loads(async_result.result)

        if 'error' in results and results['error']:
            raise BooleanResultError(results['error'])
        else:
            return results


def read_results_file(task_id):
    with open(RESULTS_PATH + '/' + task_id + '.json', 'r') as f:
        json_results = f.readline()
        f.close()
    return json.loads(json_results)


def get_emphgenes(user_id):
    return [str(row['ode_gene_id']) for row in gwdb.get_gene_and_species_info_by_user(user_id)]


def paginate_dict(dict, page, per_page):
    page = int(page)
    per_page = int(per_page)
    sorted_items = sorted(dict.items(), key=operator.itemgetter(0))
    start = page*per_page
    paged = sorted_items[start:start+per_page]
    return OrderedDict(paged)


def paginate_bool_dicts(json_results, page, per_page):
    if 'bool_results' in json_results:
        json_results['bool_results'] = paginate_dict(json_results['bool_results'], page, per_page)
    if 'bool_except' in json_results:
        json_results['bool_except'] = {k: paginate_dict(v, page, per_page)
                                       for k, v in json_results['bool_except'].iteritems()}
    if 'intersect_results' in json_results:
        json_results['intersect_results'] = {k: paginate_dict(v, page, per_page)
                                             for k, v in json_results['intersect_results'].iteritems()}
    return json_results


def calculate_gene_list_for_table(table):
    this_gene_list = []
    for _, row in table.iteritems():
        this_gene_list.append(row[0][0])
    return list(set(this_gene_list))


def calculate_gene_list_results(json_results):
    if json_results['type'] == 'Union':
        results = {'union': json_results['bool_results']}
    elif json_results['type'] == 'Intersect':
        results = json_results['intersect_results']
    elif json_results['type'] == 'Except':
        results = json_results['bool_except']
    else:
        return json_results

    gene_list = {}
    for key, table in results.iteritems():
        gene_list[key] = calculate_gene_list_for_table(table)
    json_results['gene_list'] = gene_list

    return json_results


@boolean_algebra_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        flask.flash("Please log in to view results")
        return flask.redirect('analyze')

    try:
        results = get_results(async_result, tool)
    except BooleanResultError as e:
        flask.flash(e.message)
        return flask.redirect('analyze')

    if results:
        # added emphgeneids for the table in the boolean algebra result html file
        emphgeneids = get_emphgenes(user_id)
        json_results = read_results_file(task_id)

        json_results = calculate_gene_list_results(json_results)

        if json_results['type'] == 'Except':
            json_results['type'] = 'Symmetric Difference'

        return flask.render_template(
            'tool/BooleanAlgebra_result.html',
            json_results=json_results,
            async_result=results,
            tool=tool,
            emphgeneids=emphgeneids,
            task_id=task_id)
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


def datatablify(row_dict, draw_value, start=0, length=25):
    dtbls_data = {'data': [
        {"row_genes": {'key': key,
                       'ids': list(set([it[0] for it in row])),
                       'data': [{'sp': it[2], 'name': it[1]} for it in row]},
         "homology": True if len(row) > 1 else False,
         "genesets": [it[3] for it in row],
         "species": list(set([it[2] for it in row])),
         "emphasis": None}
        for key, row in row_dict.iteritems()
    ]}
    total = len(dtbls_data['data'])
    dtbls_data['data'] = dtbls_data['data'][start:start + length]
    dtbls_data['recordsFiltered'] = total
    dtbls_data['recordsTotal'] = total
    dtbls_data['draw'] = draw_value
    return dtbls_data


@boolean_algebra_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>/output.json', methods=['GET'])
def datatable_data(task_id):
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    if 'user_id' not in flask.session:
        flask.flash("Please log in to view results")
        return flask.redirect('analyze')

    try:
        results = get_results(async_result, tool)
    except BooleanResultError as e:
        return flask.jsonify({'error1': e.message})
    if results:

        json_results = read_results_file(task_id)

        draw = int(flask.request.args.get('draw', 0))
        start = int(flask.request.args.get('start', 0))
        length = int(flask.request.args.get('length', 25))

        if json_results['type'] == 'Union':
            data = json_results['bool_results']
        elif json_results['type'] == 'Intersect':
            table = flask.request.args.get('table')
            data = json_results['intersect_results'][table]
        elif json_results['type'] == 'Except':
            json_results['type'] = 'Symmetric Difference'
            table = flask.request.args.get('table')
            data = json_results['bool_except'][table]
        else:
            return flask.jsonify({'data': None})

        datatables_data = datatablify(data, draw, start, length)
        return flask.jsonify(datatables_data)


@boolean_algebra_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
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

