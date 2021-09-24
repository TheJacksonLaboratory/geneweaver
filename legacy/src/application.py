"""
application
~~~~~~~~~~~

Geneweaver web main module.
"""
from collections import OrderedDict, defaultdict
from decimal import Decimal
from io import StringIO
from urllib.error import HTTPError
import datetime
import itertools
import json
import math
import os
import os.path as path
import re
import urllib

from flask import Flask, Response
from flask import (abort, jsonify, make_response, redirect, render_template,
                   request, send_from_directory, session, url_for)
from flask_admin import Admin, BaseView, expose
from flask_admin.base import MenuLink
from psycopg2 import Error
from psycopg2 import IntegrityError
from wand.image import Image
from werkzeug.routing import BaseConverter
import urllib3
import bleach
import flask
import flask_restful as restful

from decorators import login_required, create_guest, restrict_to_current_user
from tools import abbablueprint
from tools import booleanalgebrablueprint
from tools import combineblueprint
from tools import dbscanblueprint
from tools import genesetviewerblueprint
from tools import jaccardclusteringblueprint
from tools import jaccardsimilarityblueprint
from tools import msetblueprint
from tools import phenomemapblueprint
from tools import similargenesetsblueprint
from tools import tricliqueblueprint
import adminviews
import annotator
import config
import curation_assignments
import error
import genesetblueprint
import geneweaverdb
import notifications
import pub_assignments
import publication_generator
import report_bug
import search
import uploadfiles


app = Flask(__name__)
app.register_blueprint(abbablueprint.abba_blueprint)
app.register_blueprint(combineblueprint.combine_blueprint)
app.register_blueprint(dbscanblueprint.dbscan_blueprint)
app.register_blueprint(genesetblueprint.geneset_blueprint)
app.register_blueprint(genesetviewerblueprint.geneset_viewer_blueprint)
app.register_blueprint(phenomemapblueprint.phenomemap_blueprint)
app.register_blueprint(jaccardclusteringblueprint.jaccardclustering_blueprint)
app.register_blueprint(jaccardsimilarityblueprint.jaccardsimilarity_blueprint)
app.register_blueprint(booleanalgebrablueprint.boolean_algebra_blueprint)
app.register_blueprint(tricliqueblueprint.triclique_viewer_blueprint)
app.register_blueprint(msetblueprint.mset_blueprint)
app.register_blueprint(similargenesetsblueprint.similar_genesets_blueprint)

# *************************************

admin = Admin(app, name='GeneWeaver', index_view=adminviews.AdminHome(
    url='/admin', name='Admin'))

admin.add_view(
    adminviews.Viewers(name='Users', endpoint='viewUsers', category='User Tools'))
admin.add_view(
    adminviews.Viewers(name='Recent Users', endpoint='viewRecentUsers', category='User Tools'))
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

admin.add_link(MenuLink(name='My Account', url='/accountsettings'))


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
        return '+'.join(super(ListConverter, self).to_url(value) for value in values)


## Add a custom URL converter to handle list variables
app.url_map.converters['list'] = ListConverter

# *************************************

RESULTS_PATH = '/var/www/html/dev-geneweaver/results/'

HOMOLOGY_BOX_COLORS = ['#58D87E', '#588C7E', '#F2E394', '#1F77B4', '#F2AE72', '#F2AF28', 'empty', '#D96459',
                       '#D93459', '#5E228B', '#698FC6']
SPECIES_NAMES = ['Mus musculus', 'Homo sapiens', 'Rattus norvegicus', 'Danio rerio', 'Drosophila melanogaster',
                 'Macaca mulatta', 'empty', 'Caenorhabditis elegans', 'Saccharomyces cerevisiae', 'Gallus gallus',
                 'Canis familiaris']


@app.route('/register_or_login')
def register_or_login():
    return render_template('register_or_login.html')


@app.errorhandler(400)
def bad_request(e):
    return render_template('error/400.html'), 400


@app.errorhandler(401)
def unauthorized(e):
    return render_template('error/401.html'), 401


@app.errorhandler(403)
def forbidden(e):
    return render_template('error/403.html'), 403


@app.errorhandler(404)
def not_found(e):
    return render_template('error/404.html'), 404


@app.errorhandler(405)
def not_allowed(e):
    return render_template('error/405.html'), 405


@app.errorhandler(500)
def unexpected_error(e):
    return render_template('error/500.html'), 500


@app.route('/results/<path:filename>')
def static_results(filename):
    return send_from_directory(config.get('application', 'results'),
                               filename)


@app.before_request
def lookup_user_from_session():
    # lookup the current user if the user_id is found in the session
    flask.g.user = None
    user_id = session.get('user_id')
    if user_id:
        if request.remote_addr == session.get('remote_addr'):
            flask.g.user = geneweaverdb.get_user(user_id)
        else:
            # If IP addresses don't match we're going to reset the session for
            # a bit of extra safety. Unfortunately this also means that we're
            # forcing valid users to log in again when they change networks
            _logout()


@app.route('/logout')
def _logout():
    try:
        del session['user_id']
    except KeyError:
        pass
    try:
        del session['remote_addr']
    except KeyError:
        pass

    try:
        del flask.g.user
    except AttributeError:
        pass


def _form_login():
    user = None
    _logout()

    form = request.form
    if 'usr_email' in form:
        # TODO deal with login failure
        user = geneweaverdb.authenticate_user(
            form['usr_email'], form['usr_password'])

        if user is not None:
            session['user_id'] = user.user_id
            remote_addr = request.remote_addr

            if remote_addr:
                session['remote_addr'] = remote_addr

            geneweaverdb.update_user_seen(user.user_id)

    flask.g.user = user
    return user



def send_mail(to, subject, body):
    # print to, subject, body
    sendmail_location = "/usr/bin/mail"  # sendmail location
    p = os.popen("%s -t" % sendmail_location, "w")
    p.write("From: NoReply@geneweaver.org\n")
    p.write("To: %s\n" % to)
    p.write("Subject: %s\n" % subject)
    p.write("\n")  # blank line separating headers from body
    p.write(body)
    status = p.close()
    if status != 0:
        print("Sendmail exit status", status)


def _form_register():
    user = flask.g.user
    user_id = user.user_id if user else None
    is_guest = user.is_guest if user else None
    form = request.form
    if 'usr_email' in form:
        existing_user = geneweaverdb.get_user_byemail(form['usr_email'])
        if existing_user and is_guest:
            user = _form_login()
        elif existing_user:
            _logout()
            user = None
        elif user_id and is_guest:
            user = geneweaverdb.register_user_from_guest(
                form['usr_first_name'], form['usr_last_name'], form['usr_email'], form['usr_password'], user_id)
        else:
            _logout()
            user = geneweaverdb.register_user(
                form['usr_first_name'], form['usr_last_name'], form['usr_email'], form['usr_password'])

        return user


@app.route('/logout.json', methods=['GET', 'POST'])
def json_logout():
    _logout()
    return jsonify({'success': True})


@app.route('/login.json', methods=['POST'])
def json_login():
    json_result = dict()
    user = _form_login()
    if user is None:
        json_result['success'] = False
        return redirect(url_for('render_login_error'))
    else:
        json_result['success'] = True
        json_result['usr_first_name'] = user.first_name
        json_result['usr_last_name'] = user.last_name
        json_result['usr_email'] = user.email

    return redirect('/')

@app.route('/login_as/<int:as_user_id>', methods=['GET'])
def login_as(as_user_id):
    if not as_user_id:
        return jsonify({'error': ''})

    if 'user' not in flask.g:
        return jsonify({'error': ''})

    user = flask.g.user

    if not user.is_admin:
        return jsonify({'error': ''})

    as_user = geneweaverdb.get_user(as_user_id)

    if not as_user:
        return jsonify({'error': ''})


    session['user_id'] = as_user.user_id
    flask.g.user = as_user

    return redirect('/')


@app.route('/analyze')
@login_required(allow_guests=True)
def render_analyze():
    grp2proj = OrderedDict()
    active_tools = geneweaverdb.get_active_tools()

    if 'user' not in flask.g:
        return render_template('analyze.html', active_tools=active_tools)

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

    return render_template(
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
            # sorted(flask.g.user.shared_projects, key=lambda x: x.group_id)

    active_tools = geneweaverdb.get_active_tools()
    return render_template('analyze_shared.html', active_tools=active_tools, grp2proj=grp2proj)

@app.route('/get_user_projects.json')
@login_required(allow_guests=True)
def get_user_projects():

    if 'user' in flask.g:
        projects = []

        for p in flask.g.user.projects:
            ## Format datetime object to string
            if p.created:
                p.created = p.created.strftime('%Y-%m-%d')

            projects.append({
                'name': p.name,
                'project_id': p.project_id,
                'group_id': p.group_id,
                'created': p.created,
                'notes': p.notes,
                'star': p.star,
                'count': p.count,
                'group_name': p.group_name,
                'owner': p.owner
            })

        return jsonify(projects)
    else:
        return jsonify([])

@app.route('/projects')
@login_required(allow_guests=True)
def render_projects():
    return render_template('projects.html')


@app.route("/gwdb/get_group/<user_id>/")
def get_group(user_id):
    return geneweaverdb.get_all_member_groups(user_id)


@app.route("/gwdb/create_group/<group_name>/<group_private>/<user_id>/")
def create_group(group_name, group_private, user_id):
    # decode the group_name in case "/" had been encoded at "%2f"
    group_name = urllib.parse.unquote_plus(group_name)
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
@login_required(allow_guests=True)
@app.route('/share_projects.html')
def render_shareprojects():
    active_tools = geneweaverdb.get_active_tools()
    return render_template('share_projects.html', active_tools=active_tools)


@app.route('/analyze_new_project/<string:pj_name>.html')
@login_required(allow_guests=True)
def render_analyze_new_project(pj_name):
    # print 'dbg analyze proj'
    args = request.args
    active_tools = geneweaverdb.get_active_tools()
    user = geneweaverdb.get_user(session.get('user_id'))
    geneweaverdb.create_project(pj_name, user.user_id)
    return render_template('analyze.html', active_tools=active_tools)


@app.route('/curategeneset/edit/<int:gs_id>')
def render_curategeneset_edit(gs_id):
    return render_editgenesets(gs_id, True)


@app.route('/editgeneset/<int:gs_id>')
def render_editgenesets(gs_id, curation_view=False):
    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    species = geneweaverdb.get_all_species()
    pubs = geneweaverdb.get_all_publications(gs_id)
    #onts = geneweaverdb.get_all_ontologies_by_geneset(gs_id, "All Reference Types")
    ont_dbs = geneweaverdb.get_all_ontologydb()
    ref_types = geneweaverdb.get_all_gso_ref_type()
    ros = json.dumps(geneweaverdb.get_ontologies_by_ontdb_id(12))
    user_pref = json.loads(geneweaverdb.get_user(user_id).prefs)

    user_info = geneweaverdb.get_user(user_id)
    # SRP Implementation
    srp = geneweaverdb.get_srp(gs_id)
    gs_update = geneweaverdb.update_geneset_date(gs_id)
    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id or geneweaverdb.user_is_assigned_curation(user_id, gs_id) else None
    else:
        view = None

    if not (user_info.is_admin or user_info.is_curator or curation_view):
        ref_types = ["Publication, NCBO Annotator",
                     "Description, NCBO Annotator",
                     "Publication, MI Annotator",
                     "Description, MI Annotator",
                     "GeneWeaver Primary Inferred",
                     "Manual Association", ]

    return render_template(
        'editgenesets.html',
        geneset=geneset,
        user_id=user_id,
        species=species,
        pubs=pubs,
        view=view,
        ref_types=ref_types,
        ont_dbs=ont_dbs,
        curation_view=curation_view,
        relation_onts=ros,
        user_pref=user_pref,
        # SRP Implementation
        srp=srp,
        gs_update=gs_update
    )

@app.route('/addRelationsOntology', methods=['POST'])
@login_required(json=True)
def add_relations_ontology():
    gs_id = request.form.get('gs_id')
    ont_ids = request.form.getlist('ont_ids')
    ro_ont_ids = request.form.getlist('ro_ont_id')
    for ont_id in ont_ids:
        for ro_ont_id in ro_ont_ids:
            try:
                geneweaverdb.add_ro_ont_to_geneset(gs_id, ont_id, ro_ont_id)
            except IntegrityError as e:
                try:
                    geneweaverdb.update_ro_ont_to_geneset(gs_id, ont_id, ro_ont_id)
                except Error as e:
                    print('RDF Update Error: ' + e.message)

    return jsonify({'success': True})


@app.route('/relationshipOntologies')
def relationshipOntologies():
    ros = geneweaverdb.get_ontologies_by_ontdb_id(12)
    select2 = {"results": ros, "pagination": {"more": False}}
    return jsonify(select2)


@app.route('/assign_genesets_to_curation_group.json', methods=['POST'])
@login_required(json=True)
def assign_genesets_to_curation_group():
    user = flask.g.user
    user_id = user.user_id

    note = bleach.clean(request.form.get('note', ''), strip=True)
    grp_id = request.form.get('grp_id')

    gs_ids = request.form.getlist('gs_ids[]', type=int)

    status = {}
    for gs_id in gs_ids:
        geneset = geneweaverdb.get_geneset(gs_id, user_id)

        # allow a geneset owner or GW admin to assign the geneset for curation
        if geneset and (user.user_id == geneset.user_id or user.is_admin):
            curation_assignments.submit_geneset_for_curation(geneset.geneset_id, grp_id, note)
            status[gs_id] = {'success': True}
        else:
            status[gs_id] = {'success': False}

    response = jsonify(results=status)

    return response


@app.route('/nominate_public_geneset.json', methods=['POST'])
def nominate_public_geneset_for_curation():
    if 'user_id' in session:
        gs_id = request.form.get('gs_id')
        notes = request.form.get('notes')

        # TODO: Just throwing raw exception message is not prefered.
        # It should be redirected to error page.
        try:
            curation_assignments.nominate_public_gs(gs_id, notes)
            response = Response()
        except IntegrityError as err:
            response = jsonify(message=str(err))
            response.status_code = 400
        except Exception as err:
            response = jsonify(message=str(err))
            response.status_code = 500

    else:
        # user is not logged in
        response = jsonify(message='You must be logged in to perform this function')
        response.status_code = 401

    return response

@app.route('/assign_genesets_to_curator.json', methods=['POST'])
@login_required(json=True)
def assign_genesets_to_curator():
    user = flask.g.user
    user_id = user.user_id

    note = bleach.clean(request.form.get('note', ''), strip=True)
    curator = request.form.get('usr_id')
    gs_ids = request.form.getlist('gs_ids[]', type=int)
    owned_groups = geneweaverdb.get_all_owned_groups(user_id)

    status = {}
    for gs_id in gs_ids:
        assignment = curation_assignments.get_geneset_curation_assignment(gs_id)
        if assignment:
            if assignment.group in [g['grp_id'] for g in owned_groups]:
                assignment.assign_curator(curator, user_id, note)
                status[gs_id] = {'success': True}
            else:
                status[gs_id] = {'success': False,
                                 'message': "You are not an owner of the group and cannot assign a curator"}
        else:
            status[gs_id] = {'success': False,
                             'message': "Error assigning curator, GeneSet " + str(gs_id) +
                                        "does not have an active curation record"}
        response = jsonify(results=status)

    return response


@app.route('/assign_publications_to_curator.json', methods=['POST'])
@login_required(json=True)
def assign_publications_to_curator():
    user_id = session['user_id']
    notes = bleach.clean(request.form.get('note', ''), strip=True)
    curator = request.form.get('usr_id')
    pub_assign_ids = request.form.getlist('pub_assign_ids[]', type=int)
    group_id = request.form.get('group_id')
    owned_groups = geneweaverdb.get_all_owned_groups(session['user_id'])

    status = {}
    for pub_assign_id in pub_assign_ids:
        if int(group_id) in [g['grp_id'] for g in owned_groups]:
            assignment = pub_assignments.get_publication_assignment(pub_assign_id)
            assignment.assign_to_curator(curator, user_id, notes)
            status[pub_assign_id] = {'success': True}
        else:
            status[pub_assign_id] = {'success': False,
                                     'message': "You are not an owner of the group and cannot assign a curator"}
        response = jsonify(results=status)

    return response


@app.route("/assign_geneset_to_curator.json", methods=['POST'])
@login_required(json=True)
def assign_geneset_to_curator():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('note', ''), strip=True)
    gs_id = request.form.get('gs_id', type=int)
    curator = request.form.get('curator', type=int)

    assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

    if assignment:
        owned_groups = geneweaverdb.get_all_owned_groups(session['user_id'])
        if assignment.group in [g['grp_id'] for g in owned_groups]:

            curator_info = geneweaverdb.get_user(curator)

            assignment.assign_curator(curator, user_id, notes)

            response = jsonify(success=True, curator_name=curator_info.first_name + " " + curator_info.last_name, curator_email=curator_info.email)

    else:
        response = jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
        response.status_code = 412

    return response


@app.route("/geneset_ready_for_review.json", methods=['POST'])
@login_required(json=True)
def geneset_ready_for_review():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('note', ''), strip=True)
    gs_id = request.form.get('gs_id', type=int)

    assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

    if assignment:
        if user_id == assignment.curator:
            assignment.submit_for_review(notes)
            response = jsonify(success=True)
        else:
            response = jsonify(success=False, message='You do not have permissions to perform this action.')
            response.status_code = 403
    else:
        response = jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
        response.status_code = 412

    return response


@app.route("/mark_geneset_reviewed.json", methods=['POST'])
@login_required(json=True)
def mark_geneset_reviewed():
    user = flask.g.user

    notes = bleach.clean(request.form.get('note', ''), strip=True)
    gs_id = request.form.get('gs_id', type=int)
    review_ok = request.form.get('review_ok') in ['true', '1']

    assignment = curation_assignments.get_geneset_curation_assignment(gs_id)

    if assignment:
        if user.user_id == assignment.reviewer:
            if review_ok:
                tier = request.form.get('tier', type=int)
                assignment.review_passed(notes, tier, user)
            else:
                assignment.review_failed(notes)
            response = jsonify(success=True)
        else:
            response = jsonify(success=False, message='You do not have permissions to perform this action.')
            response.status_code = 403
    else:
        response = jsonify(success=False, message="Error assigning curator, GeneSet does not have an active curation record")
        response.status_code = 412

    return response


@app.route('/publication_assignment', defaults={'group_id': None})
@app.route('/publication_assignment/<int:group_id>')
@login_required()
def render_assign_publication(group_id):
    generators = []
    user_id = session['user_id']
    my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)

    if group_id and group_id in (group['grp_id'] for group in my_groups):
        generators = publication_generator.list_generators_by_group([str(group_id)])

    if not group_id:
        generators = publication_generator.list_generators(user_id, [str(group['grp_id']) for group in my_groups])

    return render_template('publication_assignment.html',
                                 myGroups=my_groups,
                                 myGenerators=generators)


@app.route('/add_generator', methods=['POST'])
@login_required(json=True)
def add_generator():
    user_id = session['user_id']
    generator_name = request.form.get('name', '')
    generator_querystring = request.form.get('querystring', '')
    group_id = request.form.get('group_id', type=int)

    if generator_name and generator_querystring and group_id:
        generator_dict = {
            'name': generator_name,
            'querystring': generator_querystring,
            'grp_id': group_id,
            'usr_id': user_id
        }
        generator = publication_generator.PublicationGenerator(**generator_dict)

        if not generator:
            # couldn't create a generator
            response = jsonify(message="Generator not created")
            response.status_code = 500
        else:
            # generator created
            response = jsonify(message="Generator successfully added to group")
    else:
        response = jsonify(success=False, message='You must provide a generator name, query string and group id.')
        response.status_code = 412

    return response


@app.route('/update_generator', methods=['POST'])
@login_required(json=True)
def update_generator():
    user_id = session['user_id']

    generator_id = request.form.get('id', '')
    generator_name = request.form.get('name', '')
    generator_querystring = request.form.get('querystring', '')
    group_id = request.form.get('group_id', type=int)

    if generator_id and generator_name and generator_querystring and group_id:
        generator_dict = {
            'stubgenid': generator_id,
            'name': generator_name,
            'querystring': generator_querystring,
            'grp_id': group_id,
            'usr_id': user_id
        }
        try:
            generator = publication_generator.PublicationGenerator(**generator_dict)
            generator.save()
            response = jsonify(message="Generator successfully updated")
        except Error as error:
            response = jsonify(message="Generator not saved.  Error encountered while updating database: {0}".format(error))
    else:
        response = jsonify(success=False,
                                 message='You must provide a generator id, name, query string and group id.')
        response.status_code = 412

    return response


@app.route('/delete_generator/<int:generator_id>/<int:usr_id>/')
@login_required(json=True)
def delete_generator(generator_id, usr_id):
    flask_user = session['user_id']
    if not (flask_user == usr_id):
        # user owning generator not current user
        response = jsonify(message='You cannot delete a generator belonging to another user.')
        response.status_code = 412

    else:
        generator = publication_generator.PublicationGenerator.get_generator_by_id(generator_id)
        if generator:
            row_count = publication_generator.delete_generator(generator)
            if row_count > 0:
                # generator deleted
                response = jsonify(message="Generator successfully deleted")
            else:
                # couldn't delete a generator
                response = jsonify(message="Generator not deleted")
                response.status_code = 500
        else:
            response = jsonify(message="No generator for that id " + str(generator_id))
            response.status_code = 412

    return response


@app.route('/run_generator/<int:generator_id>')
@login_required(json=True)
def run_generator(generator_id):
    pubmed_entries = []
    generator = publication_generator.PublicationGenerator.get_generator_by_id(generator_id)
    try:
        results = generator.run()
    except HTTPError:
        print("HTTPError trying to run generator {}".format(generator.name))
        return json.dumps({'error': 'Problem communicating with PubMed, please try again later...'})
    return json.dumps(results.__dict__)


@app.route('/get_generator_results')
def get_generator_results():
    sEcho = request.args.get('sEcho', type=int)
    iDisplayStart = request.args.get('start', type=int)
    iDisplayLength = request.args.get('length', type=int)
    search_response = request.args.get('pubmedResult[search_response]')
    pubmed_results = publication_generator.PubmedResult(search_response)
    results = pubmed_results.fetch(iDisplayStart, iDisplayLength)
    response = {'sEcho': sEcho,
                'iTotalRecords': results.total_count,
                'iTotalDisplayRecords': results.total_count,
                'aaData': results.current_rows
                }
    return json.dumps(response)


@app.route('/get_publication_by_pubmed_id/<pubmed_id>.json')
@login_required(json=True)
def get_publication_by_pubmed_id(pubmed_id):
    publication = geneweaverdb.get_publication_by_pubmed(pubmed_id)
    if publication:
        response = jsonify(**publication.__dict__)
    else:
        response = jsonify(message="Publication Not Found")
        response.status_code = 404

    return response


@app.route('/assign_publication_to_group.json', methods=['POST'])
@login_required(json=True)
def assign_publication_to_group():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pubmed_id = request.form.get('pubmed_id')
    group_id = request.form.get('group_id', type=int)

    if group_id not in geneweaverdb.get_user_groups(user_id):
        response = jsonify(message="You do not have permissions to assign tasks to this group.")
        response.status_code = 403

    else:
        # lookup publication in database, if it doesn't exist in the db yet
        # this will add it
        publication = geneweaverdb.get_publication_by_pubmed(pubmed_id, create=True)

        if not publication:
            # didn't find matching publication in database or querying pubmed
            response = jsonify(message="Publication Not Found")
            response.status_code = 404

        else:
            # check to see if publication is already assigned to the group
            publication_assignment = pub_assignments.get_publication_assignment_by_pub_id(publication.pub_id, group_id)

            if publication_assignment and publication_assignment.state != publication_assignment.REVIEWED:
                # is it already an active task for this group?
                response = jsonify(message="Publication is already assigned to this group.")
                response.status_code = 422

            else:
                # everything is good,  do the assignment
                pub_assignments.queue_publication(publication.pub_id, group_id, notes)
                response = jsonify(message="Publication successfully assigned to group")

    return response


@app.route('/assign_publications_to_group.json', methods=['POST'])
@login_required(json=True)
def assign_publications_to_group():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pubmed_ids = request.form.getlist('pubmed_ids[]', type=str)
    group_id = request.form.get('group_id', type=int)

    if group_id not in geneweaverdb.get_user_groups(user_id):
        response = jsonify(message="You do not have permissions to assign tasks to this group.")
        response.status_code = 403

    else:
        status = {}
        for pubmed_id in pubmed_ids:
            # lookup publication in database, if it doesn't exist in the db yet
            # this will add it
            publication = geneweaverdb.get_publication_by_pubmed(pubmed_id, create=True)

            if not publication:
                # didn't find matching publication in database or querying pubmed
                status[pubmed_id] = {
                    'success': False,
                    'message': "Publication Not Found."
                }

            else:
                # check to see if publication is already assigned to the group
                publication_assignment = pub_assignments.get_publication_assignment_by_pub_id(publication.pub_id, group_id)
                if publication_assignment and publication_assignment.state != publication_assignment.REVIEWED:
                    # is it already an active task for this group?
                    status[pubmed_id] = {
                        'success': False,
                        'message': "Publication is already assigned to this group."
                    }

                else:
                    # everything is good,  do the assignment
                    pub_assignments.queue_publication(publication.pub_id, group_id, notes)
                    status[pubmed_id] = {
                        'success': True,
                        'message': "Publication successfully assigned to group"
                    }
        response = jsonify(results=status)

    return response


@app.route("/assign_publication_to_curator.json", methods=['POST'])
@login_required(json=True)
def assign_publication_to_curator():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pub_assignment_id = request.form.get('assignment_id', type=int)
    curator = request.form.get('curator', type=int)

    assignment = pub_assignments.get_publication_assignment(pub_assignment_id)

    if assignment:
        owned_groups = geneweaverdb.get_all_owned_groups(session['user_id'])
        curator_groups = geneweaverdb.get_all_owned_groups(curator) + geneweaverdb.get_all_member_groups(curator)

        # make sure user has permission to assign this publication, and the
        # user they are assigning it to actually belongs to the group
        if assignment.group not in [g['grp_id'] for g in owned_groups]:
            response = jsonify(message='You do not have permissions to perform this action.')
            response.status_code = 401
        elif assignment.group not in [g['grp_id'] for g in curator_groups]:
            response = jsonify(message='User is not a member of this group.')
            response.status_code = 401
        else:
            curator_info = geneweaverdb.get_user(curator)
            assignment.assign_to_curator(curator, user_id, notes)

            response = jsonify(success=True,
                                     curator_name=curator_info.first_name + " " + curator_info.last_name,
                                     curator_email=curator_info.email)

    else:
        response = jsonify(success=False, message="Error assigning curator, publication does not have an active curation record")
        response.status_code = 403

    return response


@app.route("/mark_pub_assignment_as_complete.json", methods=['POST'])
@login_required(json=True)
def mark_pub_assignment_as_complete():
    user_id = session['user_id']

    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pub_assignment_id = request.form.get('assignment_id', type=int)

    assignment = pub_assignments.get_publication_assignment(pub_assignment_id)

    if assignment:

        if assignment.assignee != user_id:
            response = jsonify(message='You do not have permissions to perform this action.')
            response.status_code = 403
        elif assignment.state != assignment.ASSIGNED:
            response = jsonify(message='This assignment must first be assigned to you.')
            response.status_code = 403
        else:
            # check to make sure that all attached geneset assignments are approved
            all_ready_or_approved = True
            for gs in geneweaverdb.get_genesets_for_publication(assignment.pub_id, user_id):
                gs_state = curation_assignments.get_geneset_curation_assignment(gs.geneset_id).state
                if gs_state < curation_assignments.CurationAssignment.READY_FOR_REVIEW:
                    all_ready_or_approved = False
                    # if even one fails the test then we can jump out of the loop
                    break

            if all_ready_or_approved:
                assignment.mark_as_complete(notes)
                response = jsonify(success=True)
            else:
                response = jsonify(
                    message='All associated geneset curation tasks must first be reviewed or ready for review.'
                )
                response.status_code = 403

    else:
        response = jsonify(message='Publication Assignment Not Found.')
        response.status_code = 404

    return response


@app.route("/close_pub_assignment.json", methods=['POST'])
@login_required(json=True)
def close_pub_assignment():
    user_id = session['user_id']
    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pub_assignment_id = request.form.get('assignment_id', type=int)
    assignment = pub_assignments.get_publication_assignment(pub_assignment_id)

    if assignment:
        if assignment.assigner != user_id:
            response = jsonify(message='You do not have permissions to perform this action.')
            response.status_code = 403
        elif assignment.state != assignment.READY_FOR_REVIEW:
            response = jsonify(message='The assignment must first be made ready for review.')
            response.status_code = 403
        else:
            # check to make sure that all attached geneset assignments are approved
            all_approved = True
            for gs in geneweaverdb.get_genesets_for_publication(assignment.pub_id, user_id):
                gs_state = curation_assignments.get_geneset_curation_assignment(gs.geneset_id).state
                if gs_state < curation_assignments.CurationAssignment.REVIEWED:
                    all_approved = False
                    # if even one fails the test then we can jump out of the loop
                    break

            if all_approved:
                assignment.review_accepted(notes)
                response = jsonify(success=True)
            else:
                response = jsonify(
                    message='Any associated geneset curation tasks must first be reviewed and approved.'
                )
                response.status_code = 403

    else:
        response = jsonify(message='Publication Assignment Not Found.')
        response.status_code = 404

    return response


@app.route("/pub_assignment_rejection.json", methods=['POST'])
@login_required(json=True)
def pub_assignment_rejection():
    user_id = session['user_id']
    notes = bleach.clean(request.form.get('notes', ''), strip=True)
    pub_assignment_id = request.form.get('assignment_id', type=int)
    assignment = pub_assignments.get_publication_assignment(pub_assignment_id)

    if assignment:

        if assignment.assigner != user_id:
            response = jsonify(message='You do not have permissions to perform this action.')
            response.status_code = 403
        elif assignment.state != assignment.READY_FOR_REVIEW:
            response = jsonify(message='Invalid state.')
            response.status_code = 403
        else:
            assignment.review_rejected(notes)
            response = jsonify(success=True)
    else:
        response = jsonify(message='Publication Assignment Not Found.')
        response.status_code = 404

    return response


@app.route('/viewPubAssignment/<int:assignment_id>')
@login_required()
def render_pub_assignment(assignment_id):
    publication = None
    view = None
    pub_assignment = None
    geneset_assignmnet_map = {}
    curator = None
    curation_team_members = None
    species = None
    gs_ids = []

    other_gs_ids = []

    if 'user_id' in session:
        uid = session['user_id']
        pub_assignment = pub_assignments.get_publication_assignment(assignment_id)
        if pub_assignment:
            publication = geneweaverdb.get_publication(pub_assignment.pub_id)

            if uid == pub_assignment.assignee and uid == pub_assignment.assigner:
                if pub_assignment.state == pub_assignment.ASSIGNED:
                    view = 'assignee'
                    species = geneweaverdb.get_all_species()
                else:
                    view = 'assigner'
            elif uid == pub_assignment.assignee:
                view = 'assignee'
                species = geneweaverdb.get_all_species()
            elif uid == pub_assignment.assigner:
                view = 'assigner'
            elif pub_assignment.group in [g['grp_id'] for g in geneweaverdb.get_all_owned_groups(uid)]:
                view = 'group_admin'
            elif uid in [u['usr_id'] for u in geneweaverdb.get_group_members(pub_assignment.group)]:
                view = 'group_member'
            else:
                view = 'no_access'

            if view != 'no_access':
                genesets = pub_assignment.get_genesets()
                genesets_for_pub = geneweaverdb.get_genesets_for_publication(pub_assignment.pub_id, uid)
                other_genesets = [gs for gs in genesets_for_pub if gs.geneset_id not in [gs.geneset_id for gs in genesets]]
                if pub_assignment.state != pub_assignment.UNASSIGNED:
                    curator = geneweaverdb.get_user(pub_assignment.assignee)
                group_name = geneweaverdb.get_group_name(pub_assignment.group)

                ## Remove sets that have been deleted by the curators or others
                genesets = [gs for gs in genesets if gs.status != 'deleted']
                other_genesets = [gs for gs in other_genesets if gs.status != 'deleted']

                # create a dictionary that maps each gene set to a curation assignment if there is one
                all_genesets = genesets + other_genesets
                for gs in all_genesets:
                    geneset_assignmnet_map[gs.geneset_id] = curation_assignments.get_geneset_curation_assignment(gs.geneset_id)

            if view == 'assigner' or view == 'group_admin':
                # needed for rendering the assignment dialog
                curation_team_members = [geneweaverdb.get_user(uid) for uid in geneweaverdb.get_group_users(pub_assignment.group)]
        else:
            # publication assignment not found
            abort(404)

    return render_template('viewPubAssignment.html', pub=publication,
                           view=view, assignment=pub_assignment,
                           curator=curator, group_name=group_name,
                           species=species,
                           curation_team=curation_team_members,
                           genesets=genesets, other_genesets=other_genesets,
                           assignment_map=geneset_assignmnet_map)


@app.route('/save_pub_note.json', methods=['POST'])
@login_required(json=True)
def save_pub_assignment_note():
    uid = session['user_id']
    pub_assignment_id = request.form.get('assignment_id', type=int)

    notes = bleach.clean(request.form.get('notes', ''), strip=True)

    assignment = pub_assignments.get_publication_assignment(pub_assignment_id)

    gid = assignment.group
    if assignment:
        # make sure user is authorized (assignee, assigner, group admin)
        if uid == assignment.assignee or uid == assignment.assigner or int(gid) in [g['grp_id'] for g in geneweaverdb.get_all_owned_groups(uid)]:
            # SAVE notes to DB
            assignment.update_notes(notes)
            response = jsonify(success=True)
        else:
            response = jsonify(message='You do not have permissions to perform this action.')
            response.status_code = 403
    else:
        response = jsonify(message='Assignment not found.')
        response.status_code = 404

    return response


@app.route('/create_geneset_stub.json', methods=['POST'])
@login_required(json=True)
def create_geneset_stub():
    user_id = session['user_id']
    stubs = json.loads(request.form.get('stubs'))
    pub_assign_id = request.form.get('pub_assign_id', type=int)
    species_id = request.form.get('species_id', type=int)
    geneset_assignment_map = {}

    assignment = pub_assignments.get_publication_assignment(pub_assign_id)

    if assignment.state != assignment.ASSIGNED and assignment.assignee != user_id:
        response = jsonify(message='You do not have permissions to perform this action.')
        response.status_code = 403
    else:
        group_id = assignment.group
        gs_ids = [assignment.create_geneset_stub(stub['gs_name'], stub['gs_label'], stub['gs_description'], species_id, group_id) for stub in stubs]
        for gs in gs_ids:
            assignment = curation_assignments.get_geneset_curation_assignment(gs)
            geneset_assignment_map[gs] = {"status_id": assignment.state, "status_name": assignment.status_to_string()}
        response = jsonify(gs_ids=gs_ids, assignment_map=geneset_assignment_map)

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
    ro_ont_id = request.args.get('ro_ont_id')


    if (flag == "true"):
        geneweaverdb.add_ont_to_geneset(gs_id, ont_id, gso_ref_type)
    else:
        if ro_ont_id:
            remove_relation_ontology(ont_id, gs_id, ro_ont_id)
        ro_count = geneweaverdb.count_relation_ontologies(gs_id, ont_id)
        if ro_count < 1:
            geneweaverdb.remove_ont_from_geneset(gs_id, ont_id, gso_ref_type)

    return json.dumps(True)

def remove_relation_ontology(ont_id, gs_id, ro_ont_id):
    try:
        geneweaverdb.remove_relation_ont(gs_id, ont_id, ro_ont_id)
        result = {'success': True}
    except Error:
        result = {'success': False}

    return result

@app.route('/rerun_annotator.json', methods=['POST'])
@login_required(json=True)
def rerun_annotator():
    """
    Reruns the annotator tool for a given geneset and updates its annotations.
    """

    publication = request.form['publication']
    description = request.form['description']
    gs_id = request.form['gs_id']
    user_id = session['user_id'] if session['user_id'] else 0
    user = geneweaverdb.get_user(user_id)

    # Only admins, curators, and owners can make changes
    if ((not user.is_admin and not user.is_curator) and
            (not geneweaverdb.user_is_owner(user_id, gs_id) and
                     not geneweaverdb.user_is_assigned_curation(user_id,
                                                                gs_id))):
        response = jsonify(
            {'error': 'You do not have permission to update this GeneSet'})
        response.status_code = 403
        return response

    # get user's annotator preference
    user_prefs = json.loads(user.prefs)

    annotator.rerun_annotator(gs_id, publication, description, user_prefs)

    return jsonify({'success': True})


@app.route('/get_gene_ref_ID.json', methods=['GET'])
def get_gene_ref_ID():
    """
    Returns a json list of genes that fit the query for auto complete
    """
    ids = geneweaverdb.get_ode_ref_id(request.args['search'], request.args['sp_id'])
    data = {'list': ids}
    return jsonify(data)


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

    for ont in onts:
        if ont.ro_ont_id:
            ro = geneweaverdb.get_ontology_by_id(ont.ro_ont_id)
            ont.ro_name = ro.name
            ont.ro_ont_ref_id = ro.reference_id
        else:
            ont.ro_name = ''
            ont.ro_ont_ref_id = ''

    ## Convert ontdb references to a dict so they're easier to lookup
    for ont in ontdb:
        ontdbdict[ont.ontologydb_id] = ont

    ## Format ontologies for display, only send the min. requirements
    for ont in onts:
        o = {
            'reference_id': ont.reference_id, 
            'name': ont.name,
            'dbname': ontdbdict[ont.ontdb_id].name,
            'ontdb_id': ont.ontdb_id,
            'ont_id': ont.ontology_id,
            'ro_name': ont.ro_name,
            'ro_id': ont.ro_ont_id,
            'ro_ref_id': ont.ro_ont_ref_id
        }

        ontret.append(o)

    return ontret


@app.route('/getGenesetAnnotations.json', methods=['GET'])
@login_required(json=True)
def get_geneset_annotations():
    """
    Returns a list of terms that have been annotated to the given gene set.

    args
        request.args['gs_id']: gene set ID to use when retrieving annotations

    returns
        a list of JSON serialized annotation objects with the following fields:

        {
            reference_id: the external identifier for the term (e.g. GO:123456)
            name:         the ontology term name (e.g. death)
            dbname:       ontology this term comes from (e.g. GO)
            ontdb_id:     internal GW identifier for the ontology
            ont_id:       internal GW identifier for this term
            ref_type:     the type of association that produced this annotation
        }
    """

    args = request.args

    if 'gsid' not in args:
        return jsonify({'error': 'Missing gs_id'})

    gsid = args['gsid']
    annos = get_ontology_terms(gsid)

    for an in annos:
        ref_type = geneweaverdb.get_geneset_annotation_reference(
            gsid, an['ont_id']
        )

        an['ref_type'] = ref_type

    return jsonify({'annotations': annos})


@app.route('/ontologyTermSearch.json', methods=['GET'])
@login_required(allow_guests=True, json=True)
def search_ontology_terms():
    """
    Returns a list of ontology terms that match a given string typed in by the
    user. Used for ontology term autocomplete on the edit gene set page.
    """

    args = request.args

    if 'search' not in args:
        return jsonify({'error': 'No search text provided', 'terms': []})

    search = args['search']
    terms = []

    for ont in geneweaverdb.search_ontology_terms(search):
        ref_id = ont['ont_ref_id']
        name = ont['ont_name']
        ontdb_name = ont['ontdb_name']

        terms.append({
            'label': '%s: %s (%s)' % (ref_id, name, ontdb_name),
            'value': '',
            'name': name,
            'ont_id': ont['ont_id'],
            'ontdb_name': ontdb_name,
            'ref_id': ref_id
        })

    return jsonify({'terms': terms})


@app.route('/initOntTree')
def init_ont_tree():
    parentdict = {}
    gs_id = request.args['gs_id']
    ontdb_id = request.args['universe']

    # Gather root annotations for given ontology database
    root_annotations = geneweaverdb.get_all_root_ontology_for_database(ontdb_id)

    for annotation in root_annotations:
        parentdict[annotation.ontology_id] = [[annotation.ontology_id]]

    # Gather all terms associated with the geneset within the selected ontology
    assoc_annotations = geneweaverdb.get_all_ontologies_by_geneset_and_db(gs_id, ontdb_id)

    for annotation in assoc_annotations:
        ## Path is a list of lists since there may be more than one
        ## root -> term path for a particular ontology term
        paths = geneweaverdb.get_all_parents_to_root_for_ontology(annotation.ontology_id)

        for path in paths:
            root = path[0]
            if parentdict.get(root) and path not in parentdict.get(root):
                parentdict[root].append(path)

    tree = {}
    ontcache = {}

    for ontid, paths in parentdict.items():
        paths.sort()

        for path in paths:
            ontpath = []

            for p in path:
                if p not in ontcache:
                    p = geneweaverdb.get_ontology_by_id(p)
                    ontcache[p.ontology_id] = p

                else:
                    p = ontcache[p]

                node = create_new_child_dict(p, ontdb_id)
                ontpath.append(node)

            for i in range(0, len(ontpath)):
                if not i == len(ontpath) - 1:
                    ontpath[i]['expand'] = True

                    child_annotations = geneweaverdb.get_all_children_for_ontology(ontpath[i]['key'])
                    children = list()

                    for j in range(0, len(child_annotations)):
                        child_node = dict()
                        child_node["title"] = child_annotations[j].name

                        if child_annotations[j].children == 0:
                            child_node["isFolder"] = False
                        else:
                            child_node["isFolder"] = True

                        child_node["isLazy"] = True
                        child_node["key"] = child_annotations[j].ontology_id
                        child_node["db"] = False
                        children.append(child_node)

                        if child_node in [s for s in children if s["title"] == ontpath[i + 1]["title"]]:
                            children.remove(child_node)

                    ontpath[i]["children"] = children

                if len(ontpath) > 1:
                    ontpath[i]['select'] = True

            tree = mergeTreePath(tree, ontpath)

    tree = convertTree(tree)

    return json.dumps(tree)


def doesChildExist(child, children):
    """
    Given a list of children, checks to see if a child node already exists
    in the given list. Used to prevent duplicates from cropping up in the
    ontology tree.
    """

    children = [c['key'] for c in children]

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

    :param root:    the top level (root) node of the tree structure
    :return:        formatted tree (see create_new_child_dict for relevant 
                    fields)
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
    Merges a single path from an ontology tree into an existing tree structure.
    Used to merge section of an ontology that may overlap. The list of nodes in
    the path should be in order i.e. from root -> leaf. 
    In the returned tree, every element except the 'node' key is a child of the 
    previous node.

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
    # new_child_dict["children"] = set()
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
    if 'user_id' in session:
        user_id = session['user_id']
        result = geneweaverdb.update_geneset(user_id, request.form)
        result['usr_id'] = user_id
        return json.dumps(result)

@app.route('/curategenesetgenes/<int:gs_id>')
def render_curategenesetgenes(gs_id):
    return render_editgeneset_genes(gs_id, curation_view=True)

@app.route('/editgenesetgenes/<int:gs_id>')
def render_editgeneset_genes(gs_id, curation_view=False):
    user_id = session['user_id'] if 'user_id' in session else 0
    user_info = geneweaverdb.get_user(user_id)
    uploadfiles.create_temp_geneset_from_value(gs_id)
    meta = uploadfiles.get_temp_geneset_gsid(gs_id)
    geneset = geneweaverdb.get_geneset(gs_id, user_id, temp='temp')
    platform = geneweaverdb.get_microarray_types()
    idTypes = geneweaverdb.get_gene_id_types()
    #SRP IMPLEMENTATION
    srp = geneweaverdb.get_srp(gs_id)
    #SRP IMPLEMENTATION END

    # get unmapped gene ids (this is only an approximation and will not work
    # for probe sets
    genesnotfound = uploadfiles.get_unmapped_ids(gs_id, geneset, geneset.sp_id, geneset.gene_id_type)

    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
        if view is None and curation_view and geneweaverdb.user_is_assigned_curation(user_id, gs_id):
            view = 'True'

    else:
        view = None

    if not geneset:
        return render_template('editgenesetsgenes.html', geneset=geneset,
                               user_id=user_id)

    if geneset.status == 'deleted':
        return render_template('editgenesetsgenes.html', geneset=geneset,
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
        contents = [s.split('\t')[0] for s in contents.split('\n')]
        gene_refs = geneweaverdb.resolve_feature_ids(geneset.sp_id, contents)
        symbol2ode = {}

        for d in gene_refs:
            symbol2ode[d['ode_ref_id']] = d['ode_gene_id']
            ## Reverse to make our lives easier during templating
            symbol2ode[d['ode_gene_id']] = d['ode_ref_id']
        #keys = [list(query) for query in symbol2ode.keys()]
        #symbol2ode = dict([(k[0], symbol2ode[tuple(k)][0]) for k in keys])
        #for sym, ode in symbol2ode.items():
        #    symbol2ode[ode] = sym

    else:
        symbol2ode = None

    return render_template(
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
        curation_view=curation_view,
        genesnotfound=genesnotfound,
        # SRP IMPLEMENTATION
        srp=srp
        # SRP IMPLEMENTATION END
    )


@app.route('/removegenesetsfromproject/<gs_id>')
def render_remove_genesets(gs_id):
    user_id = session['user_id'] if 'user_id' in session else 0
    gs_and_proj = None
    if user_id is not 0:
        gs_and_proj = geneweaverdb.get_selected_genesets_by_projects(gs_id)
    return render_template('removegenesets.html', user_id=user_id, gs_and_proj=gs_and_proj)


@app.route('/setthreshold/<int:gs_id>')
def render_set_threshold(gs_id):
    d3BarChart = []
    user_id = session['user_id'] if 'user_id' in session else 0
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
            k_first_value = list(k.values())[0]
            valArray.append(float(k_first_value))
            maxVal = float(k_first_value) if float(k_first_value) > maxVal else maxVal
            minVal = float(k_first_value) if float(k_first_value) < minVal else minVal
            d3BarChart.append(
                {'x': i, 'y': float(k_first_value), 'gsid': str(list(k.values())[1]), 'abr': str(k_first_value)})
            i += 1
    json.dumps(d3BarChart, default=decimal_default)
    return render_template('viewThreshold.html', geneset=geneset,
                           user_id=user_id, view=view, is_bimodal=is_bimodal,
                           d3BarChart=d3BarChart, threshold=thresh,
                           minVal=minVal, maxVal=maxVal, valArray=valArray)


@app.route('/saveThresholdValues', methods=['GET'])
def save_threshold_values():
    if 'user_id' in session:
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
    if 'user_id' in session:
        user_id = request.args['user_id']
        gs_id = request.args['gs_id']
        if geneweaverdb.get_user(user_id).is_admin != 'False' or geneweaverdb.get_user(user_id).is_curator != 'False' \
                or geneweaverdb.user_is_owner(user_id, gs_id) != 0:
            results = uploadfiles.insert_into_geneset_value_by_gsid(gs_id)
            return json.dumps(results)


@app.route('/updateProjectGroups', methods=['GET'])
def update_project_groups():
    if 'user_id' in session:
        user_id = request.args['user_id']
        proj_id = request.args['proj_id']

        if json.loads(request.args['groups']) != '':
            groups = (json.loads(request.args['groups']))
        else:
            groups = '-1'

        ## Prevent the user from sharing a project containing a private gene
        ## set that has been shared with them
        genesets = geneweaverdb.get_genesets_for_project(proj_id, user_id)
        genesets = [g for g in genesets if g.cur_id == 5]

        for gs in genesets:
            if not geneweaverdb.user_is_owner(user_id, gs.geneset_id):
                return jsonify(
                    success=False,
                    message=('You cannot share a private, Tier V GeneSet that '
                             'you do not own. Please remove the GeneSet from '
                             'this project before sharing it with others.')
                )

        if geneweaverdb.get_user(user_id).is_admin != 'False' or \
                geneweaverdb.user_is_project_owner(user_id, proj_id):
            results = geneweaverdb.update_project_groups(proj_id, groups, user_id)
            return jsonify(success=True, results=results)


@app.route('/shareGenesetsWithGroups')
def update_genesets_groups():
    """ Function to share a collection of genesets with a collection of groups.

    Args:
        request.args['gs_ids']: The genesets that will be added to projects
        request.args['options']: The groups to which genesets will be added

    Returns:
        JSON Dict: {'error': 'None'} for successs, {'error': 'Error Message'} for error

    """
    if 'user_id' in session:
        user_id = session['user_id']
        gs_ids = request.args.get('gs_id', type=str, default='').split(',')
        groups = json.loads(request.args.get('option', type=str))
        errors = set()

        for product in itertools.product(gs_ids, groups):

            ## Prevent the user from sharing private, Tier 5 gene sets that
            ## do not belong to them but they have access to (b/c those sets 
            ## have been shared with them)
            if geneweaverdb.get_geneset_tier(product[0]) == 5 and\
               not geneweaverdb.user_is_owner(user_id, product[0]):
                errors.add(product[0])
                continue

            try:
                geneweaverdb.add_geneset_group(product[0].strip(), product[1])
            except ValueError:
                pass
            except TypeError:
                pass

        if not errors:
            return json.dumps({'error': 'None'})

        else:
            errors = ', '.join(['GS' + s for s in errors])

            return json.dumps({
                'error': ('The GeneSet(s) %s are private (Tier V) and can '
                          'only be shared by their owners.' % errors)
            })
    else:
        return json.dumps({'error': 'You must be logged in to share a geneset with a group'})


@app.route('/updateStaredProject', methods=['GET'])
def update_star_project():
    if int(session['user_id']) == int(request.args['user_id']):
        proj_id = request.args['proj_id']
        user_id = request.args['user_id']
        if geneweaverdb.get_user(user_id).is_admin != 'False' or geneweaverdb.user_is_project_owner(user_id, proj_id):
            results = geneweaverdb.update_stared_project(proj_id, user_id)
            return json.dumps(results)


@app.route('/removeUsersFromGroup', methods=['GET'])
@login_required(json=True)
def remove_users_from_group():
    user_id = request.args['user_id']
    user_emails = request.args['user_emails']
    grp_id = request.args['grp_id']
    results = geneweaverdb.remove_selected_users_from_group(user_id, user_emails, grp_id)
    return json.dumps(results)


@app.route('/updateGroupAdmins', methods=['GET'])
@login_required(json=True)
def update_group_admins():
    user_id = request.args['user_id']
    users = [int(u) for u in request.args.getlist('uids')]
    grp_id = request.args['grp_id']

    results = geneweaverdb.update_group_admins(user_id, users, grp_id)
    return json.dumps(results)


@app.route('/deleteProjectByID', methods=['GET'])
@login_required(json=True, allow_guests=True)
def delete_projects():
    results = geneweaverdb.delete_project_by_id(request.args['projids'])
    return json.dumps(results)


@app.route('/addProjectByName', methods=['GET'])
@create_guest
def add_projects():
    results = geneweaverdb.add_project_by_name(request.args['name'], request.args['comment'])
    return json.dumps(results)


@app.route('/get_project_groups_by_user_id')
@login_required(json=True, allow_guests=True)
def get_project_groups_by_user_id():
    results = geneweaverdb.get_project_groups()
    return json.dumps(results)


@app.route('/changeProjectNameById', methods=['GET'])
@login_required(json=True, allow_guests=True)
def rename_project():
    results = geneweaverdb.change_project_by_id(request.args)
    return json.dumps(results)


@app.route('/addPublicGroupsToUser')
@login_required()
def add_public_groups_to_user():
    user = flask.g.user
    group_ids = json.loads(request.args['projects'])
    try:
        result = geneweaverdb.add_user_to_public_groups(group_ids, user.user_id)
    except geneweaverdb.Error:
        result = {'error': True}
    return json.dumps(result)


@app.route('/accountsettings')
@login_required()
def render_accountsettings():
    user = flask.g.user
    user_id = user.user_id
    groupsMemberOf = geneweaverdb.get_all_member_groups(user_id)
    groupsOwnerOf = geneweaverdb.get_all_owned_groups(user_id)
    groupsEmail = geneweaverdb.get_all_members_of_group(user_id)
    public_groups = geneweaverdb.get_other_visible_groups(user_id)

    groupAdmins = {}
    for group in groupsOwnerOf:
        groupAdmins[group['grp_id']] = geneweaverdb.get_group_admins(group['grp_id'])

    prefs = json.loads(user.prefs)
    email_pref = prefs.get('email_notification', 0)
    annotation_pref = prefs.get('annotator', 'monarch')

    return render_template('accountsettings.html', user=user,
                           groupsMemberOf=groupsMemberOf,
                           groupsOwnerOf=groupsOwnerOf,
                           groupsEmail=groupsEmail,
                           groupAdmins=groupAdmins,
                           emailNotifications=email_pref,
                           groups=public_groups,
                           annotation_pref=annotation_pref)


@app.route('/update_notification_pref.json', methods=['GET'])
@login_required()
@restrict_to_current_user
def update_notification_pref():
    user_id = int(request.args['user_id'])
    state = int(request.args['new_state'])
    result = geneweaverdb.update_notification_pref(user_id, state)
    response = jsonify(**result)
    if 'error' in result:
        response.status_code = 500

    return response


@app.route('/set_annotator.json')
@login_required(json=True)
@restrict_to_current_user
def set_annotator():
    user_id = int(request.args['user_id'])
    result = geneweaverdb.update_annotation_pref(user_id, request.args['annotator'])
    response = jsonify(**result)
    if 'error' in result:
        response.status_code = 500

    return response

@app.route('/login')
def render_login():
    return render_template('login.html')


@app.route('/login_error')
def render_login_error():
    return render_template('login.html', error="Invalid Credentials")


@app.route('/resetpassword.html')
def render_forgotpass():
    return render_template('resetpassword.html')


@app.route('/downloadResult', methods=['POST'])
def download_result():
    """
    Used when a user requests to download a hi-res result image. The SVG data
    is posted to the server, upscaled, converted to a PNG or other image format, 
    and sent back to the user.

    args
        request.form['svg']:        String containing the SVG XML that will be
                                    converted into another image format
        request.form['filetype']:   The filetype extension (e.g. PNG, PDF) for
                                    the final image
        request.form['version']:    A filepath to a classic (GW1) version of
                                    the visualization. Only set when the user
                                    requests the classic version otherwise this
                                    is always null. Currently only used for the
                                    HiSim graph tool.

    returns
        the rendered image as a Base64 encoded blob
    """

    form = request.form
    filetype = form['filetype'].lower().strip()
    runhash = form['runhash'].strip()
    svg = StringIO(form['svg'].strip())
    results = config.get('application', 'results')
    imgstream = StringIO()
    dpi = 400 if filetype != 'svg' else 25

    ## Some tools like HiSim graph write their own SVG file out to the results
    ## and we don't want to overwrite this so we add the -s postfix to the
    ## runhash.
    if filetype == 'svg':
        runhash = '%s-s' % runhash

    img_file = '%s.%s' % (runhash, filetype)
    img_abs = os.path.join(results, img_file)
    img_rel = os.path.join('results', img_file)

    if filetype == 'svg':
        with open(img_abs, 'w') as fl:
            print(svg.getvalue(), file=fl)

            return img_rel

    ## The user wants the classic HiSim image
    elif 'version' in form and form['version']:
        classicpath = os.path.join(results, form['version'])
        ## For some reason the DPI for this image needs to be low otherwise it
        ## takes forever to render (and may cause ImageMagick to crash). It's 
        ## also very clear even at low DPI.
        img = Image(filename=classicpath, format='svg', resolution=150)

    else:
        img = Image(file=svg, format='svg', resolution=dpi)

    img.format = filetype
    img.save(filename=img_abs)
    img.close()

    return img_rel


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
        return url_for(
            jaccardsimilarityblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'HiSim Graph':
        return url_for(
            phenomemapblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'GeneSet Graph':
        return url_for(
            genesetviewerblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'Clustering':
        return url_for(
            jaccardclusteringblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'Boolean Algebra':
        return url_for(
            booleanalgebrablueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'MSET':
        return url_for(
            msetblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    elif results['res_tool'] == 'UpSet':
        # TODO: Not sure that this upsetblueprint
        return url_for(
            upsetblueprint.TOOL_CLASSNAME + '.view_result',
            task_id=runhash
        )

    else:
        ## Something bad has happened
        return ''


@app.route('/reruntool.json', methods=['POST', 'GET'])
def rerun_tool():
    args = request.args
    results = geneweaverdb.get_results_by_runhash(args['runHash'])
    data = json.loads(results['res_data'])
    tool = results['res_tool']

    try:
        params = data['parameters']
    except KeyError:
        params = {}

    ## inconsistent naming conventions
    if data.get('gs_ids', None) and data['gs_ids']:
        gs_ids = data['gs_ids']
    elif data.get('genesets', None) and data['genesets']:
        gs_ids = data['genesets']
    elif params.get('gs_dict'):
        gs_ids = [params['gs_dict']['group_1_gsid'], params['gs_dict']['group_2_gsid']]
    else:
        gs_ids = []

    return json.dumps({'tool': tool, 'parameters': params, 'gs_ids': gs_ids})


@app.route('/createtempgeneset_original', methods=["POST"])
@login_required(json=True)
def create_geneset_meta():
    if int(request.form['sp_id']) == 0:
        return json.dumps({'error': 'You must select a species.'})
    if str(request.form['gdb_id']) == '0':
        return json.dumps({'error': 'You must select an identifier.'})
    results = uploadfiles.create_new_geneset(request.form)
    return json.dumps(results)


@app.route('/createtempgeneset_large', methods=["POST"])
@login_required(json=True)
def create_large_geneset():
    user = flask.g.user
    if int(request.form['sp_id']) == 0:
        return json.dumps({'error': 'You must select a species.'})
    if str(request.form['gdb_id']) == '0':
        return json.dumps({'error': 'You must select an identifier.'})
    results = uploadfiles.create_new_large_geneset_for_user(request.form, user.user_id)
    return json.dumps(results)


@app.route('/transposeGenesetIDs', methods=["POST"])
@login_required(json=True)
def transposeGSIDs():
    results = geneweaverdb.transpose_genes_by_species(request.form)
    return json.dumps(results)


@app.route('/viewgenesetdetails/<int:gs_id>', methods=['GET', 'POST'])
@create_guest
@login_required(allow_guests=True)
def render_viewgeneset(gs_id):
    assignment = curation_assignments.get_geneset_curation_assignment(gs_id)
    return render_viewgeneset_main(gs_id, curation_assignment=assignment)


@app.route('/curategeneset/<int:gs_id>', methods=['GET', 'POST'])
@login_required()
def render_curategeneset(gs_id):
    assignment = curation_assignments.get_geneset_curation_assignment(gs_id)
    curation_view = None
    curation_team_members = None
    curator_info = None
    user = flask.g.user

    def user_is_curation_leader():
        owned_groups = geneweaverdb.get_all_owned_groups(session['user_id'])
        if assignment.group in [x['grp_id'] for x in owned_groups]:
            return True

    if assignment:
        if request.args.get('reset_assignment_state') and (user.is_curator or user.is_admin):
            assignment.assign_curator(assignment.curator, user.user_id)
            assignment.set_curation_state('Ready for review')
            curation_view = 'reviewer'

        #figure out the proper view depending on the state and your role(s)
        if assignment.state == curation_assignments.CurationAssignment.UNASSIGNED and user_is_curation_leader():
            curation_view = 'curation_leader'
        elif assignment.state == curation_assignments.CurationAssignment.ASSIGNED:
            if session['user_id'] == assignment.curator:
                curation_view = 'curator'
            elif user_is_curation_leader():
                curation_view = 'curation_leader'
        elif (assignment.state == curation_assignments.CurationAssignment.READY_FOR_REVIEW or
                      assignment.state == curation_assignments.CurationAssignment.REVIEWED):
            if session['user_id'] == assignment.reviewer:
                curation_view = 'reviewer'
            elif session['user_id'] == assignment.curator:
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

@app.route('/get_geneset_values', methods=['GET'])
def get_geneset_genes():
    #return the list of genes associated with a geneset in json format
    #this endpoint wil only get hit from a logged in page (viewgenesetdetails)
    if 'user_id' in session:
        user_id = session['user_id']

    args = request.args
    gs_id = args['gs_id']
    total_records = int(args['gs_len'])

    if 'order[0][column]' in args:
        orderBy = int(args['order[0][column]'])
        columns = ['symbol', 'alt', '', 'value', 'priority']
        session['sort'] = columns[orderBy]
        session['dir'] = args['order[0][dir]']
    else:
        session['sort'] = ''
        session['dir'] = 'ASC'

    if 'length' in args:
        session['length'] = args['length']
    else:
        session['length'] = 50

    if 'start' in args:
        start = args['start']
        session['start'] = start
    else:
        session['start'] = 0

    if 'search[value]' in args:
        session['search'] = args['search[value]']
    else:
        session['search'] = ''

    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    #gsvs = geneset.geneset_values
    # not sure why you have to give datatables both of these as the same value, but that's what it wants...
    gene_list = {'aaData': [], 'iTotalDisplayRecords': total_records, 'iTotalRecords': total_records}

    emphgenes = {}
    emphgeneids = []

    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(row['ode_gene_id'])

    ## Force linkouts to use gene symbols rather than whatever identifier is
    ## currently present on the page. First get the gene type list.
    genetypes = geneweaverdb.get_gene_id_types()
    genedict = {}

    for gtype in genetypes:
        genedict[gtype['gdb_name']] = gtype['gdb_id']

    ## The get_geneset_values function requires a session variable (should be
    ## be updated so this is no longer necessary)
    if 'extsrc' not in session:
        alt_gene_id = genedict['Gene Symbol']
    else:
        alt_gene_id = session['extsrc']

    session['extsrc'] = genedict['Gene Symbol']

    gsvs = geneweaverdb.get_geneset_values(
        gs_id, 
        alt_gene_id,
        session['length'], 
        session['start'], 
        session['search'], 
        session['sort'],
        session['dir']
    )

    ## Retrieves the set with symbol identifiers
    gs = geneweaverdb.get_geneset(gs_id, user_id)
    symbols = []
    session['extsrc'] = alt_gene_id

    for gsv in gs.geneset_values:
        symbols.append(gsv.ode_ref)

    print(gsvs)
    #map each GenesetValue object's contents back onto a dictionary, turn geneset value (decimal) into string
    for i in range(len(gsvs)):
        gene_id = gsvs[i].ode_gene_id
        gene = []
        #gene id
        gene.append(gene_id)
        #gene name (default symbol)
        gene.append(str(gsvs[i].source_list[0]))
        #gene symbol
        gene.append(str(gsvs[i].ode_ref))
        #homology
        gene.append(sorted(gsvs[i].hom))
        #score
        gene.append(str(round(gsvs[i].value, 3)))
        #priority
        gene.append((float(gsvs[i].gene_rank) / 0.15) * 100)
        #blank column for linkouts - handled in DOM on page
        gene.append('Null')
        #emphasis on/off flag.
        if gene_id in emphgeneids:
            gene.append('On')
        else:
            gene.append('Off')
        #'add genes to geneset' checkbox - handled in DOM on page
        gene.append('Null')
        ## Add the symbol to the list for the linkouts
        if i < len(symbols):
            gene.append(symbols[i])
        else:
            gene.append(str(gsvs[i].ode_ref))

        gene_list['aaData'].append(gene)

    return jsonify(gene_list)

def render_viewgeneset_main(gs_id, curation_view=None, curation_team=None, curation_assignment=None, curator_info=None):
    # get values for sorting result columns and saving these to a session variable
    if request.method == 'GET':
        args = request.args
        if 'sort' in args:
            session['sort'] = args['sort']
            if 'dir' in session:
                if session['dir'] != 'DESC':
                    session['dir'] = 'DESC'
                else:
                    session['dir'] = 'ASC'
            else:
                session['dir'] = 'ASC'

    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0

    numgenes = geneweaverdb.get_genecount_in_geneset(gs_id)
    user_info = flask.g.user
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    # SRP IMPLEMENTATION
    srp = geneweaverdb.get_srp(gs_id)
    #SRP IMPLEMENTATIOn END

    # can the user see this geneset?
    ## User account
    if user_info:
        if not user_info.is_admin and not user_info.is_curator:
            ## get_geneset takes into account permissions, if a geneset is
            ## returned by *_no_user then we know they can't view it b/c of
            ## access rights
            if not geneset and geneweaverdb.get_geneset_no_user(gs_id):
                return render_template(
                    'viewgenesetdetails.html',
                    no_access=True,
                    user_id=user_id
                )

    ## Guest account attempting to view geneset without proper access
    if not geneset:
        return render_template(
            'viewgenesetdetails.html',
            no_access=True,
            user_id=user_id
        )


    genetypes = geneweaverdb.get_gene_id_types(geneset.sp_id)
    genedict = {}

    for gtype in genetypes:
        genedict[gtype['gdb_id']] = gtype['gdb_name']
        genedict[gtype['gdb_name']] = gtype['gdb_id']

    uploaded_as = 'Gene Symbol'
    gene_type = abs(geneset.gene_id_type)

    ## Get the original identifier type used during the upload of this gene
    ## set. Normal identifiers are negative, expression platforms are positive.
    if geneset.gene_id_type < 0:
        uploaded_as = genedict[gene_type]
    else:
        for plat in geneweaverdb.get_microarray_types():
            if plat['pf_id'] == gene_type:
                uploaded_as = plat['pf_name']

    show_gene_list = True
    # get value for the alt-gene-id column
    # if this is a 'stub' geneset.gene_id_type might not be valid,
    # if it is a stub and doens't have any genes yet, don't try to display a
    # gene list
    if not curation_view or len(geneset.geneset_values):
        if 'extsrc' in session:
            if genedict.get(session['extsrc'], None):
                altGeneSymbol = genedict[session['extsrc']]
                alt_gdb_id = session['extsrc']
            else:
                ## The genedict will not have references for expression 
                ## platforms so if the gene_id_type is missing, it's 
                ## probably a platform and we should handle it by setting
                ## the default display to gene symbol
                if geneset.gene_id_type not in genedict:
                    alt_gdb_id = genedict['Gene Symbol']
                    altGeneSymbol = genedict[alt_gdb_id]

                else:
                    altGeneSymbol = genedict[abs(geneset.gene_id_type)]
                    alt_gdb_id = abs(geneset.gene_id_type)
        else:
            if geneset.gene_id_type not in genedict:
                alt_gdb_id = genedict['Gene Symbol']
                altGeneSymbol = genedict[alt_gdb_id]

            else:
                altGeneSymbol = genedict[abs(geneset.gene_id_type)]
                alt_gdb_id = abs(geneset.gene_id_type)
    else:
        altGeneSymbol = None
        alt_gdb_id = None
        show_gene_list = False

    ## Nothing is ever deleted but that doesn't mean users should be able
    ## to see them. Some sets have a NULL status so that MUST be
    ## checked for, otherwise sad times ahead :(
    ## allow admins, curators, and gene set owners to view deleted sets 
    ## (like in classic GW)
    if (not user_info.is_admin and not user_info.is_curator and user_id != geneset.user_id) and\
       (not geneset or (geneset and geneset.status == 'deleted')):
        return render_template(
            'viewgenesetdetails.html',
            geneset=None,
            deleted=True,
            user_id=user_id
        )

    if user_id != 0:
        view = 'True' if user_info.is_admin or user_info.is_curator or geneset.user_id == user_id else None
    else:
        view = None

    ## Ontologies associated with this geneset
    ontology = get_ontology_terms(gs_id)

    #print ontology

    ## Ontology linkout mapping, ontdb_id -> url
    ontdb = geneweaverdb.get_all_ontologydb()

    ont_links = {}

    for odb in ontdb:
        #just in case the linkout_url is empty. if it is it breaks the template, so avoid
        if odb.linkout_url is not None:
            ont_links[odb.ontologydb_id] = odb.linkout_url

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    return render_template(
        'viewgenesetdetails.html',
        gs_id=gs_id,
        geneset=geneset,
        user_id=user_id,
        colors=HOMOLOGY_BOX_COLORS,
        tt=SPECIES_NAMES,
        altGeneSymbol=altGeneSymbol,
        view=view,
        ontology=ontology,
        ont_links=ont_links,
        alt_gdb_id=alt_gdb_id,
        species=species,
        curation_view=curation_view,
        curation_team=curation_team,
        curation_assignment=curation_assignment,
        curator_info=curator_info,
        show_gene_list=show_gene_list,
        totalGenes=numgenes,
        uploaded_as=uploaded_as,
        #SRP IMPLEMENTATION
        srp=srp
        #SRP IMPLEMENTATION END
    )

@app.route('/viewgenesetoverlap/<list:gs_ids>', methods=['GET'])
@login_required(allow_guests=True)
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

        return render_template(
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
    ## Homology is only used if sets from multiple species are present
    sp_ids = list(set([g.sp_id for g in genesets]))

    if len(sp_ids) > 1:
        use_homology = True
    else:
        use_homology = False

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

            if use_homology:
                intersect = geneweaverdb.get_intersect_by_homology(gs_id1, gs_id2)
            else:
                intersect = geneweaverdb.get_geneset_intersect(gs_id1, gs_id2)

            gs_intersects[gs_id1][gs_id2] = intersect
            gs_intersects[gs_id2][gs_id1] = intersect

            ## Keep track of gene-genesets for sorting and ease of display
            for i in intersect:
                gene_intersects[i['gi_symbol']].add(gs_id1)
                gene_intersects[i['gi_symbol']].add(gs_id2)

    intersects = []

    ## Generate a single structure containing all the intersection information
    ## for the template
    for gene, gs_ids in gene_intersects.items():
        ## If the intersection is among >1 species, it's a homologous gene
        ## cluster
        species = list(set([gs_map[i].sp_id for i in gs_ids]))

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
        if user_info.is_admin or \
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

        c1y += 30
        c2y += 30

        return {'c1x':c1x,'c1y':c1y,'r1':r1, 'c2x':c2x,'c2y':c2y,'r2':r2, 'tx': tx, 'ty': ty}


    ## TODO: fix emphasis genes
    # emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)

    # for row in emphgenes:
    #    emphgeneids.append(str(row['ode_gene_id']))

    ## variables to hole if a geneset has an emphasis gene
    # inGeneset1 = False
    # inGeneset2 = False

    ## Check to see if an emphasis gene is in one of the genesets
    # for gene in emphgeneids:
    #    inGeneset1 = geneweaverdb.check_emphasis(gs_id, gene)
    #    if inGeneset1 == True:
    #        break

    # for gene in emphgeneids:
    #    inGeneset2 = geneweaverdb.check_emphasis(gs_id1, gene)
    #    if inGeneset2 == True:
    #        break

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    ## Pairwise comparison so we provide additional data for the venn diagram
    if len(genesets) == 2:
        gslen1 = len(list(
            geneweaverdb.get_geneset_values_simple(genesets[0].geneset_id)
        ))
        gslen2 = len(list(
            geneweaverdb.get_geneset_values_simple(genesets[1].geneset_id)
        ))
        venn = venn_circles(
            gslen1, 
            gslen2, 
            len(intersects), 
            200
        )
        venn_text = {'tx': venn['tx'], 'ty': venn['ty']}
        venn = [{'cx': venn['c1x'], 'cy': venn['c1y'], 'r': venn['r1']},
                {'cx': venn['c2x'], 'cy': venn['c2y'], 'r': venn['r2']}]

        left_count = gslen1 - len(intersects)
        right_count = gslen2 - len(intersects)

        venn_text['text'] = '(%s (%s) %s)' % (left_count, len(intersects), right_count)

    else:
        venn = None
        venn_text = None

    #emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)

    return render_template('viewgenesetoverlap.html',
                           gs_map=gs_map,
                           intersects=intersects,
                           species=species,
                           venn=json.dumps(venn),
                           venn_text=json.dumps(venn_text))


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
@login_required()
def render_user_genesets():
    table = 'production.geneset'
    my_groups = []
    other_groups = []
    if 'user_id' in session:
        user_id = session['user_id']
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

    return render_template(
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
    group_owner = False
    group_curators = []
    groups_member = []
    groups_owner = []
    user = flask.g.user if 'user_id' in session else None
    if user and not user.is_guest:
        user_id = session['user_id']
        columns = [
            {'name': 'full_name'},
            {'name': 'task_id'},
            {'name': 'task'},
            {'name': 'task_type'},
            {'name': 'updated'},
            {'name': 'task_status'},
            {'name': 'reviewer'},
            {'name': 'pubmedid'},
            {'name': 'geneset_count'}
        ]
        headerCols = ["Assignee Name",
                      "Task ID",
                      "Task",
                      "Task Type",
                      "Updated",
                      "Status",
                      "Reviewer",
                      "Pub Assignment",
                      "# GeneSets"]

        groups_member = geneweaverdb.get_all_member_groups(user_id)
        groups_owner  = geneweaverdb.get_all_owned_groups(user_id)

        if not group_id:
            if len(groups_owner) > 0:
                group_id = groups_owner[0]['grp_id']
            elif len(groups_member) > 0:
                group_id = groups_member[0]['grp_id']
            else:
                public_groups = geneweaverdb.get_other_visible_groups(user_id)
                response = render_template('joinOrCreateGroups.html', groups=public_groups)
                return response

        group = geneweaverdb.get_group_by_id(group_id)
        group_curators = geneweaverdb.get_group_members(group_id)

        try:
            if group_id_in_groups(group.grp_id, groups_owner):
                group_owner = True
        except TypeError as error:
            print("TypeError while trying to match group id: {0}".format(error))
    else:
        headerCols, user_id, columns = [], 0, None

    return render_template(
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
        if 'grp_id' not in group:
            raise TypeError("geneweaverdb.Groups instance has no grp_id value.  Possibly invalid type...")
        if group['grp_id'] == id:
            included = True
    return included


def jaccard(a, b):
    """
    stupid easy jaccard with no pair-wise deletion
    but maybe not needed because mapping to hom_id?
    This is something that we need to verify.
    :param a: gs_id of geneset that is the seed of the search
    :param b: gs_id of geneset for comparison
    :return: non-normalized jaccard
    """
    # TODO: This can be improved in better way.
    if a == 0:
        a = []
    if b == 0:
        b = []
    c = list(set(a).intersection(b))
    return float(len(c)) / (len(a) + len(b) - len(c))


def calculate_jaccard(gs_id, genesets):
    """
    get hom ids from gs_id and each geneset.
    :param gs_id: gs_id of geneset that is the seed of the search
    :param genesets: list of gs_ids that contain hom_ids from a
    :return: a dictionary of gs_id => jaccard value
    """
    jaccards = {}
    gs1 = geneweaverdb.get_geneset_hom_ids(gs_id)
    for g in genesets:
        gs2 = geneweaverdb.get_geneset_hom_ids(g)
        jaccards[g] = jaccard(gs1, gs2)
    return jaccards


def dynamic_jaccard(gs_id):
    """
    This function takes a gs_id and maps it against the hom2geneset table to dynamically create and
    add rows to the geneset_jaccard table
    :param gs_id:
    :return: 1 if True
    """
    hom_ids = geneweaverdb.get_geneset_hom_ids(gs_id)
    if hom_ids == 0:
        return 0
    else:
        genesets = geneweaverdb.get_genesets_by_hom_id(hom_ids)
        results = calculate_jaccard(gs_id, genesets)
        if geneweaverdb.insert_into_geneset_jaccard(results, gs_id):
            return 1


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
    if isinstance(obj, bytes):
        return obj.decode('utf-8')
    if isinstance(obj, Decimal):
        return float(obj)
    raise TypeError


@app.route('/viewSimilarGenesets/<int:gs_id>/<int:grp_by>')
@login_required(allow_guests=True)
def render_sim_genesets(gs_id, grp_by):
    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0
    # Call function to dynamically calculate jaccard values -- added to the geneset_value table
    if dynamic_jaccard(gs_id) == 0:
        sim_status = 0
    else:
        sim_status = 1
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
        d3BarChart.append(
            {'x': i, 'y': float(k.jac_value), 'gsid': int(k.geneset_id), 'abr': k.abbreviation})
        i += 1
    d3Data.extend([tier1, tier2, tier3, tier4, tier5])
    json.dumps(d3Data, default=decimal_default)
    json.dumps(d3BarChart, default=decimal_default)

    ## sp_id -> sp_name map so species tags can be dynamically generated
    species = []

    for sp_id, sp_name in geneweaverdb.get_all_species().items():
        species.append([sp_id, sp_name])

    # #################################################################################
    # This is deprecated. The dynamic jaccard does not make use of this information
    # We will pass the sim_status to the template to indicate if there are results
    #
    # Checks to see if the jaccard cache has been built for this set, if not
    # allows the user to calculate jaccard coefficients for the gene set
    # set_info = geneweaverdb.get_geneset_info(gs_id)
    # sim_status = 0
    #
    # The cache has never been built
    # if set_info and not set_info.jac_started:
    #     sim_status = 1
    #
    # The cache is currently building
    # elif set_info and set_info.jac_started and not set_info.jac_completed:
    #     sim_status = 2

    return render_template(
        'similargenesets.html',
        geneset=geneset,
        user_id=user_id,
        gs_id=gs_id,
        simgs=simgs,
        d3Data=d3Data,
        max=max,
        d3BarChart=d3BarChart,
        sim_status=sim_status,
        species=species
    )


@app.route('/getPubmed', methods=['GET', 'POST'])
def get_pubmed_data():
    """
    """

    from pubmedsvc import get_pubmed_info

    pubmedValues = []

    if request.method == 'GET':
        args = request.args

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


@app.route('/exportGeneList/<int:gs_id>')
def render_export_genelist(gs_id):
    if 'user_id' in session:
        str = ''
        results = geneweaverdb.export_results_by_gs_id(gs_id)
        for k in results:
            str = str + k + ',' + results[k] + '\n'
        response = make_response(str)
        response.headers["Content-Disposition"] = "attachment; filename=geneset_export.csv"
        return response


@app.route('/exportBatch/<int:gs_id>')
def render_export_batch(gs_id):
    """
    This will use functions developed as part of the batch-download script to populate a batch file associated with
    a geneset
    :param gs_id: 
    :return: an extended batch string
    """
    title = 'gene_export_geneset_' + str(gs_id) + '_' + str(datetime.date.today()) + '.gw'
    if 'user_id' in session:
        import export_batch
        metadata = export_batch.metadata_batch(geneweaverdb.PooledCursor(), gs_id)
        ontologydata = export_batch.ontology_batch(geneweaverdb.PooledCursor(), gs_id)
        geneinfo = export_batch.geneinfo_batch(geneweaverdb.PooledCursor(), gs_id)
        # build string
        s = metadata + ontologydata + '\n' + geneinfo
    else:
        s = '## You must be logged in to generate a gene set report ##'
    response = make_response(s)
    response.headers["Content-Disposition"] = "attachment; filename=" + title
    response.headers["Cache-Control"] = "must-revalidate"
    response.headers["Pragma"] = "must-revalidate"
    response.headers["Content-type"] = "text/plain"
    return response


@app.route('/exportgsid/<string:gs_id>')
def render_export_genes(gs_id):
    title = 'gene_export_geneset_' + str(gs_id) + '_' + str(datetime.date.today()) + '.txt'
    if 'user_id' in session:
        export_list = geneweaverdb.get_all_gene_ids(gs_id)
        gdb_names = geneweaverdb.get_gdb_names()
        # create a tab-delimated string to write directly to the download file
        export_string = '\t'.join(gdb_names)
        export_string = 'GeneWeaver ID\t' + export_string + '\n'
        for key, value in export_list.items():
            export_string = export_string + str(key) + '\t'
            for g in gdb_names:
                for k, v in value.items():
                    if g == k:
                        export_string = export_string + str(v) + '\t'
            export_string = export_string + '\n'
    else:
        export_string = '## You must be logged in to generate a gene set report ##'
    response = make_response(export_string)
    response.headers["Content-Disposition"] = "attachment; filename=" + title
    response.headers["Cache-Control"] = "must-revalidate"
    response.headers["Pragma"] = "must-revalidate"
    response.headers["Content-type"] = "text/plain"
    return response


@app.route('/exportOmicsSoft/<string:gs_ids>')
def render_export_omicssoft(gs_ids):
    if 'user_id' in session:
        gs_ids_list = gs_ids.split(',')
        string = ''
        for gs_id in gs_ids_list:
            results = geneweaverdb.get_geneset(gs_id, session['user_id'])
            gsv_values = geneweaverdb.export_results_by_gs_id(gs_id)
            omicssoft = geneweaverdb.get_omicssoft(gs_id)
            print(omicssoft)
            title = 'gw_omicssoft_' + str(gs_id) + '_' + str(datetime.date.today()) + '.txt'
            string += '[GeneSet]\n'
            if results is not None:
                string += '##Source=GeneWeaver Generated\n'
                string += '##Type=' + str(omicssoft['type']) + '\n'
                string += '##Project=' + str(omicssoft['project']) + '\n'
                string += '##Name=' + str(results.name) + '\n'
                string += '##Description=' + str(results.description) + '\n'
                string += '##Tag=' + str(omicssoft['tag']) + '\n'
                for gene, value in gsv_values.items():
                    string += str(gene) + '\t' + str(value) + '\n'
                string += '\n'
            else:
                string = '## An Error Occured During File Creation. Please contact GeneWeaver@gmail.com.\n\n'
        response = make_response(string)
        response.headers["Content-Disposition"] = "attachment; filename=" + title
        response.headers["Cache-Control"] = "must-revalidate"
        response.headers["Pragma"] = "must-revalidate"
        response.headers["Content-type"] = "text/plain"
        return response


@app.route('/exportJacGeneList/<int:gs_id>')
def render_export_jac_genelist(gs_id):
    if 'user_id' in session:
        user_id = session['user_id']
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
    if 'user_id' in session:
        user_id = session['user_id']
    else:
        user_id = 0
    results = geneweaverdb.get_similar_genesets_by_publication(gs_id, user_id)
    return render_template('viewsamepublications.html', user_id=user_id, gs_id=gs_id, geneset=results)


@app.route('/emphasis', methods=['GET', 'POST'])
@login_required(allow_guests=True)
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
    user_id = session['user_id']
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))

    if request.method == 'POST':
        form = request.form

        if 'Emphasis_SearchGene' in form:
            search_gene = form['Emphasis_SearchGene']
            foundgenes = geneweaverdb.get_gene_and_species_info(search_gene)

    elif request.method == 'GET':
        args = request.args

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
    return render_template('emphasis.html', emphgenes=emphgenes, foundgenes=foundgenes)


@app.route('/emphasize/<string:add_gene>.html', methods=['GET', 'POST'])
def emphasize(add_gene):
    user_id = session['user_id']
    return str(geneweaverdb.create_usr2gene(user_id, add_gene))


@app.route('/deemphasize/<string:rm_gene>.html', methods=['GET', 'POST'])
def deemphasize(rm_gene):
    user_id = session['user_id']
    return str(geneweaverdb.delete_usr2gene_by_user_and_gene(user_id, rm_gene))


@app.route('/search/')
def render_searchFromHome():
    """
    Executes searches from the home page. Constructs a sphinx query from the
    given user input and returns/renders the search results.

    returns
        a rendered flask template of the search results
    """

    form = request.form
    # Terms from the search bar, as a list since there can be <= 3 terms
    terms = request.args.getlist('searchbar')
    sortby = request.args.get('sortBy')

    # If terms is empty, we can assume a) the user submitted a blank search,
    # or b) the user clicked on the search link. Both are handled the same way
    if not terms or (len(terms) == 1 and not terms[0]):
        return render_template('search.html', paginationValues=None)

    if request.method == 'GET':
        args = request.args
    # pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    raw_pagination_page = request.args.get('pagination_page')
    pagination_page = int(raw_pagination_page) if raw_pagination_page else 1
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
        return render_template('search.html', paginationValues=None)

    if (search_values['STATUS'] == 'NO MATCHES'):
        return render_template('search.html', paginationValues=None,
                                     noResults=True)

    ## Used to dynamically generate species tags
    species = geneweaverdb.get_all_species()
    species = species.items()

    ## Used to generate attribution tags
    attribs = geneweaverdb.get_all_attributions()

    return render_template(
        'search.html',
        searchresults=search_values['searchresults'],
        genesets=search_values['genesets'],
        paginationValues=search_values['paginationValues'],
        field_list=field_list,
        searchFilters=search_values['searchFilters'],
        filterLabels=search_values['filterLabels'],
        sort_ascending='true',
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
        userValues['sort_by'],
        userValues['sort_ascending']
    )

    ## Used to dynamically generate species tags
    species = geneweaverdb.get_all_species()
    species = species.items()

    ## Used to generate attribution tags
    attribs = geneweaverdb.get_all_attributions()

    return render_template(
        'search/search_wrapper_contents.html',
        searchresults=search_values['searchresults'],
        genesets=search_values['genesets'],
        paginationValues=search_values['paginationValues'],
        field_list=userValues['field_list'],
        searchFilters=search_values['searchFilters'],
        userFilters=userValues['userFilters'],
        filterLabels=search_values['filterLabels'],
        sort_by=userValues['sort_by'],
        sort_ascending=userValues['sort_ascending'],
        species=species,
        attribs=attribs)


@app.route('/searchsuggestionterms.json')
def render_search_suggestions():
    return render_template('searchsuggestionterms.json')

@app.route('/projectGenesets.json', methods=['GET'])
def render_project_genesets():
    uid = session.get('user_id')
    pid = request.args['project']
    genesets = geneweaverdb.get_genesets_for_project(pid, uid)

    species = geneweaverdb.get_all_species()
    splist = []

    for sp_id, sp_name in species.items():
        splist.append([sp_id, sp_name])

    species = splist

    return render_template('singleProject.html',
                                 genesets=genesets,
                                 proj={'project_id': pid},
                                 species=species)

@app.route('/get_project_groups_modal', methods=['GET'])
def get_project_groups_modal():
    """
    Renders the shared project groups modal.
    """

    pid = request.args['project']

    return render_template(
        'modal/viewProjectGroups.html',
        proj={'project_id': pid}
    )

@app.route('/get_add_project_group_modal', methods=['GET'])
def get_add_project_group_modal():
    """
    Renders the add project to group modal.
    """

    pid = request.args['project']
    project = geneweaverdb.get_project_by_id(pid)

    return render_template(
        'modal/addProjectToGroup.html',
        proj=project
    )


@app.route('/getProjectGroups.json', methods=['GET'])
def render_project_groups():
    results = geneweaverdb.get_groups_by_project(request.args['proj_id'])
    return json.dumps(results)


@app.route('/changePvalues/<setSize1>/<setSize2>/<jaccard>', methods=["GET"])
def changePvalues(setSize1, setSize2, jaccard):
    tempDict = geneweaverdb.checkJaccardResultExists(setSize1, setSize2)
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
        return render_template('admin/adminForbidden.html')


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
        return render_template('admin/adminForbidden.html')


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
        return render_template('admin/adminForbidden.html')


@app.route('/admin/usertoolstats')
def admin_widget_4():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.user_tool_stats()
        return json.dumps(data)
    else:
        return render_template('admin/adminForbidden.html')


@app.route('/admin/currentlyrunningtools')
def admin_widget_5():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.currently_running_tools()
        # print data
        return json.dumps(data, default=date_handler)
    else:
        return render_template('admin/adminForbidden.html')


@app.route('/admin/sizeofgenesets')
def admin_widget_6():
    if "user" in flask.g and flask.g.user.is_admin:
        data = geneweaverdb.size_of_genesets()
        # print data
        return json.dumps(data)
    else:
        return render_template('admin/adminForbidden.html')


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
        return render_template('admin/adminForbidden.html')


@app.route('/admin/adminEdit')
def admin_edit():
    if "user" in flask.g and flask.g.user.is_admin:
        rargs = request.args
        table = rargs['table']
        return AdminEdit().render("admin/adminEdit.html", columns=rargs, table=table)
    else:
        return render_template('admin/adminForbidden.html')


@app.route('/admin/adminSubmitEdit', methods=['POST'])
def admin_submit_edit():
    if "user" in flask.g and flask.g.user.is_admin:
        form = request.form
        table = form['table']
        prim_keys = geneweaverdb.get_primary_keys(table.split(".")[1])
        keys = []
        for att in prim_keys:
            temp = form[att['attname']]
            keys.append(att['attname'] + "=\'" + temp + "\'")
        status = geneweaverdb.admin_set_edit(form, keys)
        return json.dumps(status)
    else:
        return render_template('admin/adminForbidden.html')


@app.route('/admin/adminDelete', methods=['POST'])
def admin_delete():
    if "user" in flask.g and flask.g.user.is_admin:
        form = request.form
        table = form['table']
        prim_keys = geneweaverdb.get_primary_keys(table.split(".")[1])
        keys = []
        for att in prim_keys:
            temp = form[att['attname']]
            keys.append(att['attname'] + "=\'" + temp + "\'")
        result = geneweaverdb.admin_delete(form, keys)
        return json.dumps(result)
    else:
        return render_template('admin/adminForbidden.html')


@app.route('/admin/adminAdd', methods=['POST'])
def admin_add():
    if "user" in flask.g and flask.g.user.is_admin:
        form = request.form
        table = form.get('table', type=str)
        result = geneweaverdb.admin_add(form)
        return json.dumps(result)
    else:
        return render_template('admin/adminForbidden.html')


# fetches info for admin viewers
@app.route('/admin/serversidedb')
def get_db_data():
    if "user" in flask.g and flask.g.user.is_admin:
        results = geneweaverdb.get_server_side(request.args)
        return json.dumps(results, default=date_handler)
    else:
        return render_template('admin/adminForbidden.html')


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
    return json.dumps(results)

@app.route('/assignmentStatusAsString/<int:status>')
def get_assignment_status_string(status):
    status_text = {'status': curation_assignments.CurationAssignment.status_to_string(status)}
    return jsonify(status_text)


def str_handler(obj):
    return str(obj)


def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj


# ************************************************************************


@app.route('/manage.html')
@login_required()
def render_manage():
    return render_template('mygenesets.html')


# This function should be deprecated
@app.route('/share_projects.html')
def render_share_projects():
    active_tools = geneweaverdb.get_active_tools()
    return render_template('share_projects.html', active_tools=active_tools)

@app.route('/mygroupselect')
@login_required(allow_guests=True)
def my_groups_select():
    """
    An endpoint that renders an htmlfragment select element containing the groups the user is a memeber or admin of.
    :return: (html): htmlfragments/groupselect.html
    """
    user_id = flask.g.user.user_id
    my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)
    return render_template('htmlfragments/groupSelect.html', groups=my_groups)

@app.route('/publicgroupsmultiselect')
@login_required(allow_guests=True)
def public_groups_multiselect():
    """
    An endpoint that renders an htmlfragment multiple select containing the public groups the user is not a member of.
    :return: (html): htmlfragments/groupsMultiselect.html
    """
    public_groups = geneweaverdb.get_other_visible_groups(flask.g.user.user_id)
    return render_template('htmlfragments/groupsMultiselect.html', groups=public_groups)

@app.route('/projectsmultiselect')
@login_required(allow_guests=True)
def get_projects_multiselect():
    """
    An endpoint that renders a htmlfragment multiple select containing all projects a user is a member of.
    :return: (html): htmlfragments/projectsMultiselect.html
    """
    return render_template('htmlfragments/projectsMultiselect.html')

@app.route('/addGenesetsToProjects')
@create_guest
@login_required(json=True, allow_guests=True)
def add_genesets_projects():
    """ Function to add a group of genesets to a group of projects.

    Args:
        request.args['gs_ids']: The genesets that will be added to projects
        request.args['options']: The projects to which genesets will be added
        request.args['npn'] (optional): The name of a new project to be created (if given)

    Returns:
        JSON Dict: {'error': 'None'} for successs, {'error': 'Error Message'} for error

    """
    
    user_id = session['user_id']
    gs_ids = request.args.get('gs_id', type=str, default='').split(',')
    try:
        projects = json.loads(request.args.get('option', type=str))
    except TypeError:
        projects = []
    new_project_name = request.args.get('npn', type=str)

    if not projects:
        projects = []

    if new_project_name:
        new_project_id = geneweaverdb.add_project(user_id, new_project_name)
        projects.append(new_project_id)

    for product in itertools.product(projects, gs_ids):
        geneweaverdb.add_geneset2project(product[0], product[1].strip())

    results = {'error': 'None', 'is_guest': 'True'} if flask.g.user.is_guest else {'error': 'None'}

    return json.dumps(results)


@app.route('/removeGenesetFromProject')
@login_required(json=True, allow_guests=True)
def remove_geneset_from_project():
    results = geneweaverdb.remove_geneset_from_project(request.args)
    return json.dumps(results)


@app.route('/removeGenesetsFromMultipleProjects')
@login_required(json=True, allow_guests=True)
def remove_genesets_from_multiple_projects():
    results = geneweaverdb.remove_genesets_from_multiple_projects(request.args)
    return json.dumps(results)


@app.route('/deleteGeneset')
@login_required(json=True)
def delete_geneset():
    results = geneweaverdb.delete_geneset_by_gsid(request.args)
    return json.dumps(results)


@app.route('/deleteGenesetValueByID', methods=['GET', 'POST'])
@login_required(json=True)
def delete_geneset_value():
    results = geneweaverdb.delete_geneset_value_by_id(request.args)
    return json.dumps(results)


@app.route('/editGenesetIdValue', methods=['GET'])
@login_required(json=True)
def edit_geneset_id_value():
    results = geneweaverdb.edit_geneset_id_value_by_id(request.args)
    return json.dumps(results)


def remove_non_ascii(text):
    return ''.join([i if ord(i) < 128 else ' ' for i in text.strip('\r')]) if text else None


def split_lines_and_tabs(to_split=''):
    return (re.split(r'\t+', row) for row in iter(to_split.splitlines())) if to_split else ()


@app.route('/addGenesetGene', methods=['GET', 'POST'])
@login_required(json=True)
def add_geneset_gene():

    # Data from GET / POST
    input_data = request.args if request.args else request.form

    # Generic Info
    user = flask.g.user
    gs_id = input_data['gsid']
    results = []
    warnings = []
    errors = []

    # Copy/Paste and File Upload
    new_genes = input_data.get('text_data') + os.linesep + input_data.get('file_contents')
    new_genes = split_lines_and_tabs(remove_non_ascii(new_genes))
    gene_dict = {split[0]: {'id': split[0], 'value': split[1]} for split in new_genes if len(split) > 1}

    # Add Single Gene
    single_value = input_data.get('single_value')
    single_id = input_data.get('single_id')
    if single_id and single_value:
        gene_dict[single_id] = {'id': single_id, 'value': single_value}

    if not geneweaverdb.user_can_edit(user.user_id, gs_id) and not (user.is_admin or user.is_curator):
        errors.append({'error': 'You don\'t have permission to modify this geneset'})
    if len(gene_dict) < 1:
        errors.append({'error': 'No genes to upload'})
    else:
        # We can't add genes we don't have an ode_gene_id for
        missing = []
        gene_ids = geneweaverdb.geneset_gene_identifiers(gs_id, [(gene_dict[gene]['id'],) for gene in gene_dict])
        for gene in gene_ids:
            if gene[1]:
                gene_dict[gene[0]]['ode_gene_id'] = gene[1]
            else:
                missing.append(gene[0])
                del gene_dict[gene[0]]

        warnings += [{'warning': 'Identifier Not Found for ID: {}'.format(gene)} for gene in missing]

        # We will overwrite genes only if the user explicitly says to do it
        overwrite = input_data.get('overwrite', False) == 'true'

        if len(gene_dict) < 1:
            errors.append({'error': 'No valid genes to upload'})
        else:
            existing = geneweaverdb.existing_identifiers_for_geneset(gs_id,
                                                                     tuple(gene_dict[gene]['id'] for gene in gene_dict))
            # elements can be duplicated in this list, so let's turn it into a set
            existing = sorted(set([gene[0] for gene in existing]))

            if overwrite:
                warnings += [{'warning': 'The value for \'{}\', has been overwritten in this geneset'.format(gene)} for gene in existing]

            else:
                for gene in existing:
                    del gene_dict[gene]

                warnings += [{'warning': 'The Source ID \'{}\', already exists for this geneset'.format(gene)} for gene in existing]

            row_list = [(gs_id, gene_dict[gene]['ode_gene_id'], gene_dict[gene]['value'], gene_dict[gene]['id'])
                        for gene in gene_dict]
            if row_list:
                db_results, db_errors = geneweaverdb.add_geneset_genes_to_temp(gs_id, row_list)
                results += db_results
                errors += db_errors
            else:
                errors.append({'error': 'All genes currently exist in this geneset.'})

    return json.dumps({'results': results, 'errors': errors, 'warnings': warnings})


@app.route('/cancelEditByID', methods=['GET'])
@login_required(json=True)
def cancel_edit_by_id():
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
@login_required(json=True, allow_guests=True)
def check_results():
    runhash = request.args.get('runHash', type=str)
    resultpath = config.get('application', 'results')

    files = [f for f in os.listdir(resultpath) if path.isfile(path.join(resultpath, f))]
    found = False

    for f in files:
        rh = f.split('.')[0]

        if rh == runhash:
            found = True
            break

    return json.dumps({'exists': found})


@app.route('/deleteResults')
@login_required(json=True, allow_guests=True)
def delete_result():
    results = geneweaverdb.delete_results_by_runhash(request.args)
    runhash = request.args.get('runHash', type=str)
    resultpath = config.get('application', 'results')

    # Delete the files from the results folder too--traverse the results
    # folder and match based on runhash
    files = [f for f in os.listdir(resultpath) if path.isfile(path.join(resultpath, f))]

    for f in files:
        rh = f.split('.')[0]

        if rh == runhash:
            # os.remove(path.join(RESULTS_PATH, f))
            os.remove(path.join(resultpath, f))

    return json.dumps(results)


@app.route('/editResults')
@login_required(json=True, allow_guests=True)
def edit_result():
    results = geneweaverdb.edit_results_by_runhash(request.args)
    return json.dumps(results)


@app.route('/results')
@login_required(allow_guests=True)
def render_user_results():
    table = 'production.result'
    if 'user_id' in session:
        user_id = session['user_id']
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
    return render_template('results.html', headerCols=headerCols, user_id=user_id, columns=columns, table=table)


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

    if 'sort' not in session:
        session['sort'] = ''
    if 'dir' not in session:
        session['dir'] = 'ASC'
    if 'length' not in session:
        session['length'] = 50
    if 'start' not in session:
        session['start'] = 0
    if 'search' not in session:
        session['search'] = ''

    ## Retrieves the geneset but using the new alternate symbol ID
    gs = geneweaverdb.get_geneset(gs_id, user_id)
    gsvs = geneweaverdb.get_geneset_values(
        gs.geneset_id, 
        session['extsrc'], 
        session['length'], 
        session['start'],
        session['search'], 
        session['sort'],
        session['dir']
    )
    geneset_values = []

    #for gsv in gs.geneset_values:
    for gsv in gsvs:
        geneset_values.append({'ode_gene_id': gsv.ode_gene_id,
                               'ode_ref_id': gsv.ode_ref,
                               'gdb_id': gsv.gdb_id,
                               'alt_gene_id': alt_gene_id})

    return json.dumps(geneset_values)


@app.route('/updateGenesetSpecies', methods=['GET'])
def update_geneset_species():
    args = request.args
    if int(session['user_id']) == int(args['user_id']):
        results = uploadfiles.update_species_by_gsid(args)
        return json.dumps(results)


@app.route('/updateGenesetIdentifier', methods=['GET'])
def update_geneset_identifier():
    args = request.args
    if int(session['user_id']) == int(args['user_id']):
        results = uploadfiles.update_identifier_by_gsid(args)
        return json.dumps(results)


@app.route('/help/')
def render_help():
    help_url = config.get('application', 'help_url')
    return render_template('help.html', help_url=help_url)


@app.route('/about')
def render_about():
    return render_template('about.html')


def nested_dict():
    return defaultdict(nested_dict)


@app.route('/data')
def render_data():
    species_info = geneweaverdb.get_all_species_resources()
    platform_info = geneweaverdb.get_all_platform_resources()
    ontology_info = geneweaverdb.get_all_ontology_resources()
    gene_info = geneweaverdb.get_all_gene_resources()
    return render_template('data.html', sp=species_info, pl=platform_info, ont=ontology_info,
                                 gene=gene_info)


@app.route('/funding')
def render_funding():
    return render_template('funding.html')


@app.route('/datasharing')
def render_datasharing():
    return render_template('datasharing.html')


@app.route('/datasources')
def render_datasources():
    attribs = geneweaverdb.get_all_attributions()
    attlist = []
    attcounts = {}
    for at_id, at_abbrev in attribs.items():
        attlist.append(at_abbrev)
        # attcounts.append(geneweaverdb.get_attributed_genesets(at_id, at_abbrev))
        attcounts[at_abbrev] = geneweaverdb.get_attributed_genesets(at_id, at_abbrev)

    return render_template('datasources.html', attributions=attlist, attcounts=attcounts)


@app.route('/privacy')
def render_privacy():
    return render_template('privacy.html')


@app.route('/usage')
def render_usage():
    return render_template('usage.html')


@app.route('/register', methods=['GET', 'POST'])
def render_register():
    return render_template('register.html')


@app.route('/reset', methods=['GET', 'POST'])
def render_reset():
    return render_template('reset.html')


@app.route('/reset_submit.html', methods=['GET', 'POST'])
def reset_password():
    form = request.form
    user = geneweaverdb.get_user_byemail(form['usr_email'])
    if user is None:
        return render_template('reset.html', reset_failed=True)
    else:
        new_password = geneweaverdb.reset_password(user.email)
        notifications.send_email(user.email, "Password Reset Request",
                                 "Your new temporary password is: " + new_password)
        return redirect('reset_success')


@app.route('/reset_success')
def render_success():
    return render_template('password_reset.html')

@app.route('/change_password', methods=['POST'])
@login_required(json=True)
def change_password():
    user = flask.g.user
    if geneweaverdb.authenticate_user(user.email, request.form.get('curr_pass')) is None:
        return "Fail"
    else:
        geneweaverdb.change_password(user.user_id, request.form.get('new_pass'))
        return "Success"

@app.route('/generate_api_key', methods=['POST'])
def generate_api_key():
    geneweaverdb.generate_api_key(session.get('user_id'))
    return redirect('accountsettings')


@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    news_array = geneweaverdb.get_news()
    stats = geneweaverdb.get_stats()
    return render_template('index.html', news_array=news_array, stats=stats)


@app.route('/register_submit.html', methods=['GET', 'POST'])
def json_register_successful():
    # Secret key for reCAPTCHA form
    RECAP_SECRET = '6LeO7g4TAAAAAObZpw2KFnFjz1trc_hlpnhkECyS'
    RECAP_URL = 'https://www.google.com/recaptcha/api/siteverify'
    form = request.form
    http = urllib3.PoolManager()

    if not form['usr_first_name']:
        return render_template('register.html', error="Please enter your first name.")
    elif not form['usr_last_name']:
        return render_template('register.html', error="Please enter your last name.")
    elif not form['usr_email']:
        return render_template('register.html', error="Please enter your email.")
    elif not form['usr_password']:
        return render_template('register.html', error="Please enter your password.")

    captcha = form['g-recaptcha-response']

    ## No robots
    if not captcha:
        return render_template('register.html',
                                     error="There was a problem with your captcha input. Please try again.")

    else:
        ## The only data required by reCAPTCHA is secret and response. An
        ## optional parameter, remotep, containing the end user's IP can also
        ## be appended.
        pdata = {'secret': RECAP_SECRET, 'response': captcha}
        resp = http.request('POST', RECAP_URL, fields=pdata)

    ## 200 = OK
    if resp.status != 200:
        return render_template('register.html',
                                     error=("There was a problem with the reCAPTCHA servers. "
                                            "Please try again."))

    rdata = json.loads(resp.data)

    ## If success is false, the dict should contain an 'error-code.' This
    ## isn't checked currently.
    if not rdata['success']:
        return render_template('register.html',
                                     error="Incorrect captcha. Please try again.")
    user = _form_register()

    if user is None:
        return render_template('register.html', register_not_successful=True)
    else:
        session['user_id'] = user.user_id
        remote_addr = request.remote_addr
        if remote_addr:
            session['remote_addr'] = remote_addr

    flask.g.user = user

    return render_home()


@create_guest
@login_required(allow_guests=True)
@app.route('/add_geneset_to_project/<string:project_id>/<string:geneset_id>.html', methods=['GET', 'POST'])
def add_geneset_to_project(project_id, geneset_id):
    return str(geneweaverdb.insert_geneset_to_project(project_id, geneset_id))


@app.route('/create_project/<string:project_name>.html', methods=['GET', 'POST'])
def create_project(project_name):
    user_id = session['user_id']
    return str(geneweaverdb.create_project(project_name, user_id))


@app.template_filter('quoted')
def quoted(s):
    l = re.findall('\'([^\']*)\'', str(s))
    if l:
        return l[0]
    return None


@app.route('/notifications')
@login_required()
def render_notifications():
    return render_template('notifications.html')


@app.route('/notifications.json')
@login_required(json=True)
def get_notifications_json():
    if 'start' in request.args:
        start = request.args['start']
    else:
        start = 0
    if 'limit' in request.args:
        #
        limit = int(request.args['limit']) + 1
        notes = notifications.get_notifications(session['user_id'], start, limit)
        if len(notes) < limit:
            has_more = False
        else:
            has_more = True
            del notes[-1]
    else:
        notes = notifications.get_notifications(session['user_id'], start)
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


@app.route('/dismiss_notification')
@login_required(json=True)
def dismiss_notification():
    if 'note_id' in request.args:
        note_id = request.args['note_id']
        result = notifications.dismiss_notification(note_id)
    else:
        result = {'error': 'Notification ID wasn\'t included in request.'}

    return json.dumps(result)


@app.route('/unread_notification_count.json')
@login_required(json=True)
def get_unread_notification_count_json():
    count = notifications.get_unread_count(session['user_id'])
    return json.dumps({'unread_notifications': count})


@app.route('/message_group.json', methods=['POST'])
@login_required(json=True)
def message_group_json():
    user_id = session['user_id']
    group_id = int(request.form.get('group_id', '-1'))

    if group_id in [g.grp_id for g in geneweaverdb.get_groups_owned_by_user(user_id)]:
        try:
            subject = bleach.clean(request.form['subject'], strip=True)
            message = bleach.clean(request.form['message'], strip=True)
            if len(subject) < 1 or len(message) < 1:
                raise KeyError

            notifications.send_group_notification(group_id, subject, message)
            response = jsonify(success=True, message="Message sent.")

        except KeyError:
            response = jsonify(success=False, message="Can't send message. You must provide both a subject and a message.")
            response.status_code = 400

    else:
        response = jsonify(success=False, message='You must be a group owner to message group members.')
        response.status_code = 401

    return response


@app.route('/message_all.json', methods=['POST'])
@login_required(json=True)
def message_all_json():
    user_id = session['user_id']

    if geneweaverdb.get_user(user_id).is_admin:
        try:
            subject = bleach.clean(request.form['subject'], strip=True)
            message = bleach.clean(request.form['message'], strip=True)
            notifications.send_all_users_notification(subject, message)
            response = jsonify(success=True)

        except KeyError:
            response = jsonify(success=False, message="Can't send message. You must provide both a subject and a message.")
            response.status_code = 400

    else:
        response = jsonify(success=False, message='You must be an admin to message all users.')
        response.status_code = 401

    return response


@app.route('/report_bug.json', methods=['POST'])
@login_required(allow_guests=True)
def report_bug_to_jira():

    results = report_bug.to_jira(
        description=request.values['description'],
        fullname=request.values['fullname'],
        email=request.values['email'],
        user_id=request.values['user_id'],
        user_page=request.values['user_page']
    )

    return json.dumps(results)


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


class AddGeneSetByUser(restful.Resource):
    def post(self, apikey):
        return uploadfiles.post_geneset_by_user(apikey, request.data)


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

class ToolUpSet(restful.Resource):
    def get(self, apikey, homology, genesets, zeros):
        return upsetblueprint.run_tool_api(apikey, homology, genesets, zeros)


class ToolUpSetProjects(restful.Resource):
    def get(self, apikey, homology, projects, zeros):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return upsetblueprint.run_tool_api(apikey, homology, genesets, zeros)


class ToolMSET(restful.Resource):
    def get(self, apikey, homology, numberOfSamples, genesets):
        return msetblueprint.run_tool_api(apikey, homology, numberOfSamples, genesets)


class ToolMSETProjects(restful.Resource):
    def get(self, apikey, homology, numberOfSamples, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return msetblueprint.run_tool_api(apikey, homology, numberOfSamples, genesets)


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
api.add_resource(AddGeneSetByUser,'/api/add/geneset/byuser/<apikey>/')

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

api.add_resource(ToolMSET, '/api/tool/mset/<apikey>/<homology>/<method>/<genesets>/')
api.add_resource(ToolMSETProjects,
                 '/api/tool/mset/byprojects/<apikey>/<homology>/<method>/<projects>/')

api.add_resource(ToolUpSet,
                 '/api/tool/upset/<apikey>/<homology>/<zeros>/<genesets>/')
api.add_resource(ToolUpSetProjects,
                 '/api/tool/upset/byprojects/<apikey>/<homology>/<zeros>/<projects>/')

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

