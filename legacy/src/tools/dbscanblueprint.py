import celery.states as states
import flask
import json
import uuid
import geneweaverdb as gwdb
import sys
import itertools
import toolcommon as tc
TOOL_CLASSNAME = 'DBSCAN'
dbscan_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)

HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']
SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
                 'Canis familiaris']
placeholder_homology = [1, 2, 3, 4, 5, 6, 8, 9, 10, 11]


@dbscan_blueprint.route('/run-dbscan.html', methods=['POST'])
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

    # info dictionary
    gs_dict = {}

    # retrieve gene symbols
    gene_symbols = {}
    # gene_symbols_set = set()
    for gs_id in selected_geneset_ids:
        raw = gwdb.get_genesymbols_by_gs_id(gs_id)
        symbol_list = []

        for sym in raw:
            symbol_list.append(sym[0])
            # gene_symbols_set.add(sym[0])
        gene_symbols[gs_id] = symbol_list

    # gene_symbols_set = list(gene_symbols_set)
    edges = list()
    threshold = 0
    counter = 0
    for gs_id in selected_geneset_ids:
        countConnections = 0
        for connection in itertools.combinations(gene_symbols[gs_id], 2):
            edges.append(connection)
            countConnections += 1
        if countConnections > counter:
            counter = countConnections
    if counter > 150:
        threshold = 1
    # retrieve gs names and abbreviations
    gene_set_names = {}
    gene_set_abbreviations = {}
    species_info = {}
    species_map = {}

    for gs_id in selected_geneset_ids:
        raw = gwdb.get_gsinfo_by_gs_id(gs_id)
        gene_set_names[gs_id] = raw[0][0]
        gene_set_abbreviations[gs_id] = raw[0][1]
        species_info[gs_id] = gwdb.get_species_name_by_sp_id(raw[0][2])

    gs_dict["gene_symbols"] = gene_symbols
    gs_dict["gene_set_names"] = gene_set_names
    gs_dict["gene_set_abbr"] = gene_set_abbreviations
    gs_dict["species_info"] = species_info
    gs_dict["species_map"] = species_map
    gs_dict["edges"] = edges
    gs_dict["threshold"] = threshold
    # gather the params into a dictionary
    homology_str = 'Homology'
    params = {homology_str: None}
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        params[tool_param.name] = form[tool_param.name]
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = form[tool_param.name]
    if params[homology_str] != 'Excluded':
        params[homology_str] = 'Included'

    # add mapping of (key) gene to (entry) species for visualization
    for gene_set_id in gs_dict["gene_symbols"]:
        species = gs_dict["species_info"][gene_set_id]
        for gene_id in gs_dict["gene_symbols"][gene_set_id]:
            if gene_id not in gs_dict["species_map"]:
                gs_dict["species_map"][gene_id] = species


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

    # check if parameters are blank, set to a default
    if params['DBSCAN_minPts'] == '':
        params['DBSCAN_minPts'] = "1".decode('unicode-escape')
    if params['DBSCAN_epsilon'] == '':
        params['DBSCAN_epsilon'] = "1".decode('unicode-escape')

    # genes = 0
    # for set in gs_dict["gene_symbols"]:
    #     for gene in gs_dict["gene_symbols"][set]:
    #         genes += 1

    # if genes <= params['DBSCAN_minPts']:


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

    # num_genes = 0
    # num_genesets = 0
    # num_links = 0
    # genes = {}
    # genesets = {}
    # links = ""

    # sys.stderr.write("#####\n#####\n#####\n")
    # gene_symbols = gs_dict["gene_symbols"]
    # for key in gene_symbols:
    #     if str(key) not in genesets:
    #         genesets[str(key)] = num_genesets
    #         num_genesets += 1
    #     for element in gene_symbols[key]:
    #         if str(element) not in genes:
    #             genes[str(element)] = num_genes
    #             num_genes += 1
    #        links += str(genes[element])+"*"+str(genesets[key])+"*"
    #         num_links += 1
    # data_input = str(num_genes) + "*" + str(num_genesets) + "*" + str(num_links) + "*" + links
    # sys.stderr.write(data_input)

    # sys.stderr.write("#####\n#####\n#####\n")
    # for key in gs_dict:
    #   sys.stderr.write(str(key)+": "+str(gs_dict[key])+"\n")

    return response


def run_tool_api(apikey, minPts, genesets, epsilon, homology):
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
        if tool_param.name.endswith('_epsilon'):
            params[tool_param.name] = epsilon
            if epsilon not in ['1', '2']:
                params[tool_param.name] = '1'
        if tool_param.name.endswith('_minPts'):
            params[tool_param.name] = minPts
            if minPts not in ['3', '4']:
                params[tool_param.name] = '3'
        if tool_param.name.endswith('_' + homology_str):
            params[homology_str] = 'Excluded'
            params[tool_param.name] = 'Excluded'
            if homology != 'Excluded':
                params[homology_str] = 'Included'
                params[tool_param.name] = 'Included'

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


@dbscan_blueprint.route('/' + TOOL_CLASSNAME + '-result/<task_id>.html', methods=['GET', 'POST'])
def view_result(task_id):
    # TODO need to check for read permissions on task
    async_result = tc.celery_app.AsyncResult(task_id)
    tool = gwdb.get_tool(TOOL_CLASSNAME)

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        emphgenes = {}
        emphgeneids = []
        user_info = gwdb.get_user(user_id)
        emphgenes = gwdb.get_gene_and_species_info_by_user(user_id)
        # for row in emphgenes:
        #     emphgeneids.append(str(row['ode_gene_id']))



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

        gene_info = {}
        gs_ids = []
        genes = 0
        test = json.loads(async_result.result)

        sys.stderr.write("#####################"+str(test['ran'])+"\n")

        if test['ran'] == 1 and 'resClusters' in test:
            genes = len(test['decode'].keys())

            if genes < 200:
                for row in emphgenes:
                    emphgeneids.append(str(row['ode_gene_id']))

                parameters = test['parameters']
                gs_dict = parameters["gs_dict"]
                for gs_id in gs_dict["gene_symbols"]:
                    for gene in gs_dict["gene_symbols"][gs_id]:
                        gene_info[gene] = {}
                for gs_id in gs_dict["gene_symbols"]:
                    geneset = gwdb.get_geneset(gs_id, user_id)
                    for gene_value in geneset.geneset_values:
                        if gene_value.source_list[0] not in gene_info.keys():
                            gene_info[gene_value.source_list[0]] = {}
                        gene_info[gene_value.source_list[0]]['gene_rank'] = gene_value.gene_rank
                        # sys.stderr.write("gene_info["+str(gene_value.source_list[0])+"][gene_rank] = "+str(gene_value.gene_rank)+"\n")
                        gene_info[gene_value.source_list[0]]['homology'] = gene_value.hom
                        # sys.stderr.write("gene_info["+str(gene_value.source_list[0])+"][homology] = "+str(gene_value.hom)+"\n")
                        gene_info[gene_value.source_list[0]]['ode_id'] = gene_value.ode_gene_id

                for gene in gene_info:
                    if 'gene_rank' not in gene_info[gene].keys():
                        gene_info[gene]['gene_rank'] = 0
                    if 'homology' not in gene_info[gene].keys():
                        gene_info[gene]['homology'] = []
            else:
                for row in emphgenes:
                    emphgeneids.append(str(row['ode_ref_id']))


        # for gene in gene_info:
        #     sys.stderr.write("["+gene+"][gene_rank] = "+str(gene_info[gene]['gene_rank'])+"\n")

        return flask.render_template(
            'tool/DBSCAN_result.html',
            data=data, genes=genes, ran=test['ran'],
            async_result=json.loads(async_result.result), gene_info=gene_info,
            emphgeneids=emphgeneids, colors=HOMOLOGY_BOX_COLORS, tt=SPECIES_NAMES,
            placeholder_homology=placeholder_homology,
            tool=tool, list=gwdb.get_all_projects(user_id))
    else:
        # render a page telling their results are pending
        return tc.render_tool_pending(async_result, tool)


@dbscan_blueprint.route('/' + TOOL_CLASSNAME + '-status/<task_id>.json')
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


@dbscan_blueprint.route('/geneset_intersection/<gsID_1>/<gsID_2>/<i>.html')
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
        list = gwdb.get_all_projects(user_id)
    else:
        geneset1 = geneset2 = None

    return flask.render_template(
        "geneset_intersection.html", async_result=json.loads(async_result.result),
        index=i, genesets=genesets, gene_sym=intersect_genes, list=list)

