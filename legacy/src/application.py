import flask
from flask.ext.admin import Admin, BaseView, expose
from flask.ext.admin.base import MenuLink
from flask.ext import restful
from flask import request
import adminviews
import genesetblueprint
import geneweaverdb
import json
import os
from tools import genesetviewerblueprint, jaccardclusteringblueprint, jaccardsimilarityblueprint, phenomemapblueprint, combineblueprint, abbablueprint, booleanalgebrablueprint

app = flask.Flask(__name__)
app.register_blueprint(abbablueprint.abba_blueprint)
app.register_blueprint(combineblueprint.combine_blueprint)
app.register_blueprint(genesetblueprint.geneset_blueprint)
app.register_blueprint(genesetviewerblueprint.geneset_viewer_blueprint)
app.register_blueprint(phenomemapblueprint.phenomemap_blueprint)
app.register_blueprint(jaccardclusteringblueprint.jaccardclustering_blueprint)
app.register_blueprint(jaccardsimilarityblueprint.jaccardsimilarity_blueprint)
app.register_blueprint(booleanalgebrablueprint.boolean_algebra_blueprint)

# TODO this key must be changed to something secret (ie. not committed to the repo).
#      Comment out the print message when this is done
print '==================================================='
print 'THIS VERSION OF GENEWEAVER IS NOT SECURE. YOU MUST '
print 'REGENERATE THE SECRET KEY BEFORE DEPLOYMENT. SEE   '
print '"How to generate good secret keys" AT              '
print 'http://flask.pocoo.org/docs/quickstart/ FOR DETAILS'
print '==================================================='
app.secret_key = '\x91\xe6\x1e \xb2\xc0\xb7\x0e\xd4f\x058q\xad\xb0V\xe1\xf22\xa5\xec\x1e\x905'


#*************************************
admin=Admin(app, name='Geneweaver', index_view=adminviews.AdminHome(url='/admin', name='Admin'));


admin.add_view(adminviews.Viewers(name='Users', endpoint='viewUsers', category='User Tools'))
admin.add_view(adminviews.Viewers(name='Publications', endpoint='viewPublications', category='User Tools'))
admin.add_view(adminviews.Viewers(name='Groups', endpoint='viewGroups', category='User Tools'))
admin.add_view(adminviews.Viewers(name='Projects', endpoint='viewProjects', category='User Tools'))

admin.add_view(adminviews.Viewers(name='Genesets', endpoint='viewGenesets', category='Gene Tools'))
admin.add_view(adminviews.Viewers(name='Genes', endpoint='viewGenes', category='Gene Tools'))
admin.add_view(adminviews.Viewers(name='Geneset Info', endpoint='viewGenesetInfo', category='Gene Tools'))
admin.add_view(adminviews.Viewers(name='Gene Info', endpoint='viewGeneInfo', category='Gene Tools'))

admin.add_view(adminviews.Add(name='User', endpoint='newUser', category='Add'))
admin.add_view(adminviews.Add(name='Publication', endpoint='newPub', category='Add'))
admin.add_view(adminviews.Add(name='Group', endpoint='newGroup', category='Add'))
admin.add_view(adminviews.Add(name='Project', endpoint='newProject', category='Add'))
admin.add_view(adminviews.Add(name='Geneset', endpoint='newGeneset', category='Add'))
admin.add_view(adminviews.Add(name='Gene', endpoint='newGene', category='Add'))
admin.add_view(adminviews.Add(name='Geneset Info', endpoint='newGenesetInfo', category='Add'))
admin.add_view(adminviews.Add(name='Gene Info', endpoint='newGeneInfo', category='Add'))


admin.add_view(adminviews.Edit(endpoint='adminEdit'))

admin.add_link(MenuLink(name='My Account', url='/accountsettings.html'))




#*************************************

RESULTS_PATH = '/var/www/html/geneweaver/results'


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
        user = geneweaverdb.authenticate_user(form['usr_email'], form['usr_password'])
        if user is not None:
            flask.session['user_id'] = user.user_id
            remote_addr = flask.request.remote_addr
            if remote_addr:
                flask.session['remote_addr'] = remote_addr

    flask.g.user = user
    return user

def send_mail(to, subject, body):
    print to, subject, body
    sendmail_location = "/usr/bin/mail" # sendmail location
    p = os.popen("%s -t" % sendmail_location, "w")
    p.write("From: NoReply@geneweaver.org\n")
    p.write("To: %s\n" % to)
    p.write("Subject: %s\n" % subject)
    p.write("\n") # blank line separating headers from body
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
            user = geneweaverdb.register_user(form['usr_name'], 'User', form['usr_email'], form['usr_password'])
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
    else:
        json_result['success'] = True
        json_result['usr_first_name'] = user.first_name
        json_result['usr_last_name'] = user.last_name
        json_result['usr_email'] = user.email

    return flask.jsonify(json_result)


@app.route('/analyze.html')
def render_analyze():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('analyze.html', active_tools=active_tools)

@app.route('/editgenesets.html')
def render_editgenesets():
    return flask.render_template('editgenesets.html')

@app.route('/accountsettings.html')
def render_accountsettings():
    return flask.render_template('accountsettings.html')

@app.route('/login.html')
def render_login():
    return flask.render_template('login.html')

@app.route('/resetpassword.html')
def render_forgotpass():
    return flask.render_template('resetpassword.html')

@app.route('/search.html')
def render_search():
    return flask.render_template('search.html')


#************************************************************************

@app.route('/accountmanage.html')
def render_account_manage():
    user_id = flask.session.get('user_id')
    if user_id:	
        current_user = geneweaverdb.get_user(user_id)
        return flask.render_template('accountmanage.html', current_user=current_user)
    else:
	return flask.render_template('index.html')

#admin route to add new item to the database
#@app.route('/admin/add')
def render_admin_add():
    if "user" in flask.g and flask.g.user.is_admin:
	columns = geneweaverdb.get_table_columns(table)
	print columns
        return flask.render_template('admin/add.html', columns=columns)
    else:
	return flask.render_template('index.html')

#this routes from datatables to get database information
#only admins are allowed to get results back from this route
@app.route('/admin/serversidedb')
def get_db_data():
    if "user" in flask.g and flask.g.user.is_admin:
        results = geneweaverdb.get_server_side(request.args)
        return json.dumps(results,default=date_handler)
    else:
	return flask.render_template('index.html')

def date_handler(obj):
    return obj.isoformat() if hasattr(obj, 'isoformat') else obj

#************************************************************************

@app.route('/manage.html')
def render_manage():
    return flask.render_template('my_genesets.html')


@app.route('/help.html')
def render_help():
    return flask.render_template('help.html')


@app.route('/register.html', methods=['GET', 'POST'])
def render_register():
    return flask.render_template('register.html')

@app.route('/reset.html', methods=['GET', 'POST'])
def render_reset():
    return flask.render_template('reset.html')

# render home if register is successful
@app.route('/register_submit.html', methods=['GET', 'POST'])
def json_register_successful():
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
        send_mail(user.email, "Password Reset Request", "Your new temporary password is: " + new_password)
        return flask.render_template('index.html')

@app.route('/accountsettings.html', methods=['GET', 'POST'])
def change_password():
    form = flask.request.form
    if form is None:
        return flask.render_template('accountsettings.html')
    else:
        user = geneweaverdb.get_user(flask.session.get('user_id'))

        if (geneweaverdb.authenticate_user(user.email, form['curr_pass'])) is None:
    	    return flask.render_template('accountsettings.html')
        else:
            success = geneweaverdb.change_password(user.user_id, form['new_pass'])
    	    return flask.render_template('accountsettings.html')

@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    return flask.render_template('index.html')


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
        return geneweaverdb.get_geneset_by_id(genesetid)
class GetGeneByGeneId(restful.Resource):
    def get(self, geneid):
        return geneweaverdb.get_gene_by_id(geneid)
class GetGenesetById(restful.Resource):
    def get(self, genesetid):
        return geneweaverdb.get_geneset_by_id(genesetid)
class GetGenesetByUser(restful.Resource):
    def get(self, apikey):
        return geneweaverdb.get_geneset_by_user(apikey)
class GetProjectsByUser(restful.Resource):
    def get(self, apikey):
        return geneweaverdb.get_projects_by_user(apikey)
class GetGenesetByProjectId(restful.Resource):
    def get(self, apikey, projectid):
        return geneweaverdb.get_geneset_by_project_id(apikey, projectid)  
        
# TODO format syntax       
class ToolGetFile(restful.Resource):
    def get(self, apikey, task_id, file_type):
        return geneweaverdb.get_file(apikey, task_id, file_type) 
class ToolGetStatus(restful.Resource):
    def get(self, task_id):
        return geneweaverdb.get_status(task_id) 
                
#Tools          
class ToolJaccardClustering(restful.Resource):
    def get(self, apikey, homology, method, genesets):
        return jaccardclusteringblueprint.run_tool_api(apikey, homology, method, genesets)
        
class ToolGenesetViewer(restful.Resource):
    def get(self, apikey, homology, supressDisconnected, minDegree, genesets):
        return genesetviewerblueprint.run_tool_api(apikey, homology, supressDisconnected, minDegree, genesets)
#Error: JaccardSimilarity does not create files => not an API problem, tool itself problem.
class ToolJaccardSimilarity(restful.Resource):
    def get(self, apikey, homology, pairwiseDeletion, genesets):
        return jaccardsimilarityblueprint.run_tool_api(apikey, homology, pairwiseDeletion, genesets)

class ToolCombine(restful.Resource):
    def get(self, apikey, homology, genesets):
        return combineblueprint.run_tool_api(apikey, homology, genesets)


api.add_resource(GetGenesetsByGeneRefId, '/api/get/geneset/bygeneid/<apikey>/<gene_ref_id>/<gdb_name>/')
api.add_resource(GetGenesetsByGeneRefIdHomology, '/api/get/geneset/bygeneid/<apikey>/<gene_ref_id>/<gdb_name>/homology')
api.add_resource(GetGenesetByUser, '/api/get/geneset/byuser/<apikey>/')
api.add_resource(GetGenesetById, '/api/get/geneset/bygenesetid/<genesetid>/')
api.add_resource(GetGenesByGenesetId, '/api/get/genes/bygenesetid/<genesetid>/')
api.add_resource(GetGeneByGeneId, '/api/get/gene/bygeneid/<geneid>/')
api.add_resource(GetProjectsByUser, '/api/get/project/byuser/<apikey>/')
api.add_resource(GetGenesetByProjectId, '/api/get/geneset/byprojectid/<apikey>/<projectid>/')

api.add_resource(ToolGetFile, '/api/tool/get/file/<apikey>/<task_id>/<file_type>/')
api.add_resource(ToolGetStatus, '/api/tool/get/status/<task_id>/')

api.add_resource(ToolGenesetViewer, '/api/tool/genesetviewer/<apikey>/<homology>/<supressDisconnected>/<minDegree>/<genesets>/')
api.add_resource(ToolJaccardClustering, '/api/tool/jaccardclustering/<apikey>/<homology>/<method>/<genesets>/')
api.add_resource(ToolJaccardSimilarity, '/api/tool/jaccardsimilarity/<apikey>/<homology>/<pairwiseDeletion>/<genesets>/')
api.add_resource(ToolCombine, '/api/tool/combine/<apikey>/<homology>/<genesets>/')

# ********************************************
# END API BLOCK
# ********************************************



if __name__ == '__main__':
    app.debug = True
    app.run()
