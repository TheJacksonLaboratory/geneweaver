import celery.states as states
import flask
import json
import uuid
import geneweaverdb as gwdb
import toolcommon as tc
import sys
import os

from decimal import Decimal
from jinja2 import Environment, meta, PackageLoader, FileSystemLoader

TOOL_CLASSNAME = 'MSET'
mset_blueprint = flask.Blueprint(TOOL_CLASSNAME, __name__)
HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']

SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
                 'Canis familiaris']


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
    #species_params = form['MSET_Species']
    sp_params = gwdb.get_parameters_for_tool('MSET_Species')
    sp_params = sp_params[0][0]
    species_checked = flask.request.form.getlist('MSET_Species')

    #sys.stderr.write("######### I'M WRITING THINGS!!!!!#############\n")
    #sys.stderr.write(str(form['MSET_Background']))
    #sys.stderr.write(str(form)+'\n\n')
    #sys.stderr.write(str(species_params)+'\n')
    #sys.stderr.write(str(species_checked) + '\n')
    #sys.stderr.write(str(sp_params) +'\n')
    #sys.stderr.write(str(selected_project_ids)+"\n")
    # sys.stderr.write(str(selected_geneset_ids) + "\n")
    #sys.stderr.write("########## I'M DONE WRITING THINGS!!!!!############\n")
    # Used only when rerunning the tool from the results page
    if 'genesets' in form:
        add_genesets = form['genesets'].split(' ')
        edited_add_genesets = [gs[2:] for gs in add_genesets]
        selected_geneset_ids = selected_geneset_ids + edited_add_genesets

    if len(selected_project_ids) != 2:
        flask.flash("Warning: You need only 2 projects!")
        return flask.redirect('analyze')

    BGFILE_DIR = "/srv/geneweaver/tools/TOOLBOX/mset/backgroundFiles/" + form["MSET_Background"]

    size_of_files = 0
    for sp_name in species_checked:
        bgFile = BGFILE_DIR + str(sp_name) + 'BG.txt'
        bgFile = bgFile.replace(" ", "")
        sys.stderr.write(str(bgFile) + '\n')
        size_of_files += os.stat(bgFile).st_size

    if(size_of_files == 0):
        flask.flash("Warning: The background and species combination you have chosen is empty!\nPlease choose a different combination.")
        return flask.redirect('analyze')

    sp_params_array = eval(str(sp_params))
    #for name in sp_params_array:
    #    sys.stderr.write(str(name) + '\n')

    for name in species_checked:
        sys.stderr.write(str(name) + '\n')

    #if species_checked[0] == sp_params_array[0]:
        #sys.stderr.write("success?")
    #else:
        #sys.stderr.write("Checked: " + str(species_checked[0]) + " Against: " + str(sp_params_array[0]) + '\n')

    if not species_checked:
        flask.flash("Warning: You need at least 1 species selected!")
        return flask.redirect('analyze')

    topgenes = form['MSET_TopGenes']
    intgenes = form['MSET_InterestGenes']
    tgId = -1
    intId = -1

    for pj_id in selected_project_ids:
        names = gwdb.get_pjname_by_pj_id(pj_id)
        pjName = ""
        for name in names:
            pjName = str(name[0])
            # sys.stderr.write(str(name[0]))
            # if background == str(row[names):
              #  sys.stderr.write("We found the background!\n")
            if topgenes == pjName:
                tgId = pj_id
            if intgenes == pjName:
                intId = pj_id

    if tgId < 0:
        flask.flash("Warning: The top genes name you entered does not match any project selected!")
        return flask.redirect('analyze')
    if intId < 0:
        flask.flash("Warning: The interest genes name you entered does not match any project selected!")
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
            #sys.stderr.write(str(sym) + '\n')
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
    #gs_dict["gene_set_names"] = gene_set_names
    #gs_dict["gene_set_abbr"] = gene_set_abbreviations
    #gs_dict["species_info"] = species_info
    #gs_dict["species_map"] = species_map
    gs_dict["project_ids"] = selected_project_ids
    gs_dict["tgId"] = tgId
    gs_dict["intId"] = intId
    gs_dict["sp_params"] = species_checked

    sys.stderr.write("\n*****************\nFinished with main blueprint code part\n")

    #sys.stderr.write(str(gs_result) + '\n')
    ##gs_dict["geneset"] = geneset

    #gs_dict["results"] = gs_result

    # gather the params into a dictionary
    bg_str = 'Background'
    sp_str = 'Species'
    samp_str = 'NumberofSamples'
    params = {bg_str: None, samp_str: None, sp_str: None}
    # samples_str = 'MSET_NumberOfSamples'
    # samples = 0
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        params[tool_param.name] = form[tool_param.name]
        if tool_param.name.endswith('_' + bg_str):
            params[bg_str] = form[tool_param.name]
        elif tool_param.name.endswith('_' + sp_str):
            params[sp_str] = form[tool_param.name]
        elif tool_param.name.endswith('_' + samp_str):
            params[samp_str] = form[tool_param.name]

    #sys.stderr.write(str(form['MSET_NumberofSamples']) + "\n")
    #sys.stderr.write(str(samples[samples_str]) + "\n")
    # not sure if I need this
    #for project_id in gs_dict["gene_symbols"]:
    #    species = gs_dict["species_info"][project_id]
    #    for pj_id in gs_dict["gene_symbols"][project_id]:
    #        if pj_id not in gs_dict["species_map"]:
    #            gs_dict["species_map"][pj_id] = species

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
    try:
        response = flask.make_response(tc.render_tool_pending(async_result, tool))
    except Exception as e:
        sys.stderr.write(str(e))
    response.status_code = 303
    response.headers['location'] = new_location

    return response

#@mset_blueprint.route('/api/tool/MSET.html', methods=['GET'])
def run_tool_api(apikey, background, species, samples, genesets):
    # TODO need to check for read permissions on genesets

    user_id = gwdb.get_user_id_by_apikey(apikey)

    # pull out the selected geneset IDs
    selected_geneset_ids = genesets.split(':')
    if len(selected_geneset_ids) < 3:
        # TODO add nice error message about missing genesets
        raise Exception('there must be at least three genesets selected to run this tool')

    # gather the params into a dictionary
    bg_str = 'Background'
    sp_str = 'Species'
    samp_str = 'NumberofSamples'
    params = {bg_str: None, samp_str: None, sp_str: None}
    bg_params = ["CTD", "NIF", "ABA", "GWAS", "DRG", "GO", "MP", "HP", "MESH", "KEGG", "MSigDB", "PC", "OMIM",
                 "GTex", "Entrez", "Ensembl Gene", "Ensembl Protein", "Ensembl Transcript", "Unigene",
                 "Gene Symbol", "Unannotated", "MGI", "HGNC", "RGD", "ZFIN", "FlyBase", "Wormbase", "SGD",
                 "miRBase", "CGNC"]
    sp_params = ["Mus musculus", "Homo sapiens", "Rattus norvegicus", "Danio rerio", "Drosophila melanogaster",
                 "Macaca mulatta", "Caenorhabditis elegans", "Saccharomyces cerevisiae", "Gallus gallus",
                 "Canis familiaris"]
    samp_params = ['100', '1000', '5000', '10000']
    for tool_param in gwdb.get_tool_params(TOOL_CLASSNAME, True):
        if tool_param.name.endswith('_' + bg_str):
            params[tool_param.name] = background
            if background not in bg_params:
                params[tool_param.name] = 'CTD'
            if tool_param.name.endswith('_' + sp_str):
                params[tool_param.name] = species
            if species not in sp_params:
                params[tool_param.name] = 'Mus musculus'
        if tool_param.name.endswith('_' + samp_str):
            params[tool_param.name] = samples
            if samples not in samp_params:
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
        async_result = json.loads(async_result.result)
        # results are ready. render the page for the user


        ignore = 0
        geneset = []
        try:
            tgId = async_result["gs_dict"]["tgId"]
            intId = async_result["gs_dict"]["intId"]
            num_genes = async_result["gs_dict"]["num_genes"]

            if num_genes > 300:
                ignore = 1
                geneset = gwdb.get_geneset_values_for_mset_small(tgId, intId)
                #sys.stderr.write(str(geneset) + '\n')
            else:
                sys.stderr.write("\n**************\n" + tgId + '\n')
                sys.stderr.write(intId + "\n")

                geneset = gwdb.get_genes_for_mset(tgId, intId)
                sys.stderr.write(str(geneset) + '\n')
                #sys.stderr.write(str(geneset[0]) + '\n')
                #sys.stderr.write(str(geneset.geneset_values[0].source_list[0]) + '\n')
        except Exception as e:
            sys.stderr.write(e.message() + '\n')
            ignore = 1


        sys.stderr.write('Finished getting gene info\n')
        return flask.render_template(
            'tool/MSET_result.html',
            data=data,
            async_result=async_result, geneset=geneset,
            colors=HOMOLOGY_BOX_COLORS, tt=SPECIES_NAMES, ignore=ignore,
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


