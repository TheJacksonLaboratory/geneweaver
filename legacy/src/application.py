#Kelechi was here
# So was Caylee C.
# Here Again.
import flask
from flask.ext.admin import Admin, BaseView, expose
from flask.ext.admin.base import MenuLink
from flask.ext import restful
from flask import request, send_file, Response, make_response, session
from decimal import Decimal
from urlparse import parse_qs, urlparse
import adminviews
import genesetblueprint
import geneweaverdb
import uploadfiles
import json
import os
import os.path as path
import re
import urllib
import urllib3
from collections import OrderedDict, defaultdict
from tools import genesetviewerblueprint, jaccardclusteringblueprint, jaccardsimilarityblueprint, phenomemapblueprint, \
    combineblueprint, abbablueprint, booleanalgebrablueprint, tricliqueblueprint
import sphinxapi
import search

app = flask.Flask(__name__)
app.register_blueprint(abbablueprint.abba_blueprint)
app.register_blueprint(combineblueprint.combine_blueprint)
app.register_blueprint(genesetblueprint.geneset_blueprint)
app.register_blueprint(genesetviewerblueprint.geneset_viewer_blueprint)
app.register_blueprint(phenomemapblueprint.phenomemap_blueprint)
app.register_blueprint(jaccardclusteringblueprint.jaccardclustering_blueprint)
app.register_blueprint(jaccardsimilarityblueprint.jaccardsimilarity_blueprint)
app.register_blueprint(booleanalgebrablueprint.boolean_algebra_blueprint)
app.register_blueprint(tricliqueblueprint.triclique_viewer_blueprint)

# TODO this key must be changed to something secret (ie. not committed to the repo).
# Comment out the print message when this is done
print '==================================================='
print 'THIS VERSION OF GENEWEAVER IS NOT SECURE. YOU MUST '
print 'REGENERATE THE SECRET KEY BEFORE DEPLOYMENT. SEE   '
print '"How to generate good secret keys" AT			  '
print 'http://flask.pocoo.org/docs/quickstart/ FOR DETAILS'
print '==================================================='
app.secret_key = '\x91\xe6\x1e \xb2\xc0\xb7\x0e\xd4f\x058q\xad\xb0V\xe1\xf22\xa5\xec\x1e\x905'


# *************************************

admin = Admin(app, name='Geneweaver', index_view=adminviews.AdminHome(
    url='/admin', name='Admin'))

admin.add_view(
    adminviews.Viewers(name='Users', endpoint='viewUsers', category='User Tools'))
admin.add_view(adminviews.Viewers(
    name='Publications', endpoint='viewPublications', category='User Tools'))
admin.add_view(adminviews.Viewers(
    name='Groups', endpoint='viewGroups', category='User Tools'))
admin.add_view(adminviews.Viewers(
    name='Projects', endpoint='viewProjects', category='User Tools'))
admin.add_view(adminviews.Viewers(
    name='Files', endpoint='viewFiles', category='User Tools'))

admin.add_view(adminviews.Viewers(
    name='Genesets', endpoint='viewGenesets', category='Gene Tools'))
admin.add_view(
    adminviews.Viewers(name='Genes', endpoint='viewGenes', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='Geneset Info', endpoint='viewGenesetInfo', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='Gene Info', endpoint='viewGeneInfo', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='Geneset Value', endpoint='viewGenesetVals', category='Gene Tools'))

admin.add_view(adminviews.Add(name='User', endpoint='newUser', category='Add'))
admin.add_view(
    adminviews.Add(name='Publication', endpoint='newPub', category='Add'))
admin.add_view(
    adminviews.Add(name='Group', endpoint='newGroup', category='Add'))
admin.add_view(
    adminviews.Add(name='Project', endpoint='newProject', category='Add'))
admin.add_view(
    adminviews.Add(name='Geneset', endpoint='newGeneset', category='Add'))
admin.add_view(adminviews.Add(name='Gene', endpoint='newGene', category='Add'))
admin.add_view(
    adminviews.Add(name='Geneset Info', endpoint='newGenesetInfo', category='Add'))
admin.add_view(
    adminviews.Add(name='Gene Info', endpoint='newGeneInfo', category='Add'))

admin.add_link(MenuLink(name='My Account', url='/accountsettings.html'))

#*************************************

RESULTS_PATH = '/var/www/html/dev-geneweaver/results/'

HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']
SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiaw', 'Gallus gallus',
                 'Canis familiaris']


@app.route('/results/<path:filename>')
def static_results(filename):
    return flask.send_from_directory(RESULTS_PATH, filename)


# TODO the newsArray should probably be moved to a configuration file
newsArray = [
    (
    "2013: GeneWeaver user publication",
    '''
    <a href="http://www.ncbi.nlm.nih.gov/pubmed/23123364">Potential translational
    targets revealed by linking mouse grooming behavioral phenotypes to gene
    expression using public databases</a> Andrew Roth, Evan J. Kyzar, Jonathan Cachat,
    Adam Michael Stewart, Jeremy Green, Siddharth Gaikwad, Timothy P. O'Leary,
    Boris Tabakoff, Richard E. Brown, Allan V. Kalueff. Progress in Neuro-Psychopharmacology
    & Biological Psychiatry 40:313-325.
    '''
    ),
    (
    "2013: GeneWeaver user publication (Includes Deposited Data)",
    '''
    <a href="http://www.ncbi.nlm.nih.gov/pubmed/23329330">Mechanistic basis of infertility
    of mouse intersubspecific hybrids</a> Bhattacharyya T, Gregorova S, Mihola O, Anger M,
    Sebestova J, Denny P, Simecek P, Forejt J. PNAS 2013 110 (6) E468-E477.
    '''
    ),
    (
    "2012: GeneWeaver Publication",
    '''
    <a href="http://www.ncbi.nlm.nih.gov/pubmed/23195309">Cross species integration of
    functional genomics experiments.</a>Jay, JJ. Int Rev Neurobiol 104:1-24.
    '''
    ),
    (
    "Oct 2012: GeneWeaver user publication",
    '''
    <a href="http://www.ncbi.nlm.nih.gov/pubmed/22961259">The Mammalian Phenotype Ontology
    as a unifying standard for experimental and high-throughput phenotyping data.</a>
    Smith CL, Eppig JT. Mamm Genome. 23(9-10):653-68
    '''
    ),
]


# the context processor will inject global variables for us so
# that we can refer to them from our flask templates
@app.context_processor
def inject_globals():
    global_map = {
    'newsArray': newsArray
    }

    return global_map


@app.before_request
def lookup_user_from_session():
    # lookup the current user if the user_id is found in the session
    user_id = flask.session.get('user_id')
    if user_id:
        if flask.request.remote_addr == flask.session.get('remote_addr'):
            flask.g.user = geneweaverdb.get_user(user_id)
        else:
            # If IP addresses don't match we're going to reset the session for
            # a bit of extra safety. Unfortunately this also means that we're
            # forcing valid users to log in again when they change networks
            _logout()


@app.route('/logout')
def _logout():
    try:
        del flask.session['user_id']
    except KeyError:
        pass
    try:
        del flask.session['remote_addr']
    except KeyError:
        pass

    try:
        del flask.g.user
    except AttributeError:
        pass


def _form_login():
    user = None
    _logout()

    form = flask.request.form
    if 'usr_email' in form:
        # TODO deal with login failure
        user = geneweaverdb.authenticate_user(
            form['usr_email'], form['usr_password'])
        if user is not None:
            flask.session['user_id'] = user.user_id
            remote_addr = flask.request.remote_addr
            if remote_addr:
                flask.session['remote_addr'] = remote_addr

    flask.g.user = user
    return user


def send_mail(to, subject, body):
    print to, subject, body
    sendmail_location = "/usr/bin/mail"  # sendmail location
    p = os.popen("%s -t" % sendmail_location, "w")
    p.write("From: NoReply@geneweaver.org\n")
    p.write("To: %s\n" % to)
    p.write("Subject: %s\n" % subject)
    p.write("\n")  # blank line separating headers from body
    p.write(body)
    status = p.close()
    if status != 0:
        print "Sendmail exit status", status


def _form_register():
    user = None
    _logout()

    form = flask.request.form
    if 'usr_email' in form:
        user = geneweaverdb.get_user_byemail(form['usr_email'])
        if user is not None:
            return None
        else:
            user = geneweaverdb.register_user(
                form['usr_first_name'], form['usr_last_name'], form['usr_email'], form['usr_password'])
            return user


@app.route('/logout.json', methods=['GET', 'POST'])
def json_logout():
    _logout()
    return flask.jsonify({'success': True})


@app.route('/login.json', methods=['POST'])
def json_login():
    json_result = dict()
    user = _form_login()
    if user is None:
        json_result['success'] = False
        return flask.redirect(flask.url_for('render_login_error'))
    else:
        json_result['success'] = True
        json_result['usr_first_name'] = user.first_name
        json_result['usr_last_name'] = user.last_name
        json_result['usr_email'] = user.email

    # return flask.jsonify(json_result)
    return flask.redirect("index.html")


@app.route('/analyze')
def render_analyze():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('analyze.html', active_tools=active_tools)

@app.route('/projects')
def render_projects():
    return flask.render_template('projects.html')

@app.route("/gwdb/get_group/<user_id>/")
def get_group(user_id):
    return geneweaverdb.get_all_member_groups(user_id)


@app.route("/gwdb/create_group/<group_name>/<group_private>/<user_id>/")
def create_group(group_name, group_private, user_id):
    return geneweaverdb.create_group(group_name, group_private, user_id)


@app.route("/gwdb/add_user_group/<group_name>/<user_id>/<user_email>/")
def add_user_group(group_name, user_id, user_email):
    print(user_email)
    return geneweaverdb.add_user_to_group(group_name, user_id, user_email)


@app.route("/gwdb/remove_user_group/<group_name>/<user_id>/<user_email>/")
def remove_user_group(group_name, user_id, user_email):
    return geneweaverdb.remove_user_from_group(group_name, user_id, user_email)


@app.route("/gwdb/delete_group/<group_name>/<user_id>/")
def delete_group(group_name, user_id):
    geneweaverdb.delete_group(group_name, user_id)
    return flask.redirect("/accoutnsetings.html")


@app.route('/share_projects.html')
def render_shareprojects():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('share_projects.html', active_tools=active_tools)


@app.route('/analyze_new_project/<string:pj_name>.html')
def render_analyze_new_project(pj_name):
    print 'dbg analyze proj'
    args = flask.request.args
    active_tools = geneweaverdb.get_active_tools()
    user = geneweaverdb.get_user(flask.session.get('user_id'))
    geneweaverdb.create_project(pj_name, user.user_id)
    return flask.render_template('analyze.html', active_tools=active_tools)


@app.route('/editgeneset/<int:gs_id>')
def render_editgenesets(gs_id):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    species = geneweaverdb.get_all_species()
    pubs = geneweaverdb.get_all_publications(gs_id)
    #onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id)
    user_info = geneweaverdb.get_user(user_id)
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None

    onts = None
    return flask.render_template('editgenesets.html', geneset=geneset, user_id=user_id, species=species, pubs=pubs,
                                 view=view, onts=onts)


@app.route('/updategeneset', methods=['POST'])
def update_geneset():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        result = geneweaverdb.updategeneset(user_id, flask.request.form)
        data = dict()
        data.update({"success": result})
        data.update({'usr_id': user_id})
        return json.dumps(data)


@app.route('/editgenesetgenes/<int:gs_id>')
def render_editgeneset_genes(gs_id):
    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0
    user_info = geneweaverdb.get_user(user_id)
    uploadfiles.create_temp_geneset_from_value(gs_id)
    meta = uploadfiles.get_temp_geneset_gsid(gs_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id, temp='temp')
    species = geneweaverdb.get_all_species()
    platform = geneweaverdb.get_microarray_types()
    idTypes = geneweaverdb.get_gene_id_types()
    #onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id)
    onts = None
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None

    ####################################
    # Build dictionary of all possible
    # menus options
    gidts = {}
    pidts = {}
    for id in idTypes:
        gidts[id['gdb_id']] = id['gdb_shortname']
    for p in platform:
        pidts[p['pf_shortname']] = p['pf_name']
    return flask.render_template('editgenesetsgenes.html', geneset=geneset, user_id=user_id, species=species,
                                 gidts=gidts, pidts=pidts, onts=onts, view=view, meta=meta)


@app.route('/setthreshold/<int:gs_id>')
def render_set_threshold(gs_id):
    d3BarChart = []
    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0
    user_info = geneweaverdb.get_user(user_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None
    ## Determine if this is bi-modal, we won't display these
    is_bimodal = geneweaverdb.get_bimodal_threshold(gs_id)
    gsv_values = geneweaverdb.get_all_geneset_values(gs_id)
    threshold = str(geneset.threshold)
    thresh = threshold.split(',')
    if len(thresh) == 1:
        thresh.append(str(0))
    i = 1
    minVal = float(thresh[0])
    maxVal = float(thresh[1])
    valArray = []
    if gsv_values is not None:
        for k in gsv_values:
            valArray.append(float(k.values()[0]))
            maxVal = float(k.values()[0]) if float(k.values()[0]) > maxVal else maxVal
            minVal = float(k.values()[0]) if float(k.values()[0]) < minVal else minVal
            d3BarChart.append(
                {'x': i, 'y': float(k.values()[0]), 'gsid': str(k.values()[1]), 'abr': str(k.values()[0])})
            i += 1
    json.dumps(d3BarChart, default=decimal_default)
    return flask.render_template('viewThreshold.html', geneset=geneset, user_id=user_id, view=view,
                                 is_bimodal=is_bimodal,
                                 d3BarChart=d3BarChart, threshold=thresh, minVal=minVal, maxVal=maxVal,
                                 valArray=valArray)


@app.route('/saveThresholdValues', methods=['GET'])
def save_threshold_values():
    if 'user_id' in flask.session:
        try:
            float(str(request.args['min']))
            float(str(request.args['max']))
        except ValueError:
            results = {'error': 'No Threshold values were selected'}
            return json.dumps(results)
    results = geneweaverdb.update_threshold_values(request.args)
    return json.dumps(results)


@app.route('/updateGenesetGenes', methods=['GET'])
def update_geneset_genes():
    if 'user_id' in flask.session:
        user_id = request.args['user_id']
        gs_id = request.args['gs_id']
        if geneweaverdb.get_user(user_id).is_admin != 'False' or geneweaverdb.get_user(user_id).is_curator != 'False' \
                or geneweaverdb.user_is_owner(user_id, gs_id) != 0:
            results = uploadfiles.insert_into_geneset_value_by_gsid(gs_id)
            return json.dumps(results)


@app.route('/deleteProjectByID', methods=['GET'])
def delete_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.delete_project_by_id(flask.request.args['projids'])
        return json.dumps(results)


@app.route('/addProjectByName', methods=['GET'])
def add_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.add_project_by_name(flask.request.args['name'])
        return json.dumps(results)


@app.route('/changeProjectNameById', methods=['GET'])
def rename_project():
    if 'user_id' in flask.session:
        results = geneweaverdb.change_project_by_id(flask.request.args)
        return json.dumps(results)


@app.route('/accountsettings')
def render_accountsettings():
    user = geneweaverdb.get_user(flask.session.get('user_id'))
    groupsMemberOf = geneweaverdb.get_all_member_groups(flask.session.get('user_id'))
    groupsOwnerOf = geneweaverdb.get_all_owned_groups(flask.session.get('user_id'))
    return flask.render_template('accountsettings.html', user=user, groupsMemberOf=groupsMemberOf,
                                 groupsOwnerOf=groupsOwnerOf)

@app.route('/login.html')
def render_login():
    return flask.render_template('login.html')


@app.route('/login_error')
def render_login_error():
    return flask.render_template('login.html', error="Invalid Credentials")


@app.route('/resetpassword.html')
def render_forgotpass():
    return flask.render_template('resetpassword.html')


#### viewStoredResults
##
#### Only called by an ajax request when the user wants to view a saved
#### tool result from the results page. The result run hash and user ID
#### are passed via a POST request, then the function retrieves the result
#### data from the DB and chooses the correct result template to display.
##
@app.route('/viewStoredResults', methods=['POST'])
def viewStoredResults_by_runhash():
    if request.method == 'POST':
        form = flask.request.form
        user_id = form['user_id']
        results = geneweaverdb.get_results_by_runhash(form['runHash'])
        results = results[0][0]

        if results['res_tool'] == 'Jaccard Similarity':
            return flask.render_template(
                'tool/JaccardSimilarity_result.html',
                async_result=json.loads(results['res_data']),
                tool=geneweaverdb.get_tool('JaccardSimilarity'),
                list=geneweaverdb.get_all_projects(user_id))

        elif results['res_tool'] == 'HiSim Graph':
            return flask.render_template(
                'tool/PhenomeMap_result.html',
                async_result=json.loads(results['res_data']),
                tool=geneweaverdb.get_tool('PhenomeMap'),
                runhash=form['runHash'])

        elif results['res_tool'] == 'GeneSet Graph':
            return flask.render_template(
                'tool/GeneSetViewer_result.html',
                async_result=json.loads(results['res_data']),
                tool=geneweaverdb.get_tool('GeneSetViewer'),
                list=geneweaverdb.get_all_projects(user_id))

        elif results['res_tool'] == 'Clustering':
            return flask.render_template(
                'tool/GeneSetViewer_result.html',
                async_result=json.loads(results['res_data']),
                tool=geneweaverdb.get_tool('JaccardClustering'),
                list=geneweaverdb.get_all_projects(user_id))


@app.route('/reruntool.json', methods=['POST', 'GET'])
def rerun_tool():
    args = flask.request.args
    user_id = args['user_id']
    results = geneweaverdb.get_results_by_runhash(args['runHash'])
    results = results[0][0]
    data = json.loads(results['res_data'])
    tool = results['res_tool']
    params = data['parameters']

    ## inconsistent naming conventions
    if data.get('gs_ids', None) and data['gs_ids']:
        gs_ids = data['gs_ids']
    elif data.get('genesets', None) and data['genesets']:
        gs_ids = data['genesets']
    else:
        gs_ids = []

    return json.dumps({'tool': tool, 'parameters': params, 'gs_ids': gs_ids})


@app.route('/createtempgeneset', methods=["POST", "GET"])
def create_geneset_meta():
    if 'user_id' in flask.session:
        if int(request.args['sp_id']) == 0:
            return json.dumps({'error': 'You must select a species.'})
        if str(request.args['gdb_id']) == '0':
            return json.dumps({'error': 'You must select an identifier.'})
        ## Create the geneset in upload genesets. The new geneset is set to 'delayed'
        ## and will be updated whenever the editgenesetgenes are verified.
        results = uploadfiles.create_new_geneset(request.args)
        return json.dumps(results)
    else:
        return json.dumps({'error': 'You must be logged in to create a geneset'})


@app.route('/viewgenesetdetails/<int:gs_id>', methods=['GET', 'POST'])
def render_viewgeneset(gs_id):
    # get values for sorting result columns
    # i'm saving these to a session variable
    # probably not the correct format
    if flask.request.method == 'GET':
        args = flask.request.args
        if 'sort' in args:
            session['sort'] = args['sort']
            if 'dir' in session:
                if session['dir'] != 'DESC':
                    session['dir'] = 'DESC'
                else:
                    session['dir'] = 'ASC'
            else:
                session['dir'] = 'ASC'
    # get value for the alt-gene-id column
    if 'extsrc' in session:
        if session['extsrc'] == 2:
            altGeneSymbol = 'Ensembl'
        elif session['extsrc'] == 7:
            altGeneSymbol = 'Symbol'
        elif session['extsrc'] == 10:
            altGeneSymbol = 'MGD'
        elif session['extsrc'] == 12:
            altGeneSymbol = 'RGD'
        elif session['extsrc'] == 13:
            altGeneSymbol = 'ZFin'
        elif session['extsrc'] == 14:
            altGeneSymbol = 'FlyBase'
        elif session['extsrc'] == 15:
            altGeneSymbol = 'WormBase'
        else:
            altGeneSymbol = 'Entrez'
    else:
        altGeneSymbol = 'Entrez'

    emphgenes = {}
    emphgeneids = []

    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0

    user_info = geneweaverdb.get_user(user_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id)

    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))
    return flask.render_template('viewgenesetdetails.html', geneset=geneset, emphgeneids=emphgeneids, user_id=user_id,
                                 colors=HOMOLOGY_BOX_COLORS, tt=SPECIES_NAMES, altGeneSymbol=altGeneSymbol, view=view)


@app.route('/mygenesets')
def render_user_genesets():
    table = 'production.geneset'
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        columns = []
        columns.append({'name': 'sp_id'})
        columns.append({'name': 'cur_id'})
        columns.append({'name': 'gs_attribution'})
        columns.append({'name': 'gs_count'})
        columns.append({'name': 'gs_id'})
        columns.append({'name': 'gs_name'})
        headerCols = ["", "Species", "Tier", "Source", "Count", "ID", "Name", ""]
    else:
        headerCols, user_id, columns = None, 0, None
    return flask.render_template('mygenesets.html', headerCols=headerCols, user_id=user_id, columns=columns,
                                 table=table)


def top_twenty_simgenesets(simgs):
    """
    iterates through all results and picks the top twenty genesets that do not have > 0.95 jac overlap
    with the previous set.
    :param simgs:
    :return: set of top twenty
    """
    d = []
    k = 0
    j = 1
    d.append(simgs[k])
    while len(d) < 21:
        gs_id = simgs[k].geneset_id
        next_gs_id = simgs[j].geneset_id
        if geneweaverdb.compare_geneset_jac(gs_id, next_gs_id) == 1:
            j += 1
        else:
            d.append(simgs[j])
            k = j
            j += 1
    return d


def decimal_default(obj):
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


@app.route('/viewSimilarGenesets/<int:gs_id>')
def render_sim_genesets(gs_id):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    # Get GeneSet Info for the MetaData
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    # Returns a subClass of geneset that includes jac values
    simgs = geneweaverdb.get_similar_genesets(gs_id, user_id)
    # Returns a list os all active sp_ids
    sp_id = geneweaverdb.get_sp_id()
    # Initiate variables
    tier1, tier2, tier3, tier4, tier5 = ([] for i in range(5))
    d3Data = []
    d3BarChart = []
    max = 0
    # OK, OK, This is nasty. Loop through all curation tiers, then,
    # for each curation tier, Loop through all species. Then, Loop through
    # all cur - sp_id sets in the simgs set to find the average values and
    # add this to the list of list(dict).
    for i in range(1, 6):
        for l in sp_id:
            t = 0
            counter = 0
            for k in simgs:
                if k.cur_id == i and k.sp_id == l['sp_id']:
                    t += k.jac_value
                    counter += 1
            # Make sure that we don't divde by zero
            if counter > 0:
                avg = t / counter
            else:
                avg = 0
            # We need to set a max in order to ensure that the d3 graph is scaled correctly
            if avg > max:
                max = avg
            if i == 1:
                tier1.append({'axis': geneweaverdb.get_species_name_by_id(l['sp_id']), 'value': float(avg)})
            elif i == 2:
                tier2.append({'axis': geneweaverdb.get_species_name_by_id(l['sp_id']), 'value': float(avg)})
            elif i == 3:
                tier3.append({'axis': geneweaverdb.get_species_name_by_id(l['sp_id']), 'value': float(avg)})
            elif i == 4:
                tier4.append({'axis': geneweaverdb.get_species_name_by_id(l['sp_id']), 'value': float(avg)})
            elif i == 5:
                tier5.append({'axis': geneweaverdb.get_species_name_by_id(l['sp_id']), 'value': float(avg)})
    # This is the bit for the bar chart
    i = 1
    for k in simgs:
        d3BarChart.append({'x': i, 'y': float(k.jac_value), 'gsid': int(k.geneset_id), 'abr': str(k.abbreviation)})
        i += 1
    d3Data.extend([tier1, tier2, tier3, tier4, tier5])
    json.dumps(d3Data, default=decimal_default)
    json.dumps(d3BarChart, default=decimal_default)
    return flask.render_template('similargenesets.html', geneset=geneset, user_id=user_id, gs_id=gs_id, simgs=simgs,
                                 d3Data=d3Data, max=max, d3BarChart=d3BarChart)


@app.route('/getPubmed', methods=['GET', 'POST'])
def get_pubmed_data():
    pubmedValues = []
    http = urllib3.PoolManager()
    if flask.request.method == 'GET':
        args = flask.request.args
        if 'pmid' in args:
            pmid = args['pmid']
            PM_DATA = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml'
            #response = http.urlopen('GET', PM_DATA % (','.join([str(x) for x in pmid]),)).read()
            response = http.urlopen('GET', PM_DATA % (pmid), ).read()

            for match in re.finditer('<PubmedArticle>(.*?)</PubmedArticle>', response, re.S):
                article_ids = {}
                abstract = ''
                fulltext_link = None

                article = match.group(1)
                articleid_matches = re.finditer('<ArticleId IdType="([^"]*)">([^<]*?)</ArticleId>', article, re.S)
                abstract_matches = re.finditer('<AbstractText([^>]*)>([^<]*)</AbstractText>', article, re.S)
                articletitle = re.search('<ArticleTitle[^>]*>([^<]*)</ArticleTitle>', article, re.S).group(1).strip()

                for amatch in articleid_matches:
                    article_ids[amatch.group(1).strip()] = amatch.group(2).strip()
                for amatch in abstract_matches:
                    abstract += amatch.group(2).strip() + ' '

                if 'pmc' in article_ids:
                    fulltext_link = 'http://www.ncbi.nlm.nih.gov/pmc/articles/%s/' % (article_ids['pmc'],)
                elif 'doi' in article_ids:
                    fulltext_link = 'http://dx.crossref.org/%s' % (article_ids['doi'],)
                pmid = article_ids['pubmed'].strip()

                author_matches = re.finditer('<Author [^>]*>(.*?)</Author>', article, re.S)
                authors = []
                for match in author_matches:
                    name = ''
                    try:
                        name = re.search('<LastName>([^<]*)</LastName>', match.group(1), re.S).group(1).strip()
                        name = name + ' ' + re.search('<Initials>([^<]*)</Initials>', match.group(1), re.S).group(
                            1).strip()
                    except:
                        pass
                    authors.append(name)

                authors = ', '.join(authors)
                v = re.search('<Volume>([^<]*)</Volume>', article, re.S)
                vol = v.group(1).strip()
                p = re.search('<MedlinePgn>([^<]*)</MedlinePgn>', article, re.S)
                pages = p.group(1).strip()
                pubdate = re.search('<PubDate>.*?<Year>([^<]*)</Year>.*?<Month>([^<]*)</Month>', article, re.S)
                year = pubdate.group(1).strip()
                journal = re.search('<MedlineTA>([^<]*)</MedlineTA>', article, re.S).group(1).strip()
                # year month journal
                tomonthname = {
                '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr', '5': 'May', '6': 'Jun',
                '7': 'Jul', '8': 'Aug', '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
                }
                pm = pubdate.group(2).strip()
                if pm in tomonthname:
                    pm = tomonthname[pm]

                pubmedValues.extend((articletitle, authors, journal, vol, pages, year, pm, abstract))

        else:
            response = 'false'
    else:
        response = 'false'
    return json.dumps(pubmedValues)


@app.route('/exportGeneList/<int:gs_id>')
def render_export_genelist(gs_id):
    if 'user_id' in flask.session:
        str = ''
        results = geneweaverdb.export_results_by_gs_id(gs_id)
        for k in results:
            str = str + k + ',' + results[k] + '\n'
        response = make_response(str)
        response.headers["Content-Disposition"] = "attachment; filename=geneset_export.csv"
        return response


@app.route('/exportJacGeneList/<int:gs_id>')
def render_export_jac_genelist(gs_id):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    string = ''
    results = geneweaverdb.get_similar_genesets(gs_id, user_id)
    for k in results:
        string = string + str(k.geneset_id) + ',' + k.name + ',' + k.abbreviation + ',' + str(k.count) + ',' + str(
            k.jac_value) + '\n'
    response = make_response(string)
    response.headers["Content-Disposition"] = "attachment; filename=geneset_export.csv"
    return response


@app.route('/findPublications/<int:gs_id>')
def render_view_same_publications(gs_id):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    results = geneweaverdb.get_similar_genesets_by_publication(gs_id, user_id)
    return flask.render_template('viewsamepublications.html', user_id=user_id, gs_id=gs_id, geneset=results)


@app.route('/emphasis.html', methods=['GET', 'POST'])
def render_emphasis():
    '''
    Emphasis_AddGene
    Emphasis_RemoveGene
    Emphasis_RemoveAllGenes
    Emphasis_SearchGene
    '''

    foundgenes = {}
    emphgenes = {}
    emphgeneids = []
    user_id = flask.session['user_id']
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))

    if flask.request.method == 'POST':
        form = flask.request.form

        if 'Emphasis_SearchGene' in form:
            search_gene = form['Emphasis_SearchGene']
            foundgenes = geneweaverdb.get_gene_and_species_info(search_gene)

    elif flask.request.method == 'GET':
        args = flask.request.args

        if 'Emphasis_AddGene' in args:
            add_gene = args['Emphasis_AddGene']
            if add_gene:
                geneweaverdb.create_usr2gene(user_id, add_gene)

        if 'Emphasis_AddAllGenes' in args:
            add_all_genes = args['Emphasis_AddAllGenes']
            if add_all_genes:
                genes_list = add_all_genes.split(' ')
                for gene in genes_list:
                    if not str(gene) in emphgeneids:
                        geneweaverdb.create_usr2gene(user_id, gene)

        if 'Emphasis_RemoveGene' in args:
            remove_gene = args['Emphasis_RemoveGene']
            if remove_gene:
                geneweaverdb.delete_usr2gene_by_user_and_gene(user_id, remove_gene)

        if 'Emphasis_RemoveAllGenes' in args:
            if args['Emphasis_RemoveAllGenes'] == 'yes':
                geneweaverdb.delete_usr2gene_by_user(user_id)

    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    return flask.render_template('emphasis.html', emphgenes=emphgenes, foundgenes=foundgenes)


@app.route('/emphasize/<string:add_gene>.html', methods=['GET', 'POST'])
def emphasize(add_gene):
    user_id = flask.session['user_id']
    return str(geneweaverdb.create_usr2gene(user_id, add_gene))


@app.route('/deemphasize/<string:rm_gene>.html', methods=['GET', 'POST'])
def deemphasize(rm_gene):
    user_id = flask.session['user_id']
    return str(geneweaverdb.delete_usr2gene_by_user_and_gene(user_id, rm_gene))


@app.route('/search.html')
def new_search():
    print 'debug new_search'
    paginationValues = {'numResults': 0, 'numPages': 1, 'currentPage':
        1, 'resultsPerPage': 10, 'search_term': '', 'end_page_number': 1}
    return flask.render_template('search.html', paginationValues=None)


@app.route('/search/')
def render_searchFromHome():
    form = flask.request.form
    ## Terms from the search bar, as a list since there can be <= 3 terms
    terms = request.args.getlist('searchbar')
    sortby = request.args.get('sortBy')

    ## If terms is empty, we can assume a) the user submitted a blank search,
    ## or b) the user clicked on the search link. Both are handled the same way
    if not terms or (len(terms) == 1 and not terms[0]):
        return flask.render_template('search.html', paginationValues=None)

    if flask.request.method == 'GET':
        args = flask.request.args
    #pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    pagination_page = int(request.args.get('pagination_page'))
    #Build a list of search fields selected by the user (checkboxes) passed in as URL parameters
    #Associate the correct fields with each option given by the user
    field_list = {'searchGenesets': False, 'searchGenes': False, 'searchAbstracts': False, 'searchOntologies': False}
    search_fields = list()
    #Set which fields of GS data to search
    if (request.args.get('searchGenesets')):
        search_fields.append('name,description,label')
        field_list['searchGenesets'] = True
    if (request.args.get('searchGenes')):
        search_fields.append('genes')
        field_list['searchGenes'] = True
    if (request.args.get('searchAbstracts')):
        search_fields.append('pub_authors,pub_title,pub_abstract,pub_journal')
        field_list['searchAbstracts'] = True
    if (request.args.get('searchOntologies')):
        search_fields.append('ontologies')
        field_list['searchOntologies'] = True
    #Add the default case, at least be able to search these values for all searches
    search_fields.append('gs_id,gsid_prefixed,species,taxid')
    search_fields = ','.join(search_fields)
    #Perform a search
    search_values = search.keyword_paginated_search(terms, pagination_page,
                                                    search_fields, {}, sortby)
    #If there is an error render a blank search page
    if (search_values['STATUS'] == 'ERROR'):
        return flask.render_template('search.html', paginationValues=None)
    #print 'debug genesets: ' + str(search_values['genesets'][0])
    #render the template if there is no error, passing in data used in display
    return flask.render_template('search.html', searchresults=search_values['searchresults'],
                                 genesets=search_values['genesets'], paginationValues=search_values['paginationValues'],
                                 field_list=field_list, searchFilters=search_values['searchFilters'],
                                 filterLabels=search_values['filterLabels'])


@app.route('/searchFilter.json', methods=['POST'])
#This route will take as an argument, search parameters for a filtered search
def render_search_json():
    #Get the user values from the request
    userValues = search.getUserFiltersFromApplicationRequest(request.form)
    ## quick fix for now, this needs properly handle multiple terms
    #print 'debug vals: ' + str(userValues)
    userValues['search_term'] = [userValues['search_term']]
    #Get a sphinx search
    search_values = search.keyword_paginated_search(userValues['search_term'],
                                                    userValues['pagination_page'], userValues['search_fields'],
                                                    userValues['userFilters'], userValues['sort_by'])

    return flask.render_template('search/search_wrapper_contents.html',
                                 searchresults=search_values['searchresults'],  #genesets = search_values['genesets'],
                                 genesets=search_values['genesets'],
                                 paginationValues=search_values['paginationValues'],
                                 field_list=userValues['field_list'],
                                 searchFilters=search_values['searchFilters'],
                                 userFilters=userValues['userFilters'],
                                 filterLabels=search_values['filterLabels'],
                                 sort_by=userValues['sort_by'])



@app.route('/searchsuggestionterms.json')
def render_search_suggestions():
    return flask.render_template('searchsuggestionterms.json')


@app.route('/projectGenesets.json', methods=['GET'])
def render_project_genesets():

    uid = flask.session.get('user_id')
    ## Project (ID) that the user wants to view
    pid = flask.request.args['project']
    genesets = geneweaverdb.get_genesets_for_project(pid, uid)


    return flask.render_template('singleProject.html',
                                 genesets=genesets,
                                 proj={'project_id': pid})

@app.route('/changePvalues/<setSize1>/<setSize2>/<jaccard>', methods=["GET"])
def changePvalues(setSize1, setSize2, jaccard):
    tempDict = geneweaverdb.checkJaccardResultExists(setSize1, setSize2)
    print tempDict
    if(len(tempDict) > 0):
            pValue = geneweaverdb.getPvalue(setSize1,setSize2,jaccard)
    else:
        return json.dumps(-1)

    return json.dumps(pValue)


#****** ADMIN ROUTES ******************************************************************


class AdminEdit(adminviews.Authentication, BaseView):
    @expose('/')
    def __init__(self, *args, **kwargs):
        #self._default_view = True
        super(AdminEdit, self).__init__(*args, **kwargs)
        self.admin = admin


@app.route('/admin/genesetspertier')
def admin_widget_1():
    if "user" in flask.g and flask.g.user.is_admin:
        alldata = geneweaverdb.genesets_per_tier(True)
        nondeleted = geneweaverdb.genesets_per_tier(False)
        species = geneweaverdb.get_species_name()

        data = dict()
        data.update({"all": alldata})
        data.update({"nondeleted": nondeleted})
        data.update({"species": species})
        #print data
        return json.dumps(data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/genesetsperspeciespertier')
def admin_widget_2():
    if "user" in flask.g and flask.g.user.is_admin:
        alldata = geneweaverdb.genesets_per_species_per_tier(True)
        nondeleted = geneweaverdb.genesets_per_species_per_tier(False)
        species = geneweaverdb.get_species_name()

        data = dict()
        data.update({"all": alldata})
        data.update({"nondeleted": nondeleted})
        data.update({"species": species})
        return json.dumps(data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/monthlytoolstats')
def admin_widget_3():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.monthly_tool_stats()
        new_data = OrderedDict()
        for tool in data:
            temp = OrderedDict()
            for key in data[tool]:
                temp.update({str(key).split("-")[1] + "/" + str(key).split("-")[2]: data[tool][key]})
            new_data.update({tool: temp})
        return json.dumps(new_data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/usertoolstats')
def admin_widget_4():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.user_tool_stats()
        return json.dumps(data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/currentlyrunningtools')
def admin_widget_5():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.currently_running_tools()
        #print data
        return json.dumps(data, default=date_handler)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/sizeofgenesets')
def admin_widget_6():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.size_of_genesets()
        #print data
        return json.dumps(data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/timetoruntools')
def admin_widget_7():
    if "user" in flask.g and flask.g.user.is_admin:
        tools = geneweaverdb.tools();
        data = geneweaverdb.gs_in_tool_run()

        geneset_sizes = dict()
        genesets_by_resid = dict()

        all_gs_sizes = []
        for t in tools:
            tool = t['res_tool']
            distinct_sizes = dict()
            for item in data:
                if item['res_tool'] == tool:
                    size = len(item['gs_ids'].split(","))
                    genesets_by_resid.update({item['res_id']: item['gs_ids'].split(",")})
                    if size not in all_gs_sizes:
                        all_gs_sizes.append(size)
                    if size not in distinct_sizes.keys():
                        arr = [item['res_id']]
                        distinct_sizes.update({size: arr})
                    else:
                        arr = distinct_sizes[size]
                        arr.append(item['res_id'])
                        distinct_sizes.update({size: arr})
            geneset_sizes.update({tool: distinct_sizes})

        for item in geneset_sizes:
            for num in geneset_sizes[item]:
                gs = []
                for i in geneset_sizes[item][num]:
                    for j in genesets_by_resid[i]:
                        if j not in gs:
                            gs.append(j)
                avggenes = 0
                if len(gs) > 0:
                    avggenes = geneweaverdb.avg_genes(gs)
                avg = geneweaverdb.avg_tool_times(geneset_sizes[item][num], item)
                geneset_sizes[item][num] = {"time": avg.total_seconds() * 1000, "genes": avggenes}

        dat = []
        for tool in geneset_sizes:
            for size in geneset_sizes[tool]:
                temp = dict();
                time = int(geneset_sizes[tool][size]['time'])
                temp.update({"tool": tool, "size": str(size), "time": time,
                             "genes": str(int(geneset_sizes[tool][size]['genes']))})
                dat.append(temp)

        return json.dumps(dat)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/adminEdit')
def admin_edit():
    if "user" in flask.g and flask.g.user.is_admin:
        rargs = request.args
        table = rargs['table']
        return AdminEdit().render("admin/adminEdit.html", columns=rargs, table=table)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/adminSubmitEdit', methods=['POST'])
def admin_submit_edit():
    if "user" in flask.g and flask.g.user.is_admin:
        form = flask.request.form
        table = form['table']
        prim_keys = geneweaverdb.get_primary_keys(table.split(".")[1])
        keys = []
        for att in prim_keys:
            temp = form[att['attname']]
            keys.append(att['attname'] + "=\'" + temp + "\'")
        status = geneweaverdb.admin_set_edit(form, keys)
        return json.dumps(status)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/adminDelete', methods=['POST'])
def admin_delete():
    if "user" in flask.g and flask.g.user.is_admin:
        form = flask.request.form
        table = form['table']
        prim_keys = geneweaverdb.get_primary_keys(table.split(".")[1])
        keys = []
        for att in prim_keys:
            temp = form[att['attname']]
            keys.append(att['attname'] + "=\'" + temp + "\'")
        result = geneweaverdb.admin_delete(form, keys)
        return json.dumps(result)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/adminAdd', methods=['POST'])
def admin_add():
    if "user" in flask.g and flask.g.user.is_admin:
        form = flask.request.form
        table = form.get('table', type=str)
        result = geneweaverdb.admin_add(form)
        return json.dumps(result)
    else:
        return flask.render_template('admin/adminForbidden.html')


# fetches info for admin viewers
@app.route('/admin/serversidedb')
def get_db_data():
    if "user" in flask.g and flask.g.user.is_admin:
        results = geneweaverdb.get_server_side(request.args)
        return json.dumps(results, default=date_handler)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/getServersideResultsdb')
def get_db_results_data():
    results = geneweaverdb.get_server_side_results(request.args)
    return json.dumps(results)


@app.route('/getServersideGenesetsdb')
def get_db_genesets_data():
    results = geneweaverdb.get_server_side_genesets(request.args)
    return json.dumps(results)


def str_handler(obj):
    return str(obj)


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


#************************************************************************


@app.route('/manage.html')
def render_manage():
    return flask.render_template('my_genesets.html')


@app.route('/share_projects.html')
def render_share_projects():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('share_projects.html', active_tools=active_tools)


@app.route('/addGenesetsToProjects')
def add_genesets_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.add_genesets_to_projects(request.args)
        return json.dumps(results)

@app.route('/removeGenesetFromProject')
def remove_geneset_from_project():
    if 'user_id' in flask.session:
        results = geneweaverdb.remove_geneset_from_project(request.args)
        return json.dumps(results)

@app.route('/deleteGeneset')
def delete_geneset():
    if 'user_id' in flask.session:
        results = geneweaverdb.delete_geneset_by_gsid(request.args)
        return json.dumps(results)


@app.route('/deleteGenesetValueByID', methods=['GET', 'POST'])
def delete_geneset_value():
    if 'user_id' in flask.session:
        results = geneweaverdb.delete_geneset_value_by_id(request.args)
        return json.dumps(results)


@app.route('/editGenesetIdValue', methods=['GET'])
def edit_geneset_id_value():
    if 'user_id' in flask.session:
        results = geneweaverdb.edit_geneset_id_value_by_id(request.args)
        return json.dumps(results)


@app.route('/addGenesetGene', methods=['GET'])
def add_geneset_gene():
    if 'user_id' in flask.session:
        try:
            float(str(request.args['value']))
        except ValueError:
            results = {'error': 'The value you entered (' + str(request.args['value']) + ') must be a number'}
            return json.dumps(results)
        results = geneweaverdb.add_geneset_gene_to_temp(request.args)
        return json.dumps(results)


@app.route('/cancelEditByID', methods=['GET'])
def cancel_edit_by_id():
    if 'user_id' in flask.session:
        results = geneweaverdb.cancel_geneset_edit_by_id(request.args)
        return json.dumps(results)


#### check_results
##
#### Checks to see if a given runhash exists within the results directory.
#### Returns a JSON object with an attribute named 'exists,' which will be
#### set to true if the results are present in the directory.
#### This is used in the results template to make sure we don't view
#### nonexistant/null results.
##
@app.route('/checkResults.json', methods=['GET'])
def check_results():
    if 'user_id' in flask.session:
        runhash = request.args.get('runHash', type=str)

        files = os.listdir(RESULTS_PATH)
        files = filter(lambda f: path.isfile(path.join(RESULTS_PATH, f)), files)
        found = False

        for f in files:
            rh = f.split('.')[0]

            if rh == runhash:
                found = True
                break

        return json.dumps({'exists': found})


@app.route('/deleteResults')
def delete_result():
    if 'user_id' in flask.session:
        results = geneweaverdb.delete_results_by_runhash(request.args)
        runhash = request.args.get('runHash', type=str)

        ## Delete the files from the results folder too--traverse the results
        ## folder and match based on runhash
        files = os.listdir(RESULTS_PATH)
        files = filter(lambda f: path.isfile(path.join(RESULTS_PATH, f)), files)

        for f in files:
            rh = f.split('.')[0]

            if rh == runhash:
                os.remove(path.join(RESULTS_PATH, f))

        return json.dumps(results)


@app.route('/editResults')
def edit_result():
    if 'user_id' in flask.session:
        results = geneweaverdb.edit_results_by_runhash(request.args)
        return json.dumps(results)


@app.route('/results')
def render_user_results():
    table = 'production.result'
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        columns = []
        columns.append({'name': 'res_id'})
        columns.append({'name': 'res_runhash'})
        columns.append({'name': 'res_duration'})
        columns.append({'name': 'res_name'})
        columns.append({'name': 'res_created'})
        columns.append({'name': 'res_description'})
        columns.append({'name': 'res_tool'})
        headerCols = ["", "Name", "Created", "Description", "ID", "RunHash", "Duration"]
    else:
        headerCols, user_id, columns = None, 0, None
    return flask.render_template('results.html', headerCols=headerCols, user_id=user_id, columns=columns, table=table)


@app.route('/updateAltGeneSymbol')
def update_alternate_gene_symbol():
    if 'user_id' in flask.session:
        val = request.args['altSymbol']
        if val == 'EntrezID':
            session['extsrc'] = 1
        elif val == 'EnsemblID':
            session['extsrc'] = 2
        elif val == 'GeneSymbol':
            session['extsrc'] = 7
        elif val == 'MGIID':
            session['extsrc'] = 10
        elif val == 'FlyBaseID':
            session['extsrc'] = 14
        elif val == 'WormBaseID':
            session['extsrc'] = 15
        elif val == 'RGDID':
            session['extsrc'] = 12
        elif val == 'ZFinID':
            session['extsrc'] = 13
        return json.dumps(request.args)


@app.route('/updateGenesetSpecies', methods=['GET'])
def update_geneset_species():
    args = flask.request.args
    if int(flask.session['user_id']) == int(args['user_id']):
        results = uploadfiles.update_species_by_gsid(args)
        return json.dumps(results)


@app.route('/updateGenesetIdentifier', methods=['GET'])
def update_geneset_identifier():
    args = flask.request.args
    if int(flask.session['user_id']) == int(args['user_id']):
        results = uploadfiles.update_identifier_by_gsid(args)
        return json.dumps(results)


@app.route('/help.html')
def render_help():
    return flask.render_template('help.html')


@app.route('/about')
def render_about():
    return flask.render_template('about.html')


@app.route('/funding')
def render_funding():
    return flask.render_template('funding.html')


@app.route('/datasharing')
def render_datasharing():
    return flask.render_template('datasharing.html')


@app.route('/privacy')
def render_privacy():
    return flask.render_template('privacy.html')


@app.route('/usage')
def render_usage():
    return flask.render_template('usage.html')


@app.route('/register.html', methods=['GET', 'POST'])
def render_register():
    return flask.render_template('register.html')


@app.route('/reset.html', methods=['GET', 'POST'])
def render_reset():
    return flask.render_template('reset.html')


# render home if register is successful


@app.route('/register_submit.html', methods=['GET', 'POST'])
def json_register_successful():
    ## Secret key for reCAPTCHA form
    RECAP_SECRET = '6LeO7g4TAAAAAObZpw2KFnFjz1trc_hlpnhkECyS'
    RECAP_URL = 'https://www.google.com/recaptcha/api/siteverify'
    form = flask.request.form
    http = urllib3.PoolManager()
    
    if not form['usr_first_name']:
        return flask.render_template('register.html', error="Please enter your first name.")
    elif not form['usr_last_name']:
        return flask.render_template('register.html', error="Please enter your last name.")
    elif not form['usr_email']:
        return flask.render_template('register.html', error="Please enter your email.")
    elif not form['usr_password']:
        return flask.render_template('register.html', error="Please enter your password.")

    captcha = form['g-recaptcha-response']

    ## No robots
    if not captcha:
        return flask.render_template('register.html', 
		error="There was a problem with your captcha input. Please try again.")

    else:
	## The only data required by reCAPTCHA is secret and response. An
	## optional parameter, remoteip, containing the end user's IP can also
	## be appended.
	pdata = {'secret': RECAP_SECRET, 'response': captcha}
	resp = http.request('POST', RECAP_URL, fields=pdata)

	## 200 = OK
	if resp.status != 200:
	    return flask.render_template('register.html', 
		    error=("There was a problem with the reCAPTCHA servers. "
			   "Please try again."))
	
	rdata = json.loads(resp.data)

	## If success is false, the dict should contain an 'error-code.' This
	## isn't checked currently.
	if not rdata['success']:
	    return flask.render_template('register.html', 
		    error="Incorrect captcha. Please try again.")

    user = _form_register()

    if user is None:
        return flask.render_template('register.html', register_not_successful=True)
    else:
        flask.session['user_id'] = user.user_id
        remote_addr = flask.request.remote_addr
        if remote_addr:
            flask.session['remote_addr'] = remote_addr

    flask.g.user = user
    return flask.render_template('index.html')


@app.route('/reset_submit.html', methods=['GET', 'POST'])
def reset_password():
    form = flask.request.form
    user = geneweaverdb.get_user_byemail(form['usr_email'])
    if user is None:
        return flask.render_template('reset.html', reset_failed=True)
    else:
        new_password = geneweaverdb.reset_password(user.email)
        send_mail(user.email, "Password Reset Request",
                  "Your new temporary password is: " + new_password)
        return flask.render_template('index.html')


@app.route('/change_password', methods=['POST'])
def change_password():
    form = flask.request.form
    if form is None:
        return flask.render_template('accountsettings.html')
    else:
        user = geneweaverdb.get_user(flask.session.get('user_id'))

        if (geneweaverdb.authenticate_user(user.email, form['curr_pass'])) is None:
            return flask.render_template('accountsettings.html', user=user)
        else:
            success = geneweaverdb.change_password(
                user.user_id, form['new_pass'])
            return flask.render_template('accountsettings.html', user=user)


@app.route('/generate_api_key', methods=['POST'])
def generate_api_key():
    geneweaverdb.generate_api_key(flask.session.get('user_id'))
    return flask.redirect('accountsettings.html')


@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    return flask.render_template('index.html')


@app.route('/add_geneset_to_project/<string:project_id>/<string:geneset_id>.html', methods=['GET', 'POST'])
def add_geneset_to_project(project_id, geneset_id):
    return str(geneweaverdb.insert_geneset_to_project(project_id, geneset_id))


@app.route('/create_project/<string:project_name>.html', methods=['GET', 'POST'])
def create_project(project_name):
    user_id = flask.session['user_id']
    return str(geneweaverdb.create_project(project_name, user_id))


@app.template_filter('quoted')
def quoted(s):
    l = re.findall('\'([^\']*)\'', str(s))
    if l:
        return l[0]
    return None

# ********************************************
# START API BLOCK
# ********************************************

api = restful.Api(app)


class GetGenesetsByGeneRefId(restful.Resource):
    def get(self, apikey, gene_ref_id, gdb_name):
        return geneweaverdb.get_genesets_by_gene_id(apikey, gene_ref_id, gdb_name, False)


class GetGenesetsByGeneRefIdHomology(restful.Resource):
    def get(self, apikey, gene_ref_id, gdb_name):
        return geneweaverdb.get_genesets_by_gene_id(apikey, gene_ref_id, gdb_name, True)


class GetGenesByGenesetId(restful.Resource):
    def get(self, genesetid):
        return geneweaverdb.get_genes_by_geneset_id(genesetid)


class GetGeneByGeneId(restful.Resource):
    def get(self, geneid):
        return geneweaverdb.get_gene_by_id(geneid)


class GetGenesetById(restful.Resource):
    def get(self, genesetid):
        return geneweaverdb.get_geneset_by_geneset_id(genesetid)


class GetGenesetByUser(restful.Resource):
    def get(self, apikey):
        return geneweaverdb.get_geneset_by_user(apikey)


class GetProjectsByUser(restful.Resource):
    def get(self, apikey):
        return geneweaverdb.get_projects_by_user(apikey)


class GetProbesByGene(restful.Resource):
    def get(self, apikey, gene_ref_id):
        return geneweaverdb.get_probes_by_gene(apikey, gene_ref_id)


class GetPlatformById(restful.Resource):
    def get(self, apikey, platformid):
        return geneweaverdb.get_platform_by_id(apikey, platformid)


class GetSnpByGeneid(restful.Resource):
    def get(self, apikey, gene_ref_id):
        return geneweaverdb.get_snp_by_geneid(apikey, gene_ref_id)


class GetPublicationById(restful.Resource):
    def get(self, apikey, publicationid):
        return geneweaverdb.get_publication_by_id(apikey, publicationid)


class GetSpeciesByid(restful.Resource):
    def get(self, apikey, speciesid):
        return geneweaverdb.get_species_by_id(apikey, speciesid)


class GetResultsByUser(restful.Resource):
    def get(self, apikey):
        return geneweaverdb.get_results_by_user(apikey)


class GetGeneDatabaseById(restful.Resource):
    def get(self, apikey, gene_database_id):
        return geneweaverdb.get_gene_database_by_id(apikey, gene_database_id)


class GetResultByTaskId(restful.Resource):
    def get(self, apikey, taskid):
        return geneweaverdb.get_result_by_runhash(apikey, taskid)


class AddProjectByUser(restful.Resource):
    def get(self, apikey, project_name):
        return geneweaverdb.add_project_for_user(apikey, project_name)


class AddGenesetToProject(restful.Resource):
    def get(self, apikey, projectid, genesetid):
        return geneweaverdb.add_geneset_to_project(apikey, projectid, genesetid)


class DeleteGenesetFromProject(restful.Resource):
    def get(self, apikey, projectid, genesetid):
        return geneweaverdb.delete_geneset_from_project(apikey, projectid, genesetid)


class GetGenesetByProjectId(restful.Resource):
    def get(self, apikey, projectid):
        return geneweaverdb.get_geneset_by_project_id(apikey, projectid)


class GetOntologyByGensetId(restful.Resource):
    def get(self, apikey, gs_id):
        #user = geneweaverdb.get_user_id_by_apikey(apikey)
        #if (user == ''):
        #TODO ? - Do we want to throw error, or can anyone view ontology info?
        return geneweaverdb.get_all_ontologies_by_geneset(gs_id)

    def get(self, apikey, gs_id):
        #user = geneweaverdb.get_user_id_by_apikey(apikey)
        #if (user == ''):
        #TODO ? - Do we want to throw error, or can anyone view ontology info?
        return geneweaverdb.get_all_ontologies_by_geneset(gs_id)


# Tool Functions
class ToolGetFile(restful.Resource):
    def get(self, apikey, task_id, file_type):
        return geneweaverdb.get_file(apikey, task_id, file_type)


class ToolGetLink(restful.Resource):
    def get(self, apikey, task_id, file_type):
        return geneweaverdb.get_link(apikey, task_id, file_type)


class ToolGetStatus(restful.Resource):
    def get(self, task_id):
        return geneweaverdb.get_status(task_id)


# Tools
class ToolJaccardClustering(restful.Resource):
    def get(self, apikey, homology, method, genesets):
        return jaccardclusteringblueprint.run_tool_api(apikey, homology, method, genesets)


class ToolJaccardClusteringProjects(restful.Resource):
    def get(self, apikey, homology, method, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return jaccardclusteringblueprint.run_tool_api(apikey, homology, method, genesets)


class ToolGenesetViewer(restful.Resource):
    def get(self, apikey, homology, supressDisconnected, minDegree, genesets):
        return genesetviewerblueprint.run_tool_api(apikey, homology, supressDisconnected, minDegree, genesets)


class ToolGenesetViewerProjects(restful.Resource):
    def get(self, apikey, homology, supressDisconnected, minDegree, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return genesetviewerblueprint.run_tool_api(apikey, homology, supressDisconnected, minDegree, genesets)


class ToolJaccardSimilarity(restful.Resource):
    def get(self, apikey, homology, pairwiseDeletion, genesets):
        return jaccardsimilarityblueprint.run_tool_api(apikey, homology, pairwiseDeletion, genesets)


class ToolJaccardSimilarityProjects(restful.Resource):
    def get(self, apikey, homology, pairwiseDeletion, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return jaccardsimilarityblueprint.run_tool_api(apikey, homology, pairwiseDeletion, genesets)


class ToolTricliqueViewer(restful.Resource):
    def get(self, apikey, homology, pairwiseDeletion, genesets):
        return triclique_viewer_blueprint.run_tool_api(apikey, homology, pairwiseDeletion, genesets)


class ToolTricliqueViewerProjects(restful.Resource):
    def get(self, apikey, homology, pairwiseDeletion, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return triclique_viewer_blueprint.run_tool_api(apikey, homology, pairwiseDeletion, genesets)


class ToolCombine(restful.Resource):
    def get(self, apikey, homology, genesets):
        return combineblueprint.run_tool_api(apikey, homology, genesets)


class ToolCombineProjects(restful.Resource):
    def get(self, apikey, homology, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return combineblueprint.run_tool_api(apikey, homology, genesets)


class ToolPhenomeMap(restful.Resource):
    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap,
            minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, genesets):
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode,
                                                permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode,
                                                useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)


class ToolPhenomeMapProjects(restful.Resource):
    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap,
            minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode,
                                                permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode,
                                                useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)


class ToolBooleanAlgebra(restful.Resource):
    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap,
            minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode,
                                                permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode,
                                                useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)


class ToolBooleanAlgebra(restful.Resource):
    def get(self, apikey, relation, genesets):
        return booleanalgebrablueprint.run_tool_api(apikey, relation, genesets)


class ToolBooleanAlgebraProjects(restful.Resource):
    def get(self, apikey, relation, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return booleanalgebrablueprint.run_tool_api(apikey, relation, genesets)


class KeywordSearchGuest(restful.Resource):
    def get(self, apikey, search_term):
        return search.api_search(search_term)


api.add_resource(KeywordSearchGuest, '/api/get/search/bykeyword/<apikey>/<search_term>/')

api.add_resource(GetGenesetsByGeneRefId, '/api/get/geneset/bygeneid/<apikey>/<gene_ref_id>/<gdb_name>/')
api.add_resource(GetGenesetsByGeneRefIdHomology, '/api/get/geneset/bygeneid/<apikey>/<gene_ref_id>/<gdb_name>/homology')
api.add_resource(GetGenesetByUser, '/api/get/geneset/byuser/<apikey>/')
api.add_resource(GetOntologyByGensetId, '/api/get/ontologies/bygeneset/<apikey>/<gs_id>/')

api.add_resource(GetGenesetById, '/api/get/geneset/byid/<genesetid>/')
api.add_resource(GetGenesByGenesetId, '/api/get/genes/bygenesetid/<genesetid>/')

api.add_resource(GetGeneByGeneId, '/api/get/gene/bygeneid/<geneid>/')
api.add_resource(GetProjectsByUser, '/api/get/project/byuser/<apikey>/')
api.add_resource(GetGenesetByProjectId, '/api/get/geneset/byprojectid/<apikey>/<projectid>/')
api.add_resource(GetProbesByGene, '/api/get/probes/bygeneid/<apikey>/<gene_ref_id>/')
api.add_resource(GetPlatformById, '/api/get/platform/byid/<apikey>/<platformid>/')
api.add_resource(GetSnpByGeneid, '/api/get/snp/bygeneid/<apikey>/<gene_ref_id>/')
api.add_resource(GetPublicationById, '/api/get/publication/byid/<apikey>/<publicationid>/')
api.add_resource(GetSpeciesByid, '/api/get/species/byid/<apikey>/<speciesid>/')
api.add_resource(GetResultsByUser, '/api/get/results/byuser/<apikey>/')
api.add_resource(GetResultByTaskId, '/api/get/result/bytaskid/<apikey>/<taskid>/')
api.add_resource(GetGeneDatabaseById, '/api/get/genedatabase/byid/<apikey>/<gene_database_id>/')

#Not Gets
#Projects
api.add_resource(AddProjectByUser, '/api/add/project/byuser/<apikey>/<project_name>/')
api.add_resource(AddGenesetToProject, '/api/add/geneset/toproject/<apikey>/<projectid>/<genesetid>/')
api.add_resource(DeleteGenesetFromProject, '/api/delete/geneset/fromproject/<apikey>/<projectid>/<genesetid>/')

#Tool Functions
api.add_resource(ToolGetFile, '/api/tool/get/file/<apikey>/<task_id>/<file_type>/')
api.add_resource(ToolGetLink, '/api/tool/get/link/<apikey>/<task_id>/<file_type>/')
api.add_resource(ToolGetStatus, '/api/tool/get/status/<task_id>/')

#Tool Calls
api.add_resource(ToolGenesetViewer,
                 '/api/tool/genesetviewer/<apikey>/<homology>/<supressDisconnected>/<minDegree>/<genesets>/')
api.add_resource(ToolGenesetViewerProjects,
                 '/api/tool/genesetviewer/byprojects/<apikey>/<homology>/<supressDisconnected>/<minDegree>/<projects>/')

api.add_resource(ToolJaccardClustering, '/api/tool/jaccardclustering/<apikey>/<homology>/<method>/<genesets>/')
api.add_resource(ToolJaccardClusteringProjects,
                 '/api/tool/jaccardclustering/byprojects/<apikey>/<homology>/<method>/<projects>/')

api.add_resource(ToolJaccardSimilarity,
                 '/api/tool/jaccardsimilarity/<apikey>/<homology>/<pairwiseDeletion>/<genesets>/')
api.add_resource(ToolJaccardSimilarityProjects,
                 '/api/tool/jaccardsimilarity/byprojects/<apikey>/<homology>/<pairwiseDeletion>/<projects>/')

api.add_resource(ToolTricliqueViewer,
                 '/api/tool/tricliqueviewer/<apikey>/<homology>/<pairwiseDeletion>/<genesets>/')
api.add_resource(ToolTricliqueViewerProjects,
                 '/api/tool/tricliqueviewer/byprojects/<apikey>/<homology>/<pairwiseDeletion>/<projects>/')

api.add_resource(ToolCombine, '/api/tool/combine/<apikey>/<homology>/<genesets>/')
api.add_resource(ToolCombineProjects, '/api/tool/combine/byprojects/<apikey>/<homology>/<projects>/')

api.add_resource(ToolPhenomeMap,
                 '/api/tool/phenomemap/<apikey>/<homology>/<minGenes>/<permutationTimeLimit>/<maxInNode>/<permutations>/<disableBootstrap>/<minOverlap>/<nodeCutoff>/<geneIsNode>/<useFDR>/<hideUnEmphasized>/<p_Value>/<maxLevel>/<genesets>/')
api.add_resource(ToolPhenomeMapProjects,
                 '/api/tool/phenomemap/byprojects/<apikey>/<homology>/<minGenes>/<permutationTimeLimit>/<maxInNode>/<permutations>/<disableBootstrap>/<minOverlap>/<nodeCutoff>/<geneIsNode>/<useFDR>/<hideUnEmphasized>/<p_Value>/<maxLevel>/<projects>/')

api.add_resource(ToolBooleanAlgebra, '/api/tool/booleanalgebra/<apikey>/<relation>/<genesets>/')
api.add_resource(ToolBooleanAlgebraProjects, '/api/tool/booleanalgebra/byprojects/<apikey>/<relation>/<projects>/')

# ********************************************
# END API BLOCK
# ********************************************


if __name__ == '__main__':
    app.debug = True
    #app.run(host='10.3.4.114')
    app.run()
