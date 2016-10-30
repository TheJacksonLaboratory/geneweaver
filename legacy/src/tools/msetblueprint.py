import celery.states as states
import flask
import json
import uuid
import geneweaverdb as gwdb
import toolcommon as tc
import sys
from decimal import Decimal
from jinja2 import Environment, meta, PackageLoader, FileSystemLoader

TOOL_CLASSNAME = 'MSET'
mset_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)


# class result():
#    async_result=''
# r = result()

@mset_blueprint.route('/MSET.html', methods=['POST'])
def run_tool():
    # TODO need to check for read permissions on genesets

    form = flask.request.form
    # sys.stderr.write("######### I'M WRITING THINGS!!!!!#############\n")
    # sys.stderr.write(str(form['MSET_Background'])+"\n")
    # sys.stderr.write("########## I'M DONE WRITING THINGS!!!!!############\n")

    # pull out the selected geneset IDs
    selected_geneset_ids = tc.selected_geneset_ids(form)
    selected_project_ids = tc.selected_project_ids(form)

    sys.stderr.write("######### I'M WRITING THINGS!!!!!#############\n")
    sys.stderr.write(str(selected_project_ids)+"\n")
    # sys.stderr.write(str(selected_geneset_ids) + "\n")
    sys.stderr.write("########## I'M DONE WRITING THINGS!!!!!############\n")
    # Used only when rerunning the tool from the results page
    if 'genesets' in form:
        add_genesets = form['genesets'].split(' ')
        edited_add_genesets = [gs[2:] for gs in add_genesets]
        selected_geneset_ids = selected_geneset_ids + edited_add_genesets

    if len(selected_project_ids) < 3:
        flask.flash("Warning: You need at least 3 projects!")
        return flask.redirect('analyze')


    background = form['MSET_Background']
    topgenes = form['MSET_TopGenes']
    bgId = -1
    tgId = -1

    for pj_id in selected_project_ids:
        names = gwdb.get_pjname_by_pj_id(pj_id)
        pjName = ""
        for name in names:
            pjName = str(name[0])
            # sys.stderr.write(str(name[0]))
            # if background == str(row[names):
              #  sys.stderr.write("We found the background!\n")
        if background == pjName:
            bgId = pj_id
            # sys.stderr.write(str(name[0]))
        elif topgenes == pjName:
            tgId = pj_id

    if bgId < 0:
        flask.flash("Warning: The background name you entered does not match any project selected!")
        return flask.redirect('analyze')
    elif tgId < 0:
        flask.flash("Warning: The top genes name you entered does not match any project selected!")
        return flask.redirect('analyze')

    # if len(selected_project_ids) < 3:
    #    flask.flash("Warning: You must select at least 3 projects!")
    #    return flask.redirect('analyze')

    # info dictionary
    # gs_dict_bg = {}
    # gs_dict_tp = {}
    gs_dict = {}

    # retrieve gene symbols for bg, tg, & other stuff
    # gene_symbols_bg = {}
    # gene_symbols_tp = {}
    gene_symbols = {}

    for pj_id in selected_project_ids:
        raw = gwdb.get_genesymbols_by_pj_id(pj_id)
        symbol_list = []

        for sym in raw:
            symbol_list.append(sym[0])

        # if pj_id == bgId:
          #  gene_symbols_bg[pj_id] = symbol_list
        # elif pj_id == tgId:
          #  gene_symbols_tg[pj_id]
        gene_symbols[pj_id] = symbol_list

        # sys.stderr.write(str(pj_id) + "\n")

    # for sym in gene_symbols[bgId]:
      #  sys.stderr.write(str(sym) + "\n")


    # retrieve gs names and abbreviations
    gene_set_names = {}
    gene_set_abbreviations = {}
    species_info = {}
    species_map = {}

    for pj_id in selected_project_ids:
        raw = gwdb.get_gsinfo_by_pj_id(pj_id)
        gene_set_names[pj_id] = raw[0][0]
        gene_set_abbreviations[pj_id] = raw[0][1]
        species_info[pj_id] = gwdb.get_species_name_by_sp_id(raw[0][2])

    gs_dict["gene_symbols"] = gene_symbols
    gs_dict["gene_set_names"] = gene_set_names
    gs_dict["gene_set_abbr"] = gene_set_abbreviations
    gs_dict["species_info"] = species_info
    gs_dict["species_map"] = species_map
    gs_dict["project_ids"] = selected_project_ids
    gs_dict["bgId"] = bgId
    gs_dict["tgId"] = tgId

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    # samples_str = 'MSET_NumberOfSamples'
    # samples = 0
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        params[tool_param.name] = form[tool_param.name]
        sys.stderr.write(str(tool_param.name) + "\n")
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = form[tool_param.name]

    #sys.stderr.write(str(form['MSET_NumberofSamples']) + "\n")
    #sys.stderr.write(str(samples[samples_str]) + "\n")
    if params[homology_str] != 'Excluded':
        params[homology_str] = 'Included'

    # not sure if I need this
    for project_id in gs_dict["gene_symbols"]:
        species = gs_dict["species_info"][project_id]
        for pj_id in gs_dict["gene_symbols"][project_id]:
            if pj_id not in gs_dict["species_map"]:
                gs_dict["species_map"][pj_id] = species

    # TODO include logic for "use emphasis" (see prepareRun2(...) in Analyze.php)

    # insert result for this run
    user_id = None

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        gs_dict["user_id"] = user_id

    else:
        flask.flash('Please log in to run the tool')

        return flask.redirect('analyze')

    # Gather emphasis gene ids and put them in paramters
    # emphgeneids = []
    # user_id = flask.session['user_id']
    # emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
    # for row in emphgenes:
    #    emphgeneids.append(str(row['ode_gene_id']))
    # params['EmphasisGenes'] = emphgeneids

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

#@mset_blueprint.route('/api/tool/MSET.html', methods=['GET'])
def run_tool_api(apikey, homology, p_Value, genesets):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)

    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(':')
    if len(selected_geneset_ids) < 3:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least three genesets selected to run this tool')

    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = 'Excluded'
            params[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                params[homology_str] = 'Included'
                params[tool_param.name] = 'Included'
        if tool_param.name.endswith('_' + 'NumberofSamples'):
            params[tool_param.name] = p_Value
            if p_Value not in ['100', '1000', '5000', '10000']:
                params[tool_param.name] = '100'

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


@mset_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
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
            'tool/MSET_result.html',
            data=data,
            async_result=json.loads(async_result.result),
            tool=tool, list=gwdb.get_all_projects(user_id))
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@mset_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
def status_json(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)

    return flask.jsonify({
        'isReady': async_result.state in states.READY_STATES,
        'state': async_result.state,
    })


