import flask
from flask.ext.admin import Admin, BaseView, expose
from flask.ext.admin.base import MenuLink
from flask.ext import restful
from flask import request, send_file, Response, make_response, session
from decimal import Decimal
from sys import exc_info
from urlparse import parse_qs, urlparse
import config
import adminviews
import genesetblueprint
import geneweaverdb
import notifications
import curation_assignments
import pub_assignments
import error
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
import math
import cairosvg
import batch
from cStringIO import StringIO
from werkzeug.routing import BaseConverter


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

# *************************************

admin = Admin(app, name='GeneWeaver', index_view=adminviews.AdminHome(
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
    name='GeneSets', endpoint='viewGenesets', category='Gene Tools'))
admin.add_view(
    adminviews.Viewers(name='Genes', endpoint='viewGenes', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='GeneSet Info', endpoint='viewGenesetInfo', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='Gene Info', endpoint='viewGeneInfo', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='GeneSet Value', endpoint='viewGenesetVals', category='Gene Tools'))
admin.add_view(adminviews.Viewers(
    name='News', endpoint='viewNewsFeed', category='User Tools'))

admin.add_view(adminviews.Add(name='User', endpoint='newUser', category='Add'))
admin.add_view(
    adminviews.Add(name='Publication', endpoint='newPub', category='Add'))
admin.add_view(
    adminviews.Add(name='Group', endpoint='newGroup', category='Add'))
admin.add_view(
    adminviews.Add(name='Project', endpoint='newProject', category='Add'))
admin.add_view(
    adminviews.Add(name='GeneSet', endpoint='newGeneset', category='Add'))
admin.add_view(adminviews.Add(name='Gene', endpoint='newGene', category='Add'))
admin.add_view(
    adminviews.Add(name='GeneSet Info', endpoint='newGenesetInfo', category='Add'))
admin.add_view(
    adminviews.Add(name='Gene Info', endpoint='newGeneInfo', category='Add'))
admin.add_view(
    adminviews.Add(name='News Item', endpoint='newNewsItem', category='Add'))

admin.add_link(MenuLink(name='My Account', url='/accountsettings.html'))

class ListConverter(BaseConverter):
    """
    A class for handling a custom URL converter. Allows lists to be used as
    routing variables. Currently only used for viewing geneset overlap for >2
    genesets. 
    This should probably be put in a separate file.
    """

    def to_python(self, value):
        """
        Converts the value to a python list object. The separating character is
        a '+'.

        arguments
            value: a string serving as part of a URL variable

        returns
            a list of strings
        """
        
        return value.split('+')

    def to_url(self, values):
        """
        Converts a list of values to a string. The exact opposite of the
        to_python function. 

        arguments
            values: a list of values being converted 

        returns
            a string
        """

        return '+'.join(BaseConverter.to_url(value) for value in values)


## Add a custom URL converter to handle list variables
app.url_map.converters['list'] = ListConverter

# *************************************

RESULTS_PATH = '/var/www/html/dev-geneweaver/results/'

HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']
SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
                 'Canis familiaris']


@app.route('/results/<path:filename>')
def static_results(filename):
    # return flask.send_from_directory(RESULTS_PATH, filename)
    return flask.send_from_directory(config.get('application', 'results'),
                                     filename)


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
    return flask.redirect('/')


@app.route('/analyze')
def render_analyze():
    grp2proj = OrderedDict()
    active_tools = geneweaverdb.get_active_tools()

    if 'user' not in flask.g:
        return flask.render_template('analyze.html', active_tools=active_tools)

    for p in flask.g.user.shared_projects:
        p.group_id = p.group_id.split(',')
        ## If a project is found in multiple groups we just use the
        ## first group
        p.group_id = p.group_id[0]
        p.group = geneweaverdb.get_group_name(p.group_id)

        if p.group not in grp2proj:
            grp2proj[p.group] = [p]
        else:
            grp2proj[p.group].append(p)


        grp2proj = OrderedDict(sorted(grp2proj.items(), key=lambda d: d[0]))

    return flask.render_template(
        'analyze.html', 
        active_tools=active_tools,
        grp2proj=grp2proj
    )

@app.route('/analyzeshared')
def render_analyze_shared():
    if "user" in flask.g:
        grp2proj = OrderedDict()

        for p in flask.g.user.shared_projects:
            p.group_id = p.group_id.split(',')
            ## If a project is found in multiple groups we just use the
            ## first group
            p.group_id = p.group_id[0]
            p.group = geneweaverdb.get_group_name(p.group_id)

            if p.group not in grp2proj:
                grp2proj[p.group] = [p]
            else:
                grp2proj[p.group].append(p)


            grp2proj = OrderedDict(sorted(grp2proj.items(), key=lambda d: d[0]))
            #sorted(flask.g.user.shared_projects, key=lambda x: x.group_id)


    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('analyze_shared.html', active_tools=active_tools, grp2proj=grp2proj)


@app.route('/projects')
def render_projects():
    return flask.render_template('projects.html')


@app.route("/gwdb/get_group/<user_id>/")
def get_group(user_id):
    return geneweaverdb.get_all_member_groups(user_id)


@app.route("/gwdb/create_group/<group_name>/<group_private>/<user_id>/")
def create_group(group_name, group_private, user_id):
    results = geneweaverdb.create_group(group_name, group_private, user_id)
    return json.dumps(results)


@app.route("/gwdb/edit_group/<group_name>/<group_id>/<group_private>/<user_id>/")
def edit_group_name(group_name, group_id, group_private, user_id):
    results = geneweaverdb.edit_group_name(group_name, group_id, group_private, user_id)
    return json.dumps(results)


@app.route("/gwdb/add_user_group/<group_id>/<user_id>/<user_email>/")
def add_user_group(group_id, user_id, user_email):
    results = geneweaverdb.add_user_to_group(group_id, user_id, user_email)
    return json.dumps(results)


@app.route("/gwdb/remove_user_group/<group_name>/<user_id>/<user_email>/")
def remove_user_group(group_name, user_id, user_email):
    return geneweaverdb.remove_user_from_group(group_name, user_id, user_email)


@app.route("/gwdb/delete_group/<group_name>/<user_id>/")
def delete_group(group_name, user_id):
    results = geneweaverdb.delete_group(group_name, user_id)
    return json.dumps(results)


@app.route("/gwdb/remove_member/<group_name>/<user_id>/")
def remove_member(group_name, user_id):
    results = geneweaverdb.remove_member_from_group(group_name, user_id)
    return json.dumps(results)


# This function should be deprecated
@app.route('/share_projects.html')
def render_shareprojects():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('share_projects.html', active_tools=active_tools)


@app.route('/analyze_new_project/<string:pj_name>.html')
def render_analyze_new_project(pj_name):
    #print 'dbg analyze proj'
    args = flask.request.args
    active_tools = geneweaverdb.get_active_tools()
    user = geneweaverdb.get_user(flask.session.get('user_id'))
    geneweaverdb.create_project(pj_name, user.user_id)
    return flask.render_template('analyze.html', active_tools=active_tools)


@app.route('/curategeneset/edit/<int:gs_id>')
def render_curategeneset_edit(gs_id):
    return render_editgenesets(gs_id, True)


@app.route('/editgeneset/<int:gs_id>')
def render_editgenesets(gs_id, curation_view=False):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    species = geneweaverdb.get_all_species()
    pubs = geneweaverdb.get_all_publications(gs_id)
    onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id, "All Reference Types")
    ref_types = geneweaverdb.get_all_gso_ref_type()

    user_info = geneweaverdb.get_user(user_id)
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id or geneweaverdb.user_is_assigned_curation(user_id, gs_id) else None
    else:
        view = None

    if not (user_info.is_admin or user_info.is_curator):
        ref_types = ["Publication, NCBO Annotator",
                     "Description, NCBO Annotator",
                     "Publication, MI Annotator",
                     "Description, MI Annotator",
                     "GeneWeaver Primary Inferred",
                     "Manual Association", ]

    return flask.render_template(
        'editgenesets.html', 
        geneset=geneset, 
        user_id=user_id, 
        species=species, 
        pubs=pubs,
        view=view, 
        ref_types=ref_types, 
        onts=onts,
        curation_view=curation_view
    )


@app.route('/assign_genesets_to_curation_group.json', methods=['POST'])
def assign_genesets_to_curation_group():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        user_info = geneweaverdb.get_user(user_id)

        #TODO do we need to sanitize the note?
        note = request.form.get('note', '')
        grp_id = request.form.get('grp_id')

        gs_ids = request.form.getlist('gs_ids[]', type=int)

        status = {}
        for gs_id in gs_ids:
            geneset = geneweaverdb.get_geneset(gs_id, user_id)

            # allow a geneset owner or GW admin to assign the geneset for curation
            if geneset and (user_info.user_id == geneset.user_id or user_info.is_admin):
                curation_assignments.submit_geneset_for_curation(geneset.geneset_id, grp_id, note)
                status[gs_id] = {'success': True}
            else:
                status[gs_id] = {'success': False}

            response = flask.jsonify(results=status)

    else:
        #user is not logged in
        response = flask.jsonify(success=False, message='You do not have permissions to assign this GeneSet for curation')
        response.status_code = 403

    return response


@app.route('/assign_genesets_to_curator.json', methods=['POST'])
def assign_genesets_to_curator():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        user_info = geneweaverdb.get_user(user_id)

        #TODO do we need to sanitize the note?
        note = request.form.get('note', '')
        curator = request.form.get('usr_id')
        gs_ids = request.form.getlist('gs_ids[]', type=int)
        curator_info = geneweaverdb.get_user(curator)
        owned_groups = geneweaverdb.get_all_owned_groups(flask.session['user_id'])

        status = {}
        for gs_id in gs_ids:
            assignment = curation_assignments.get_geneset_curation_assignment(gs_id)
            if assignment:
                if assignment.group in [g['grp_id'] for g in owned_groups]:
                    curation_assignments.assign_geneset_curator(gs_id, curator, user_id, note)
                    status[gs_id] = {'success': True}
                else:
                    status[gs_id] = {'success': False,
                                     'message': "You are not an owner of the group and cannot assign a curator"}
            else:
                status[gs_id] = {'success': False,
                                 'message': "Error assigning curator, GeneSet " + str(gs_id) +
                                            "does not have an active curation record"}
            response = flask.jsonify(results=status)

    else:
        #user is not logged in
        response = flask.jsonify(success=False, message='You do not have permissions to assign these GeneSets to a curator')
        response.status_code = 403

    return response


@app.route("/assigncurator.json", methods=['POST'])
def assign_curator_to_geneset():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        #TODO do we need to sanitize the note?
        notes = request.form.get('note', '')
        gs_id = request.form.get('gs_id', type=int)
        curator = request.form.get('curator', type=int)

        assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

        if assignment:
            owned_groups = geneweaverdb.get_all_owned_groups(flask.session['user_id'])
            if assignment.group in [g['grp_id'] for g in owned_groups]:

                curator_info = geneweaverdb.get_user(curator)

                curation_assignments.assign_geneset_curator(gs_id, curator, user_id, notes)

                response = flask.jsonify(success=True, curator_name=curator_info.first_name + " " + curator_info.last_name, curator_email=curator_info.email)

        else:
            response = flask.jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
            response.status_code = 412

    else:
        #user is not logged in
        response = flask.jsonify(success=False, message='You do not have permissions to assign this GeneSet for curation')
        response.status_code = 403

    return response


@app.route("/geneset_ready_for_review.json", methods=['POST'])
def geneset_ready_for_review():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        #TODO do we need to sanitize the note?
        notes = request.form.get('note', '')
        gs_id = request.form.get('gs_id', type=int)

        assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

        if assignment:
            if user_id == assignment.curator:
                curation_assignments.submit_geneset_curation_for_review(gs_id, notes)
                response = flask.jsonify(success=True)
            else:
                response = flask.jsonify(success=False, message='You do not have permissions to perform this action.')
                response.status_code = 403
        else:
            response = flask.jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
            response.status_code = 412
    else:
        #user is not logged in
        response = flask.jsonify(success=False, message='You do not have permissions to perform this action.')
        response.status_code = 403

    return response


@app.route("/mark_geneset_reviewed.json", methods=['POST'])
def mark_geneset_reviewed():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        #TODO do we need to sanitize the note?
        notes = request.form.get('note', '')
        gs_id = request.form.get('gs_id', type=int)
        review_ok = request.form.get('review_ok') in ['true', '1']

        assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

        if assignment:
            if user_id == assignment.reviewer:
                if review_ok:
                    curation_assignments.geneset_curation_review_passed(gs_id, notes)
                else:
                    curation_assignments.geneset_curation_review_failed(gs_id, notes)
                response = flask.jsonify(success=True)
            else:
                response = flask.jsonify(success=False, message='You do not have permissions to perform this action.')
                response.status_code = 403
        else:
            response = flask.jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
            response.status_code = 412
    else:
        #user is not logged in
        response = flask.jsonify(success=False, message='You do not have permissions to perform this action.')
        response.status_code = 403

    return response


@app.route('/publication_assignment')
def render_assign_publication():
    my_groups = []

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)
    return flask.render_template('publication_assignment.html', myGroups=my_groups)


@app.route('/get_publication_by_pubmed_id/<pubmed_id>.json')
def get_publication_by_pubmed_id(pubmed_id):
    if 'user_id' in flask.session:

        publication = geneweaverdb.get_publication_by_pubmed(pubmed_id)

        if publication:
            response = flask.Response(json.dumps(publication.__dict__), 'application/json')
        else:
            response = flask.jsonify(message="Publication Not Found")
            response.status_code = 404

    else:
        #user is not logged in
        response = flask.jsonify(message='You do not have permissions to perform this action.')
        response.status_code = 403

    return response


@app.route('/assign_publication_to_group.json', methods=['POST'])
def assign_publication_to_group():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        notes = request.form.get('notes', '')
        pubmed_id = request.form.get('pubmed_id')
        group_id = request.form.get('group_id', type=int)

        if group_id not in geneweaverdb.get_user_groups(user_id):
            response = flask.jsonify(message="You do not have permissions to assign tasks to this group.")
            response.status_code = 403

        else:
            # lookup publication in database, if it doesn't exist in the db yet
            # this will add it
            publication = geneweaverdb.get_publication_by_pubmed(pubmed_id, create=True)

            if not publication:
                # didn't find matching publication in database or querying pubmed
                response = flask.jsonify(message="Publication Not Found")
                response.status_code = 404

            else:
                # publication exists
                publication_assignment = pub_assignments.get_publication_assignment(publication.pub_id, group_id)

                if publication_assignment and publication_assignment.state != publication_assignment.REVIEWED:
                    # is it already an active task for this group?
                    response = flask.jsonify(message="Publication is already assigned to this group.")
                    response.status_code = 412

                else:
                    # everything is good,  do the assignment
                    pub_assignments.queue_publication(publication.pub_id, group_id, notes)
                    response = flask.jsonify(message="Publication successfully assigned to group")

    else:
        # user is not logged in
        response = flask.jsonify(message='You do not have permissions to perform this action.')
        response.status_code = 403

    return response


@app.route('/updateGenesetOntologyDB')
def update_geneset_ontology_db():
    # ##########################################
    # Updates the geneset by calling a function
    #	to either add or remove an geneset-
    #	ontology link.
    # param: passed in by ajax data (ont_id,
    #		 gs_id, flag, gso_ref_type)
    # return: True
    # ##########################################

    ont_id = request.args['key']
    gs_id = request.args['gs_id']
    flag = request.args['flag']
    gso_ref_type = request.args['universe']

    if (flag == "true"):
        geneweaverdb.add_ont_to_geneset(gs_id, ont_id, gso_ref_type)
    else:
        geneweaverdb.remove_ont_from_geneset(gs_id, ont_id, gso_ref_type)

    return json.dumps(True)


def get_ontology_terms(gsid):
    """
    Retrieves ontology terms and metadata for a particular gs_id. For each term
    the function returns the term name, unique ID (from the ontology), and
    ontology name.

    :arg int:
    :ret:
    """

    gs_id = gsid
    gso_ref_type = 'All Reference Types'
    onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id, gso_ref_type)
    ontdb = geneweaverdb.get_all_ontologydb()
    ontdbdict = {}
    ontret = []

    ## Convert ontdb references to a dict so they're easier to lookup
    for ont in ontdb:
        ontdbdict[ont.ontologydb_id] = ont

    ## Format ontologies for display, only send the min. requirements
    for ont in onts:
        o = {'reference_id': ont.reference_id, 'name': ont.name,
             'dbname': ontdbdict[ont.ontdb_id].name }

        ontret.append(o)

    return ontret

@app.route('/initOntTree')
def init_ont_tree():
    parentdict = {}
    gs_id = request.args['gs_id']
    gso_ref_type = request.args['universe'] # Usually 'All Reference Types'
    onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id, gso_ref_type)

    for ont in onts:
        ## Path is a list of lists since there may be more than one
        ## root -> term path for a particular ontology term
        path = geneweaverdb.get_all_parents_to_root_for_ontology(ont.ontology_id)
        parentdict[ont.ontology_id] = path

    tree = {}
    ontcache = {}

    for ontid, paths in parentdict.items():
        for path in paths:
            ontpath = []

            for p in path:
                if p not in ontcache:
                    p = geneweaverdb.get_ontology_by_id(p)
                    ontcache[p.ontology_id] = p

                else:
                    p = ontcache[p]

                node = create_new_child_dict(p, gso_ref_type)

                ontpath.append(node)

            ## Add things in reverse order because it makes things easier
            #for p in ontpath[::-1]:
            for i in range(len(ontpath), 0, -1):
                i -= 1

                ## Last term in the path is the most granular child and
                ## shouldn't expand or be a folder
                if i == (len(ontpath) - 1):
                    ontpath[i]['isFolder'] = False
                    ontpath[i]['select'] = True
                    ontpath[i]['expand'] = False

                else:
                    ontpath[i]['expand'] = True

                if i == 0:
                    break

            tree = mergeTreePath(tree, ontpath)

    tree = convertTree(tree)

    return json.dumps(tree)

def doesChildExist(child, children):
    """
    Given a list of children, checks to see if a child node already exists
    in the given list. Used to prevent duplicates from cropping up in the
    ontology tree.
    """

    children = map(lambda c: c['key'], children)

    return child['key'] in children

def _convertTree(parent, child):
    """
    The recursive component to convertTree(). Recursively adds child nodes to
    each parent's list of children. Also checks to see if those children
    already exist in the list; if they do exist, they aren't added.

    :arg dict: parent node
    :arg dict: child node
    :ret dict: parent node with newly added children
    """

    ## This means it's a leaf node as its only key should be 'node'
    if len(child.keys()) <= 1:
        if not doesChildExist(child['node'], parent['node']['children']):
            parent['node']['children'].append(child['node'])

        return parent

    for ck in child.keys():

        if ck == 'node':
            continue

        child = _convertTree(child, child[ck])

        if not doesChildExist(child['node'], parent['node']['children']):
            parent['node']['children'].append(child['node'])

    return parent

def convertTree(root):
    """
    Converts a tree structure generated by mergeTreePath into the array of
    nested dicts that can be used by DynaTree on the client side of things.

    :arg dict: the top level (root) node of the tree structure
    :ret dict: formatted tree (see create_new_child_dict() for relevant fields)
    """

    subtrees = []

    for k in root:
        if k == 'node':
            continue

        subroot = root[k]

        for child in list(subroot.keys()):
            if child == 'node':
                continue

            subroot = _convertTree(subroot, subroot[child])

        subtrees.append(subroot['node'])

    return subtrees

def mergeTreePath(tree, path):
    """
    Given a tree and list of ontology nodes, adds the node list to the tree.
    Uses ont_ids as keys. This is used to merge sections of the ontology
    tree that may overlap. The list of nodes should be in order i.e. from
    root -> leaf. In the returned tree, every element except the 'node' key
    is a child of the previous node.

    :arg dict: tree structure to add the node path to
    :arg list: list of ontology nodes
    :ret dict: tree with newly added nodes
    """

    if not path:
        return tree

    t = tree

    for node in path:
        key = node['key']

        if not t.get(key, None):
            t[key] = {}

        t = t[key]
        t['node'] = node

    return tree

def create_new_child_dict(ontology_node, grt):
    new_child_dict = dict()
    new_child_dict["title"] = ontology_node.name
    new_child_dict["isLazy"] = True
    new_child_dict["key"] = ontology_node.ontology_id
    new_child_dict["db"] = False
    new_child_dict["children"] = []
    #new_child_dict["children"] = set()
    if grt == "All Reference Types":
        new_child_dict["unselectable"] = True
    if ontology_node.children == 0:
        new_child_dict["isFolder"] = False
    else:
        new_child_dict["isFolder"] = True
    return new_child_dict


def create_new_expanded_child_dict(ontology_node, parents, end_node, grt):
    new_child_dict = dict()
    new_child_dict["title"] = ontology_node.name
    new_child_dict["isLazy"] = True
    new_child_dict["key"] = ontology_node.ontology_id
    new_child_dict["db"] = False
    if grt == "All Reference Types":
        new_child_dict["unselectable"] = True
    if ontology_node.children == 0:
        new_child_dict["isFolder"] = False
    else:
        new_child_dict["isFolder"] = True
    if ontology_node.ontology_id in parents:
        if ontology_node.ontology_id == end_node:
            new_child_dict["select"] = True
            return new_child_dict
        else:
            new_child_dict["expand"] = True
            new_child_dict["children"] = []
            ontology_node_children = geneweaverdb.get_all_children_for_ontology((ontology_node.ontology_id))
            for child in ontology_node_children:
                if child.ontology_id in parents:
                    new_child_dict["children"].append(create_new_expanded_child_dict(child, parents, end_node, grt))
                else:
                    new_child_dict["children"].append(create_new_child_dict(child, grt))
    return new_child_dict


@app.route('/expandOntNode', methods=['POST', 'GET'])
def get_ont_root_nodes():
    if (request.args['is_db'] == "true"):
        result = geneweaverdb.get_all_root_ontology_for_database(request.args['key'])
    else:
        result = geneweaverdb.get_all_children_for_ontology(request.args['key'])
    gso_ref_type = request.args['universe']

    info = []
    for i in range(0, len(result)):
        data = dict()
        data["title"] = result[i].name
        if gso_ref_type == "All Reference Types":
            data["unselectable"] = True
        if (result[i].children == 0):
            data["isFolder"] = False
        else:
            data["isFolder"] = True
        data["isLazy"] = True
        data["key"] = result[i].ontology_id
        data["db"] = False
        info.append(data)
    return (json.dumps(info))


@app.route('/updategeneset', methods=['POST'])
def update_geneset():
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        result = geneweaverdb.updategeneset(user_id, flask.request.form)
        data = dict()
        data.update({"success": result})
        data.update({'usr_id': user_id})
        return json.dumps(data)

@app.route('/curategenesetgenes/<int:gs_id>')
def render_curategenesetgenes(gs_id):
    return render_editgeneset_genes(gs_id, curation_view=True)

@app.route('/editgenesetgenes/<int:gs_id>')
def render_editgeneset_genes(gs_id, curation_view=False):
    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0
    user_info = geneweaverdb.get_user(user_id)
    uploadfiles.create_temp_geneset_from_value(gs_id)
    meta = uploadfiles.get_temp_geneset_gsid(gs_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id, temp='temp')
    platform = geneweaverdb.get_microarray_types()
    idTypes = geneweaverdb.get_gene_id_types()

    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
        if view is None and curation_view and geneweaverdb.user_is_assigned_curation(user_id, gs_id):
            view = 'True'

    else:
        view = None

    if not geneset:
        return flask.render_template('editgenesetsgenes.html', geneset=geneset,
                                     user_id=user_id)

    if geneset.status == 'deleted':
        return flask.render_template('editgenesetsgenes.html', geneset=geneset,
                                     user_id=user_id)

    ####################################
    # Build dictionary of all possible
    # menus options
    gidts = {}
    pidts = {}
    for id in idTypes:
        gidts[id['gdb_id']] = id['gdb_shortname']

    for p in platform:
        pidts[p['pf_id']] = p['pf_name']

    ## Ontologies associated with this geneset
    ontology = get_ontology_terms(gs_id)

    species = []
    ## Species list for dynamically generated species tags
    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    contents = geneweaverdb.get_file_contents(geneset.file_id)

    if contents:
        ## Transform into a gene list
        contents = contents.split('\n')
        contents = map(lambda s: s.split('\t'), contents)
        contents = map(lambda t: t[0], contents)
        symbol2ode = batch.db.getOdeGeneIds(geneset.sp_id, contents)
        #keys = [list(query) for query in symbol2ode.keys()]
        #symbol2ode = dict([(k[0], symbol2ode[tuple(k)][0]) for k in keys])
        ## Reverse to make our lives easier during templating
        for sym, ode in symbol2ode.items():
            symbol2ode[ode] = sym

    else:
        symbol2ode = None

    return flask.render_template(
        'editgenesetsgenes.html', 
        geneset=geneset, 
        user_id=user_id, 
        species=species,
        gidts=gidts, 
        pidts=pidts, 
        view=view, 
        meta=meta, 
        ontology=ontology,
        id_map=symbol2ode,
        curation_view=curation_view
    )


@app.route('/removegenesetsfromproject/<gs_id>')
def render_remove_genesets(gs_id):
    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0
    gs_and_proj = None
    if user_id is not 0:
        gs_and_proj = geneweaverdb.get_selected_genesets_by_projects(gs_id)
    return flask.render_template('removegenesets.html', user_id=user_id, gs_and_proj=gs_and_proj)


@app.route('/setthreshold/<int:gs_id>')
def render_set_threshold(gs_id):
    d3BarChart = []
    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0
    user_info = geneweaverdb.get_user(user_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None

        if view is None and geneweaverdb.user_is_assigned_curation(user_id, gs_id):
            view = 'curator'
    else:
        view = None
    # Determine if this is bi-modal, we won't display these
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


@app.route('/updateProjectGroups', methods=['GET'])
def update_project_groups():
    if 'user_id' in flask.session:
        user_id = request.args['user_id']
        proj_id = request.args['proj_id']

        if json.loads(request.args['groups']) != '':
            groups = (json.loads(request.args['groups'])) 
        else: 
            groups = '-1'

        if geneweaverdb.get_user(user_id).is_admin != 'False' or\
           geneweaverdb.user_is_project_owner(user_id, proj_id):
            results = geneweaverdb.update_project_groups(proj_id, groups, user_id)
            return json.dumps(results)


@app.route('/updateStaredProject', methods=['GET'])
def update_star_project():
    if int(flask.session['user_id']) == int(request.args['user_id']):
        proj_id = request.args['proj_id']
        user_id = request.args['user_id']
        if geneweaverdb.get_user(user_id).is_admin != 'False' or geneweaverdb.user_is_project_owner(user_id, proj_id):
            results = geneweaverdb.update_stared_project(proj_id, user_id)
            return json.dumps(results)


@app.route('/removeUsersFromGroup', methods=['GET'])
def remove_users_from_group():
    if 'user_id' in flask.session:
        user_id = request.args['user_id']
        user_emails = request.args['user_emails']
        grp_id = request.args['grp_id']
        results = geneweaverdb.remove_selected_users_from_group(user_id, user_emails, grp_id)
        return json.dumps(results)

@app.route('/updateGroupAdmins', methods=['GET'])
def update_group_admins():
    if 'user_id' in flask.session and flask.session['user_id'] == int(request.args['user_id']):
        user_id = request.args['user_id']
        users = [int(u) for u in request.args.getlist('uids')]
        grp_id = request.args['grp_id']

        results = geneweaverdb.update_group_admins(user_id, users, grp_id)
        return json.dumps(results)
    else:
        return json.dumps({'error': 'You do not have permission to modify this group'})


@app.route('/deleteProjectByID', methods=['GET'])
def delete_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.delete_project_by_id(flask.request.args['projids'])
        return json.dumps(results)


@app.route('/addProjectByName', methods=['GET'])
def add_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.add_project_by_name(flask.request.args['name'], flask.request.args['comment'])
        return json.dumps(results)
    else:
        return json.dumps({"error": "You do not have permission to add a Project"})


@app.route('/get_project_groups_by_user_id')
def get_project_groups_by_user_id():
    if 'user_id' in flask.session:
        results = geneweaverdb.get_project_groups()
        return json.dumps(results)
    else:
        return json.dumps({"error": "An error occurred while retrieving groups"})


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
    groupsEmail = geneweaverdb.get_all_members_of_group(flask.session.get('user_id'))

    groupAdmins = {}
    for group in groupsOwnerOf:
        groupAdmins[group['grp_id']] = geneweaverdb.get_group_admins(group['grp_id'])

    prefs = json.loads(user.prefs)
    email_pref = prefs.get('email_notification', 0)


    return flask.render_template('accountsettings.html', user=user, groupsMemberOf=groupsMemberOf,
                                 groupsOwnerOf=groupsOwnerOf, groupsEmail=groupsEmail,
                                 groupAdmins=groupAdmins, emailNotifications=email_pref)


@app.route('/update_notification_pref.json', methods=['GET'])
def update_notification_pref():
    user_id = int(flask.request.args['user_id'])
    if 'user_id' in flask.session and user_id == flask.session.get('user_id'):
        state = int(flask.request.args['new_state'])
        result = geneweaverdb.update_notification_pref(user_id, state)
        response = flask.jsonify(**result)
        if 'error' in result:
            response.status_code = 500
    else:
        response = flask.jsonify(error='Unable to set email notification preference: permission error')
        response.status_code = 403

    return response


@app.route('/login')
def render_login():
    return flask.render_template('login.html')


@app.route('/login_error')
def render_login_error():
    return flask.render_template('login.html', error="Invalid Credentials")


@app.route('/resetpassword.html')
def render_forgotpass():
    return flask.render_template('resetpassword.html')

@app.route('/downloadResult', methods=['POST'])
def download_result():
    """
    Used when a user requests to download a hi-res result image. The SVG data
    is posted to the server, upscaled, converted to a PNG, and sent back to the
    user.

    :ret str: base64 encoded image
    """

    form = flask.request.form
    svg = form['svg'].strip()
    filetype = form['filetype'].lower().strip()
    svgout = StringIO()
    imgout = StringIO()
    resultpath = config.get('application', 'results')
    dpi = 600

    if 'oldver' in form:
        with open(os.path.join(resultpath, oldver), 'r') as fl:
            svg = fl.read()

        dpi = 300

    ## This is incredibly stupid, but must be done. cairosvg (for some
    ## awful, unknown reason) will not scale any SVG produced by d3. So
    ## we convert our d3js produced SVG to an SVG...then convert to PNG
    ## with a reasonably high DPI.
    ## Also, if any fonts are rendering incorrectly, it's because cairosvg
    ## doesn't parse CSS attributes correctly and you need to append each
    ## font attribute to the text element itself.
    cairosvg.svg2svg(bytestring=svg, write_to=svgout)

    if filetype == 'pdf':
        cairosvg.svg2pdf(bytestring=svgout.getvalue(), write_to=imgout, dpi=dpi)

    elif filetype == 'png':
        cairosvg.svg2png(bytestring=svgout.getvalue(), write_to=imgout, dpi=dpi)

    else:
        imgout = svgout

    return imgout.getvalue().encode('base64')

@app.route('/viewStoredResults', methods=['GET'])
def viewStoredResults_by_runhash():
    """
    Called by an AJAX request from /results when the user wants to view a saved
    tool result. Client side code ensures the result already exists on the
    server. This function retrieves the proper result URL and sends it back to
    the client for redirection.

    arguments (as part of the GET request)
        runHash: the unique run hash string for this tool run
        usr_id: int ID of the user who wishes to view the result

    returns
        a relative URL for the stored tool result
    """

    ## Should probably do some kind of usr_id check
    runhash = request.args.get('runHash', type=str)
    usr_id = request.args.get('usr_id', type=str)
    results = geneweaverdb.get_results_by_runhash(runhash)

    if results['res_tool'] == 'Jaccard Similarity':
        return flask.url_for(
            jaccardsimilarityblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'HiSim Graph':
        return flask.url_for(
            phenomemapblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'GeneSet Graph':
        return flask.url_for(
            genesetviewerblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'Clustering':
        return flask.url_for(
            jaccardclusteringblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'Boolean Algebra':
        return flask.url_for(
            booleanalgebrablueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    else:
        ## Something bad has happened
        return ''

@app.route('/reruntool.json', methods=['POST', 'GET'])
def rerun_tool():
    args = flask.request.args
    user_id = args['user_id']
    results = geneweaverdb.get_results_by_runhash(args['runHash'])
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
    return render_viewgeneset_main(gs_id)


@app.route('/curategeneset/<int:gs_id>', methods=['GET', 'POST'])
def render_curategeneset(gs_id):
    if 'user_id' in flask.session:
        assignment = curation_assignments.get_geneset_curation_assignment(gs_id)
        curation_view = None
        curation_team_members = None
        curator_info = None

        def user_is_curation_leader():
            owned_groups = geneweaverdb.get_all_owned_groups(flask.session['user_id'])
            if assignment.group in [x['grp_id'] for x in owned_groups]:
                return True

        if assignment:

            #figure out the proper view depending on the state and your role(s)
            if assignment.state == curation_assignments.CurationAssignment.UNASSIGNED and user_is_curation_leader():
                curation_view = 'curation_leader'
            elif assignment.state == curation_assignments.CurationAssignment.ASSIGNED:
                if flask.session['user_id'] == assignment.curator:
                    curation_view = 'curator'
                elif user_is_curation_leader():
                    curation_view = 'curation_leader'
            elif (assignment.state == curation_assignments.CurationAssignment.READY_FOR_TEAM_REVIEW or
                          assignment.state == curation_assignments.CurationAssignment.REVIEWED):
                if flask.session['user_id'] == assignment.reviewer:
                    curation_view = 'reviewer'
                elif flask.session['user_id'] == assignment.curator:
                    curation_view = 'curator'

            if curation_view:
                if assignment.curator:
                    curator_info = geneweaverdb.get_user(assignment.curator)

                if curation_view == 'curation_leader' or curation_view == 'reviewer':
                    # curation_leader view needs a list of users that belong to
                    # the group so it can render the assignment dialog
                    curation_team_members = [geneweaverdb.get_user(uid) for uid in geneweaverdb.get_group_users(assignment.group)]

                return render_viewgeneset_main(gs_id, curation_view, curation_team_members, assignment, curator_info)

    # not assigned curation task,  just render the normal viewgeneset page
    # if user is admin or GW curator, they will be able to view/edit this
    # otherwise user will get whatever viewing status they should have

    #TODO this should go to some permission error page
    return render_viewgeneset_main(gs_id, False)


def render_viewgeneset_main(gs_id, curation_view=None, curation_team=None, curation_assignment=None, curator_info=None):
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


    genetypes = geneweaverdb.get_gene_id_types()
    genedict = {}

    for gtype in genetypes:
        genedict[gtype['gdb_id']] = gtype['gdb_name']

    # get value for the alt-gene-id column
    if 'extsrc' in session:
        if genedict.get(session['extsrc'], None):
            altGeneSymbol = genedict[session['extsrc']]
            alt_gdb_id = session['extsrc']

        else:
            altGeneSymbol = 'Entrez'
            alt_gdb_id = 1
    else:
        altGeneSymbol = 'Entrez'
        alt_gdb_id = 1

    emphgenes = {}
    emphgeneids = []

    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0

    user_info = geneweaverdb.get_user(user_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id)

    ## User account
    if user_info:
        if not user_info.is_admin and not user_info.is_curator:
            ## get_geneset takes into account permissions, if a geneset is
            ## returned by *_no_user then we know they can't view it b/c of 
            ## access rights
            if not geneset and geneweaverdb.get_geneset_no_user(gs_id):
                return flask.render_template(
                    'viewgenesetdetails.html',
                    no_access=True,
                    user_id=user_id
                )

    ## Guest account attempting to view geneset without proper access
    if not geneset:
        return flask.render_template(
            'viewgenesetdetails.html',
            no_access=True,
            user_id=user_id
        )

    ## Nothing is ever deleted but that doesn't mean users should be able
    ## to see them. Some sets have a NULL status so that MUST be
    ## checked for, otherwise sad times ahead :(
    if not geneset or (geneset and geneset.status == 'deleted'):
        return flask.render_template(
            'viewgenesetdetails.html', 
            geneset=None,
            deleted=True,
            user_id=user_id
        )

    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))

    ## Ontologies associated with this geneset
    ontology = get_ontology_terms(gs_id)

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    return flask.render_template('viewgenesetdetails.html', geneset=geneset,
                                 emphgeneids=emphgeneids, user_id=user_id,
                                 colors=HOMOLOGY_BOX_COLORS, tt=SPECIES_NAMES,
                                 altGeneSymbol=altGeneSymbol, view=view,
                                 ontology=ontology, alt_gdb_id=alt_gdb_id,
                                 species=species, curation_view=curation_view,
                                 curation_team=curation_team,
                                 curation_assignment=curation_assignment,
                                 curator_info=curator_info)


@app.route('/viewgenesetoverlap/<list:gs_ids>', methods=['GET'])
def render_viewgenesetoverlap(gs_ids):
    """
    Renders the view geneset overlap page.

    arguments
        gs_ids: a list of gs_ids contained in the GET request
    """

    emphgenes = {}
    emphgeneids = []

    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0

    genesets = []

    ## The same geneset provided for all arguments
    if len(list(set(gs_ids))) == 1:

        return flask.render_template(
            'viewgenesetoverlap.html', 
            same_geneset=True
        )

    for gs_id in gs_ids:
        gs = geneweaverdb.get_geneset(gs_id, user_id)

        if gs:
            genesets.append(gs)

    # Get the current user id
    user_info = geneweaverdb.get_user(user_id)

    ## Mapping of gs_id pairs to the genes found in their overlap
    gs_intersects = defaultdict(lambda: defaultdict(list))
    ## Mapping of genes to the list of genesets they're found in
    gene_intersects = defaultdict(set)
    ## Maps gs_ids to geneset data
    gs_map = {}

    for gs in genesets:
        gs_map[gs.geneset_id] = gs

    for gs1 in genesets:
        gs_id1 = gs1.geneset_id

        for gs2 in genesets:
            gs_id2 = gs2.geneset_id

            if gs_id1 == gs_id2:
                continue

            ## No reason to perform unnecessary calculations
            if gs_intersects[gs_id1][gs_id2] or gs_intersects[gs_id2][gs_id1]:
                continue

            ## get_intersect* returns a tuple with a list of gene symbols and
            ## a list of homology ids
            intersect = geneweaverdb.get_intersect_by_homology(gs_id1, gs_id2)

            gs_intersects[gs_id1][gs_id2] = intersect
            gs_intersects[gs_id2][gs_id1] = intersect

            ## Keep track of gene-genesets for sorting and ease of display
            for gene in intersect[0]:
                gene_intersects[gene].add(gs_id1)
                gene_intersects[gene].add(gs_id2)

    intersects = []

    ## Generate a single structure containing all the intersection information
    ## for the template
    for gene, gs_ids in gene_intersects.items():
        ## If the intersection is among >1 species, it's a homologous gene
        ## cluster
        species = list(set(map(lambda i: gs_map[i].sp_id, gs_ids)))

        sect_struct = {
            'gene': gene,
            'gs_ids': gs_ids,
            'intersect_count': len(gs_ids),
            'is_homolog': True if len(species) > 1 else False
        }

        intersects.append(sect_struct)

    ## Sort by the # of genes in the intersection
    intersects = sorted(intersects, key=lambda i: i['intersect_count'],
            reverse=True)

    if user_id != 0:
        if user_info.is_admin or\
           user_info.is_curator:
            view = 'True' 

        else:
            view = None
    else:
        view = None

    def venn_circles(i,ii,j, size=100):
        """
        Taken from the jaccard sim. tool source code. Calculates x, y positions
        for each circle in the venn diagram so the proper overlap area is
        shown.

        arguments
            i: size of the left side geneset
            ii: size of the right side geneset
            j: size of the intersection
            size: visualization scale

        returns
            a dictionary with x, y positions and radius sizes for both circles
        """
        pi = math.acos(-1.0)
        r1 = math.sqrt(i/pi)
        r2 = math.sqrt(ii/pi)
        if r1==0:
            r1=1.0
        if r2==0:
            r2=1.0
        scale=size/2.0/(r1+r2)

        if i==j or ii==j:  # complete overlap
            c1x=c1y=c2x=c2y=size/2.0
        elif j==0:  # no overlap
            c1x=c1y=r1*scale
            c2x=c2y=size-(r2*scale)
        else:
            # originally written by zuopan, rewritten a number of times
            step = .001
            beta = pi
            if r1<r2:
                r2_=r1
                r1_=r2
            else:
                r1_=r1
                r2_=r2
            r2o1=r2_/r1_
            r1_2=r1_*r1_
            r2_2=r2_*r2_

            while beta > 0:
                beta -= step
                alpha = math.asin(math.sin(beta)/r1_ * r2_)
                Sj = r1_2*alpha + r2_2*(pi-beta) - 0.5*(r1_2*math.sin(2*alpha) + r2_2*math.sin(2*beta));
                if Sj > j:
                    break

            oq= r1_*math.cos(alpha) - r2_*math.cos(beta)
            oq=(oq*scale)/2.0

            c1x=(size/2.0) - oq
            c2x=(size/2.) + oq
            c1y=c2y=size/2.0

        vsize = 100
        if r1 > r2:
            r = r1
        else:
            r = r2

        tx = (vsize/2)*(4.0/3.0)
        ty = (vsize/2 - (r) -5)*(4.0/3.0)
        r1=r1*scale
        r2=r2*scale

        return {'c1x':c1x,'c1y':c1y,'r1':r1, 'c2x':c2x,'c2y':c2y,'r2':r2, 'tx': tx, 'ty': ty}


    ## TODO: fix emphasis genes
    #emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)

    #for row in emphgenes:
    #    emphgeneids.append(str(row['ode_gene_id']))

    ## variables to hole if a geneset has an emphasis gene
    #inGeneset1 = False
    #inGeneset2 = False

    ## Check to see if an emphasis gene is in one of the genesets
    #for gene in emphgeneids:
    #    inGeneset1 = geneweaverdb.check_emphasis(gs_id, gene)
    #    if inGeneset1 == True:
    #        break

    #for gene in emphgeneids:
    #    inGeneset2 = geneweaverdb.check_emphasis(gs_id1, gene)
    #    if inGeneset2 == True:
    #        break

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    ## Pairwise comparison so we provide additional data for the venn diagram
    if len(genesets) == 2:
        venn = venn_circles(genesets[0].count, genesets[1].count, len(intersects), 300)
        venn_text = {'tx': venn['tx'], 'ty': venn['ty']}
        venn = [{'cx': venn['c1x'], 'cy': venn['c1y'], 'r': venn['r1']}, 
                {'cx': venn['c2x'], 'cy': venn['c2y'], 'r': venn['r2']}];

        left_count = genesets[0].count - len(intersects)
        right_count = genesets[1].count - len(intersects)

        venn_text['text'] = '(%s (%s) %s)' % (left_count, len(intersects), right_count)

    else:
        venn = None
        venn_text = None

    #emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)

    return flask.render_template('viewgenesetoverlap.html', 
        gs_map=gs_map,
        intersects=intersects,
        species=species,
        venn=venn,
        venn_text=venn_text,
        #emphgenes=emphgenes
    )


# function to draw the venn diagrams for the overlap page
def createVennDiagram(i, ii, j, size=100):
    pi = math.acos(-1.0)
    r1 = math.sqrt(i / pi)
    r2 = math.sqrt(ii / pi)
    if r1 == 0:
        r1 = 1.0
    if r2 == 0:
        r2 = 1.0
    scale = size / 2.0 / (r1 + r2)

    if i == j or ii == j:  # complete overlap
        c1x = c1y = c2x = c2y = size / 2.0
    elif j == 0:  # no overlap
        c1x = c1y = r1 * scale
        c2x = c2y = size - (r2 * scale)
    else:
        # originally written by zuopan, rewritten a number of times
        step = .001
        beta = pi
        if r1 < r2:
            r2_ = r1
            r1_ = r2
        else:
            r1_ = r1
            r2_ = r2
        r2o1 = r2_ / r1_
        r1_2 = r1_ * r1_
        r2_2 = r2_ * r2_

        while beta > 0:
            beta -= step
            alpha = math.asin(math.sin(beta) / r1_ * r2_)
            Sj = r1_2 * alpha + r2_2 * (pi - beta) - 0.5 * (r1_2 * math.sin(2 * alpha) + r2_2 * math.sin(2 * beta));
            if Sj > j:
                break

        oq = r1_ * math.cos(alpha) - r2_ * math.cos(beta)
        oq = (oq * scale) / 2.0

        c1x = (size / 2.0) - oq
        c2x = (size / 2.) + oq
        c1y = c2y = size / 2.0

    r1 = r1 * scale
    r2 = r2 * scale

    data = {}
    data['circledata'] = {'c1x': c1x, 'c1y': c1y, 'r1': r1, 'c2x': c2x, 'c2y': c2y, 'r2': r2}

    return json.dumps(data)

@app.route('/mygenesets')
def render_user_genesets():
    table = 'production.geneset'
    my_groups = []
    other_groups = []
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

        my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)
        my_groups.sort(key=lambda k: k['grp_name'])

        other_groups = geneweaverdb.get_other_visible_groups(user_id)
        other_groups.sort(key=lambda k: k['grp_name'])

    else:
        headerCols, user_id, columns = None, 0, None

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    return flask.render_template(
        'mygenesets.html',
        headerCols=headerCols,
        user_id=user_id,
        columns=columns,
        table=table,
        species=species,
        myGroups=my_groups,
        otherGroups=other_groups
    )

@app.route('/groupTasks/', defaults={'group_id': None})
@app.route('/groupTasks/<int:group_id>')
def render_group_tasks(group_id):
    group = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
        columns = [
            {'name': 'full_name'},
            {'name': 'task_id'},
            {'name': 'task_type'},
            {'name': 'assignment_date'},
            {'name': 'task_status'},
            {'name': 'reviewer'}
        ]
        headerCols = ["Assignee Name",
                      "Task",
                      "Task Type",
                      "Assign Date",
                      "Status",
                      "Reviewer"]

        groups_member = geneweaverdb.get_all_member_groups(user_id)
        groups_owner  = geneweaverdb.get_all_owned_groups(user_id)

        if group_id:
            group = geneweaverdb.get_group_by_id(group_id)

        group_curators = geneweaverdb.get_group_members(group_id)
        print(group_curators)

        group_owner = False
        try:
            if group_id_in_groups(group.grp_id, groups_owner):
                group_owner = True
        except TypeError as error:
            print("TypeError while trying to match group id: {0}".format(error))
    else:
        headerCols, user_id, columns = None, 0, None

    return flask.render_template(
        'groupTasks.html',
        headerCols=headerCols, 
        user_id=user_id, 
        columns=columns,
        group=group,
        group_owner=group_owner,
        groupCurators=group_curators,
        groups_member=groups_member,
        groups_owner=groups_owner
    )

def group_id_in_groups(id, groups):
    if type(id) != int:
        raise TypeError("id must be an integer")
    included = False
    for group in groups:
        if not group.has_key('grp_id'):
            raise TypeError("geneweaverdb.Groups instance has no grp_id value.  Possibly invalid type...")
        if group['grp_id'] == id:
            included = True
    return included

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


@app.route('/viewSimilarGenesets/<int:gs_id>/<int:grp_by>')
def render_sim_genesets(gs_id, grp_by):
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0
    # Get GeneSet Info for the MetaData
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    # Returns a subClass of geneset that includes jac values
    simgs = geneweaverdb.get_similar_genesets(gs_id, user_id, grp_by)
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
        d3BarChart.append({'x': i, 'y': float(k.jac_value), 'gsid': int(k.geneset_id), 'abr': k.abbreviation.encode('utf-8')})
        i += 1
    d3Data.extend([tier1, tier2, tier3, tier4, tier5])
    json.dumps(d3Data, default=decimal_default)
    json.dumps(d3BarChart, default=decimal_default)

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    return flask.render_template(
        'similargenesets.html', 
        geneset=geneset, 
        user_id=user_id, 
        gs_id=gs_id, 
        simgs=simgs,
        d3Data=d3Data, 
        max=max, 
        d3BarChart=d3BarChart,
        species=species
    )


@app.route('/getPubmed', methods=['GET', 'POST'])
def get_pubmed_data():
    """
    """

    from pubmedsvc import get_pubmed_info

    pubmedValues = []

    if flask.request.method == 'GET':
        args = flask.request.args

        if 'pmid' in args:
            pmid = args['pmid']

            pub = get_pubmed_info(pmid)

            if not pub:
                return json.dumps({})

            pubmedValues.extend((pub['pub_title'], pub['pub_authors'], 
                                 pub['pub_journal'],
                                 pub['pub_volume'], pub['pub_pages'],
                                 pub['pub_year'], pub['pub_month'], pub['pub_abstract']))

    return json.dumps(pubmedValues)


# @app.route('/getPubmed', methods=['GET', 'POST'])
# def get_pubmed_data():
#     pubmedValues = []
#     http = urllib3.PoolManager()
#     if flask.request.method == 'GET':
#         args = flask.request.args
#         if 'pmid' in args:
#             pmid = args['pmid']
#             PM_DATA = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=%s&retmode=xml'
#             # response = http.urlopen('GET', PM_DATA % (','.join([str(x) for x in pmid]),)).read()
#             response = http.urlopen('GET', PM_DATA % (pmid), preload_content=False).read()
#
#             for match in re.finditer('<PubmedArticle>(.*?)</PubmedArticle>', response, re.S):
#                 article_ids = {}
#                 abstract = ''
#                 fulltext_link = None
#
#                 article = match.group(1)
#                 articleid_matches = re.finditer('<ArticleId IdType="([^"]*)">([^<]*?)</ArticleId>', article, re.S)
#                 abstract_matches = re.finditer('<AbstractText([^>]*)>([^<]*)</AbstractText>', article, re.S)
#                 articletitle = re.search('<ArticleTitle[^>]*>([^<]*)</ArticleTitle>', article, re.S).group(1).strip()
#
#                 for amatch in articleid_matches:
#                     article_ids[amatch.group(1).strip()] = amatch.group(2).strip()
#                 for amatch in abstract_matches:
#                     abstract += amatch.group(2).strip() + ' '
#
#                 if 'pmc' in article_ids:
#                     fulltext_link = 'http://www.ncbi.nlm.nih.gov/pmc/articles/%s/' % (article_ids['pmc'],)
#                 elif 'doi' in article_ids:
#                     fulltext_link = 'http://dx.crossref.org/%s' % (article_ids['doi'],)
#                 pmid = article_ids['pubmed'].strip()
#
#                 author_matches = re.finditer('<Author[^>]*>(.*?)</Author>', article, re.S)
#                 authors = []
#                 for match in author_matches:
#                     name = ''
#                     try:
#                         name = re.search('<LastName>([^<]*)</LastName>', match.group(1), re.S).group(1).strip()
#                         name = name + ' ' + re.search('<Initials>([^<]*)</Initials>', match.group(1), re.S).group(
#                             1).strip()
#                     except:
#                         pass
#                     authors.append(name)
#
#                 authors = ', '.join(authors)
#                 v = re.search('<Volume>([^<]*)</Volume>', article, re.S)
#                 if v:
#                     vol = v.group(1).strip()
#                 else:
#                     vol = ''
#                 p = re.search('<MedlinePgn>([^<]*)</MedlinePgn>', article, re.S)
#                 if p:
#                     pages = p.group(1).strip()
#                 else:
#                     pages = ''
#                 pubdate = re.search('<PubDate>.*?<Year>([^<]*)</Year>.*?<Month>([^<]*)</Month>', article, re.S)
#                 year = pubdate.group(1).strip()
#                 journal = re.search('<MedlineTA>([^<]*)</MedlineTA>', article, re.S).group(1).strip()
#                 # year month journal
#                 tomonthname = {
#                     '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr', '5': 'May', '6': 'Jun',
#                     '7': 'Jul', '8': 'Aug', '9': 'Sep', '10': 'Oct', '11': 'Nov', '12': 'Dec'
#                 }
#                 pm = pubdate.group(2).strip()
#                 if pm in tomonthname:
#                     pm = tomonthname[pm]
#
#                 pubmedValues.extend((articletitle, authors, journal, vol, pages, year, pm, abstract))
#
#         else:
#             response = 'false'
#     else:
#         response = 'false'
#     return json.dumps(pubmedValues)


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
    results = geneweaverdb.get_similar_genesets(gs_id, user_id, 0)
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


@app.route('/emphasis', methods=['GET', 'POST'])
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

@app.route('/search/')
def render_searchFromHome():
    """
    Executes searches from the home page. Constructs a sphinx query from the
    given user input and returns/renders the search results.

    returns
        a rendered flask template of the search results
    """

    form = flask.request.form
    # Terms from the search bar, as a list since there can be <= 3 terms
    terms = request.args.getlist('searchbar')
    sortby = request.args.get('sortBy')

    # If terms is empty, we can assume a) the user submitted a blank search,
    # or b) the user clicked on the search link. Both are handled the same way
    if not terms or (len(terms) == 1 and not terms[0]):
        return flask.render_template('search.html', paginationValues=None)

    if flask.request.method == 'GET':
        args = flask.request.args
    # pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    pagination_page = int(request.args.get('pagination_page'))
    # Build a list of search fields selected by the user (checkboxes) passed in as URL parameters
    # Associate the correct fields with each option given by the user
    field_list = {'searchGenesets': False, 'searchGenes': False, 'searchAbstracts': False, 'searchOntologies': False}
    search_fields = list()
    # Set which fields of GS data to search
    if request.args.get('searchGenesets'):
        search_fields.append('name,description,label')
        field_list['searchGenesets'] = True
    if request.args.get('searchGenes'):
        search_fields.append('genes')
        field_list['searchGenes'] = True
    if request.args.get('searchAbstracts'):
        search_fields.append('pub_authors,pub_title,pub_abstract,pub_journal')
        field_list['searchAbstracts'] = True
    if request.args.get('searchOntologies'):
        search_fields.append('ontologies')
        field_list['searchOntologies'] = True

    # Default search values
    search_fields.append('gs_id,gsid_prefixed,species,taxid')
    search_fields = ','.join(search_fields)
    default_filters = {'statusList': {'deprecated': 'no', 'provisional': 'no'}}

    # Perform a search
    search_values = search.keyword_paginated_search(
        terms, 
        pagination_page,
        search_fields,
        default_filters, 
        sortby
    )

    # If there is an error render a blank search page
    if search_values['STATUS'] == 'ERROR':
        return flask.render_template('search.html', paginationValues=None)

    if (search_values['STATUS'] == 'NO MATCHES'):
        return flask.render_template('search.html', paginationValues=None,
                noResults=True)

    ## Used to dynamically generate species tags
    species = geneweaverdb.get_all_species()
    species = species.items()

    ## Used to generate attribution tags
    attribs = geneweaverdb.get_all_attributions()

    return flask.render_template(
        'search.html',
        searchresults=search_values['searchresults'],
        genesets=search_values['genesets'],
        paginationValues=search_values['paginationValues'],
        field_list=field_list,
        searchFilters=search_values['searchFilters'],
        filterLabels=search_values['filterLabels'],
        species=species,
        attribs=attribs,
        userFilters=default_filters
    )


@app.route('/searchFilter.json', methods=['POST'])
def render_search_json():
    """
    Updates search results and renders the result based on the filters or pagination values
    a user selects. All of the filter/search data is contained in the POST request.

    returns
        a rendered flask template of the search results
    """

    # Get the user values from the request
    userValues = search.getUserFiltersFromApplicationRequest(request.form)
    # quick fix for now, this needs properly handle multiple terms
    # print 'debug vals: ' + str(userValues)
    userValues['search_term'] = [userValues['search_term']]
    # Get a sphinx search
    search_values = search.keyword_paginated_search(
        userValues['search_term'],
        userValues['pagination_page'], 
        userValues['search_fields'],
        userValues['userFilters'], 
        userValues['sort_by']
    )

    ## Used to dynamically generate species tags
    species = geneweaverdb.get_all_species()
    species = species.items()

    ## Used to generate attribution tags
    attribs = geneweaverdb.get_all_attributions()

    return flask.render_template(
        'search/search_wrapper_contents.html',
        searchresults=search_values['searchresults'],
        genesets=search_values['genesets'],
        paginationValues=search_values['paginationValues'],
        field_list=userValues['field_list'],
        searchFilters=search_values['searchFilters'],
        userFilters=userValues['userFilters'],
        filterLabels=search_values['filterLabels'],
        sort_by=userValues['sort_by'], 
        species=species,
        attribs=attribs)


@app.route('/searchsuggestionterms.json')
def render_search_suggestions():
    return flask.render_template('searchsuggestionterms.json')


@app.route('/projectGenesets.json', methods=['GET'])
def render_project_genesets():
    uid = flask.session.get('user_id')
    # Project (ID) that the user wants to view
    pid = flask.request.args['project']
    genesets = geneweaverdb.get_genesets_for_project(pid, uid)

    species = geneweaverdb.get_all_species()
    splist = []

    for sp_id, sp_name in species.items():
        splist.append([sp_id, sp_name])

    species = splist

    return flask.render_template('singleProject.html',
                                 genesets=genesets,
                                 proj={'project_id': pid},
                                 species=species)


@app.route('/getProjectGroups.json', methods=['GET'])
def render_project_groups():
    results = geneweaverdb.get_groups_by_project(request.args['proj_id'])
    return json.dumps(results)


@app.route('/changePvalues/<setSize1>/<setSize2>/<jaccard>', methods=["GET"])
def changePvalues(setSize1, setSize2, jaccard):
    tempDict = geneweaverdb.checkJaccardResultExists(setSize1, setSize2)
    print tempDict
    if len(tempDict) > 0:
        pValue = geneweaverdb.getPvalue(setSize1, setSize2, jaccard)
    else:
        return json.dumps(-1)

    return json.dumps(pValue)


# ****** ADMIN ROUTES ******************************************************************


class AdminEdit(adminviews.Authentication, BaseView):
    @expose('/')
    def __init__(self, *args, **kwargs):
        # self._default_view = True
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
        # print data
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
        # print data
        return json.dumps(data, default=date_handler)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/sizeofgenesets')
def admin_widget_6():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.size_of_genesets()
        # print data
        return json.dumps(data)
    else:
        return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/timetoruntools')
def admin_widget_7():
    if "user" in flask.g and flask.g.user.is_admin:
        tools = geneweaverdb.tools()
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
                temp = dict()
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


@app.route('/getServersideGroupTasksdb')
def get_db_grouptasks_data():
    results = geneweaverdb.get_server_side_grouptasks(request.args)
    for result in results:
        if result[2] == "Gene Set":
            assignment = curation_assignments.get_geneset_curation_assignment(result['task_id'])
            result['curation_assignment'] = assignment
    return json.dumps(results)

@app.route('/assignmentStatusAsString/<int:status>')
def get_assignment_status_string(status):
    status_text = {'status': curation_assignments.CurationAssignment.status_to_string(status)}
    return flask.jsonify(status_text)


def str_handler(obj):
    return str(obj)


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


# ************************************************************************


@app.route('/manage.html')
def render_manage():
    return flask.render_template('mygenesets.html')

# This function should be deprecated
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


@app.route('/removeGenesetsFromMultipleProjects')
def remove_genesets_from_multiple_projects():
    if 'user_id' in flask.session:
        results = geneweaverdb.remove_genesets_from_multiple_projects(request.args)
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


# check_results
#
# Checks to see if a given runhash exists within the results directory.
# Returns a JSON object with an attribute named 'exists,' which will be
# set to true if the results are present in the directory.
# This is used in the results template to make sure we don't view
# nonexistant/null results.
#
@app.route('/checkResults.json', methods=['GET'])
def check_results():
    if 'user_id' in flask.session:
        runhash = request.args.get('runHash', type=str)
        resultpath = config.get('application', 'results')

        # files = os.listdir(RESULTS_PATH)
        # files = filter(lambda f: path.isfile(path.join(RESULTS_PATH, f)), files)
        files = os.listdir(resultpath)
        files = filter(lambda f: path.isfile(path.join(resultpath, f)), files)
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
        resultpath = config.get('application', 'results')

        # Delete the files from the results folder too--traverse the results
        # folder and match based on runhash
        # files = os.listdir(RESULTS_PATH)
        # files = filter(lambda f: path.isfile(path.join(RESULTS_PATH, f)), files)
        files = os.listdir(resultpath)
        files = filter(lambda f: path.isfile(path.join(resultpath, f)), files)

        for f in files:
            rh = f.split('.')[0]

            if rh == runhash:
                # os.remove(path.join(RESULTS_PATH, f))
                os.remove(path.join(resultpath, f))

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
    alt_symbol = request.args['altSymbol']
    gs_id = request.args['gs_id']
    user_id = request.args['user_id']

    if type(alt_symbol) != str:
        alt_symbol = str(alt_symbol)

    # Lowercase comparisons because there were capitalization problems
    alt_symbol = alt_symbol.lower()

    genetypes = geneweaverdb.get_gene_id_types()
    genedict = {}

    for gtype in genetypes:
        genedict[gtype['gdb_name'].lower()] = gtype['gdb_id']

    if genedict.get(alt_symbol, None):
        session['extsrc'] = genedict[alt_symbol]
        alt_gene_id = session['extsrc']
    else:
        session['extsrc'] = 1
        alt_gene_id = session['extsrc']

    ## Retrieves the geneset but using the new alternate symbol ID
    gs = geneweaverdb.get_geneset(gs_id, user_id)
    geneset_values = []

    for gsv in gs.geneset_values:
        geneset_values.append({'ode_gene_id': gsv.ode_gene_id,
                               'ode_ref_id': gsv.ode_ref,
                               'gdb_id': gsv.gdb_id,
                               'alt_gene_id': alt_gene_id})

    return json.dumps(geneset_values)


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

@app.route('/datasources')
def render_datasources():
    attribs = geneweaverdb.get_all_attributions()
    attlist = []
    attcounts = {}
    for at_id, at_abbrev in attribs.items():
        attlist.append(at_abbrev)
        #attcounts.append(geneweaverdb.get_attributed_genesets(at_id, at_abbrev))
        attcounts[at_abbrev] = geneweaverdb.get_attributed_genesets(at_id, at_abbrev)

    return flask.render_template('datasources.html', attributions=attlist, attcounts=attcounts)

@app.route('/privacy')
def render_privacy():
    return flask.render_template('privacy.html')


@app.route('/usage')
def render_usage():
    return flask.render_template('usage.html')


@app.route('/register', methods=['GET', 'POST'])
def render_register():
    return flask.render_template('register.html')


@app.route('/reset', methods=['GET', 'POST'])
def render_reset():
    return flask.render_template('reset.html')


@app.route('/reset_submit.html', methods=['GET', 'POST'])
def reset_password():
    form = flask.request.form
    user = geneweaverdb.get_user_byemail(form['usr_email'])
    if user is None:
        return flask.render_template('reset.html', reset_failed=True)
    else:
        new_password = geneweaverdb.reset_password(user.email)
        notifications.send_email(user.email, "Password Reset Request",
                                 "Your new temporary password is: " + new_password)
        return flask.redirect('reset_success')


@app.route('/reset_success')
def render_success():
    return flask.render_template('password_reset.html')


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
    return flask.redirect('accountsettings')

@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    news_array = geneweaverdb.get_news()
    stats = geneweaverdb.get_stats()
    return flask.render_template('index.html', news_array=news_array, stats=stats)

@app.route('/register_submit.html', methods=['GET', 'POST'])
def json_register_successful():
    # Secret key for reCAPTCHA form
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
        ## optional parameter, remotep, containing the end user's IP can also
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

    return render_home()

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


@app.route('/notifications')
def render_notifications():
    return flask.render_template('notifications.html')


@app.route('/notifications.json')
def get_notifications_json():
    if 'user_id' in flask.session:
        if 'start' in request.args:
            start = request.args['start']
        else:
            start = 0
        if 'limit' in request.args:
            #
            limit = int(request.args['limit']) + 1
            notes = notifications.get_notifications(flask.session['user_id'], start, limit)
            if len(notes) < limit:
                has_more = False
            else:
                has_more = True
                del notes[-1]
        else:
            notes = notifications.get_notifications(flask.session['user_id'], start)
            has_more = False

        mark_as_read = []
        for note in notes:
            # need to format the timestamp as a string
            note['time_sent'] = note['time_sent'].strftime("%b %d, %Y at %I:%M %p")
            if not note['read']:
                mark_as_read.append(note['notification_id'])
        if mark_as_read:
            notifications.mark_notifications_read(*mark_as_read)
        return json.dumps({'notifications': notes, 'has_more': has_more})
    else:
        return json.dumps({'error': 'You must be logged in'})

@app.route('/unread_notification_count.json')
def get_unread_notification_count_json():
    if 'user_id' in flask.session:
        count = notifications.get_unread_count(flask.session['user_id'])
        return json.dumps({'unread_notifications': count})
    else:
        return json.dumps({'error': 'You must be logged in'})


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
        # user = geneweaverdb.get_user_id_by_apikey(apikey)
        # if (user == ''):
        # TODO ? - Do we want to throw error, or can anyone view ontology info?
        return geneweaverdb.get_all_ontologies_by_geneset(gs_id)

    def get(self, apikey, gs_id):
        # user = geneweaverdb.get_user_id_by_apikey(apikey)
        # if (user == ''):
        # TODO ? - Do we want to throw error, or can anyone view ontology info?
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

# Not Gets
# Projects
api.add_resource(AddProjectByUser, '/api/add/project/byuser/<apikey>/<project_name>/')
api.add_resource(AddGenesetToProject, '/api/add/geneset/toproject/<apikey>/<projectid>/<genesetid>/')
api.add_resource(DeleteGenesetFromProject, '/api/delete/geneset/fromproject/<apikey>/<projectid>/<genesetid>/')

# Tool Functions
api.add_resource(ToolGetFile, '/api/tool/get/file/<apikey>/<task_id>/<file_type>/')
api.add_resource(ToolGetLink, '/api/tool/get/link/<apikey>/<task_id>/<file_type>/')
api.add_resource(ToolGetStatus, '/api/tool/get/status/<task_id>/')

# Tool Calls
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

## Config loading should occur outside __main__ when proxying requests through
## a web server like nginx. uWSGI doesn't load anything in the __main__ block
app.secret_key = config.get('application', 'secret')
app.debug = True

if __name__ == '__main__':

    # config.loadConfig()
    # print config.CONFIG.sections()


    ## Register error handlers, should be turned off during debugging since
    ## stack traces are printed then
    if not app.debug:
        app.register_error_handler(400, error.bad_request)
        app.register_error_handler(401, error.unauthorized)
        app.register_error_handler(403, error.forbidden)
        app.register_error_handler(404, error.page_not_found)
        app.register_error_handler(Exception, error.internal_server_error)

    if config.get('application', 'host'):
        app.run(host=config.get('application', 'host'))

    else:
        app.run()

