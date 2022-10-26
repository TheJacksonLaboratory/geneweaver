import json
import uuid
from neo4j import GraphDatabase
import psycopg2
from decimal import Decimal

from jinja2 import Environment, meta, PackageLoader, FileSystemLoader
import celery.states as states
import flask

import geneweaverdb
import geneweaverdb as gwdb
import tools.toolcommon as tc

class Neo4jConnection:

    def __init__(self, uri, user, pwd):
        self.__uri = uri
        self.__user = user
        self.__pwd = pwd
        self.__driver = None
        try:
            self.__driver = GraphDatabase.driver(self.__uri, auth=(self.__user, self.__pwd))
        except Exception as e:
            print("Failed to create the driver:", e)

    def close(self):
        if self.__driver is not None:
            self.__driver.close()

    def query(self, query, db=None):
        assert self.__driver is not None, "Driver not initialized!"
        session = None
        response = None
        try:
            session = self.__driver.session(database=db) if db is not None else self.__driver.session()
            response = list(session.run(query))
        except Exception as e:
            print("Query failed:", e)
        finally:
            if session is not None:
                session.close()
        return response

conn = Neo4jConnection(uri="bolt+s://graph.geneweaver.org:7687", user="sophie",
                       pwd="laptop-private-evident-barbara-aztec-8272")

TOOL_CLASSNAME = 'FindVariants'
findvariants_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

# class result():
#    async_result=''
# r = result()

@findvariants_blueprint.route('/run-find-variants.html', methods=['POST'])
def run_tool():
    form = flask.request.form

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)

    # Used only when rerunning the tool from the results page
    if 'genesets' in form:
        add_genesets = form['genesets'].split(' ')
        edited_add_genesets = [gs[2:] for gs in add_genesets]
        selected_geneset_ids = selected_geneset_ids + edited_add_genesets

    if len(selected_geneset_ids) < 1:
        flask.flash(('You need to select at least 1 geneset as input for this tool.'))

        return flask.redirect('/analyze')

    # insert result for this run
    user_id = None

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    else:
        flask.flash('Please log in to run the tool.')

        return flask.redirect('/analyze')

    # gather the params into a dictionary
    params = {}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        # print(form[tool_param.name])
        if(tool_param.name == "FindVariants_Path"):
            all = form.getlist
            params[tool_param.name] = all("FindVariants_Path")
        else:
            params[tool_param.name] = form[tool_param.name]

    # get gene symbols for each gene in geneset
    gene_syms = []
    for g in selected_geneset_ids:
        gsv = gwdb.get_geneset_values(g)
        for i in gsv:
            gene_syms = gene_syms + i.source_list
    gene_syms = list(set(gene_syms))
    params['gene_syms'] = gene_syms
    print(params)

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


def run_tool_api(apikey, species, genesets, path):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)

    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(':')
    if len(selected_geneset_ids) < 1:
        raise Exception('You need to select at least 1 geneset as input for this tool.')

    # gather the params into a dictionary
    params = {}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_Path'):
            params[tool_param.name] = path
            if params[tool_param.name] != 'using eQTL':
                params[tool_param.name] = 'using Transcript'
        if tool_param.name.endswith('_Species'):
            params[tool_param.name] = 'Human to Mouse'
            if species != 'Human to Mouse':
                params[tool_param.name] = 'Mouse to Human'

    # get gene symbols for each gene in geneset
    gene_syms = []
    for g in selected_geneset_ids:
        gsv = gwdb.get_geneset_values(g)
        for i in gsv:
            gene_syms = gene_syms + i.source_list
    gene_syms = list(set(gene_syms))
    params['gene_syms'] = gene_syms

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


@findvariants_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    else:
        flask.flash('Please log in to view your results')

        return flask.redirect('/analyze')

    if async_result.state in states.PROPAGATE_STATES:
        # TODO render a real descriptive error page not just an exception
        raise Exception('error while processing: ' + tool.name)

    elif async_result.state == states.FAILURE:

        results = json.loads(async_result.result)

        if results['error']:
            flask.flash(results['error'])
        else:
            flask.flash(
                'An unkown error occurred. Please contact a GeneWeaver admin.'
            )

            return flask.redirect('/analyze')

    elif async_result.state in states.READY_STATES:
        results = json.loads(async_result.result)

        if 'error' in results and results['error']:
            flask.flash(results['error'])

            return flask.redirect('/analyze')

        if len(results['variants']) == 0:
            flask.flash(
                'No results were found.'
            )
            return flask.redirect('/analyze')

        # results are ready. render the page for the user
        return flask.render_template(
            'tool/FindVariants_result.html',
            data=async_result.result,
            async_result=results,
            tool=tool, list=gwdb.get_all_projects(user_id))
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@findvariants_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
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



