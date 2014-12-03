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
from collections import OrderedDict
from tools import genesetviewerblueprint, jaccardclusteringblueprint, jaccardsimilarityblueprint, phenomemapblueprint, combineblueprint, abbablueprint, booleanalgebrablueprint
#import sphinxapi
#import search

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

RESULTS_PATH = '/home/geneweaver/dev/geneweaver/results'


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


@app.route('/analyze.html')
def render_analyze():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('analyze.html', active_tools=active_tools)

@app.route('/share_projects.html')
def render_shareprojects():
    active_tools = geneweaverdb.get_active_tools()
    return flask.render_template('share_projects.html', active_tools=active_tools)

@app.route('/editgenesets.html')
def render_editgenesets():
    return flask.render_template('editgenesets.html')

@app.route('/accountsettings.html')
def render_accountsettings():
    user = geneweaverdb.get_user(flask.session.get('user_id'))
    return flask.render_template('accountsettings.html', user=user)


@app.route('/login.html')
def render_login():
    return flask.render_template('login.html')

@app.route('/login_error')
def render_login_error():
    return flask.render_template('login.html',error="Invalid Credentials")

@app.route('/resetpassword.html')
def render_forgotpass():
    return flask.render_template('resetpassword.html')


@app.route('/viewgenesetdetails/<int:gs_id>')
def render_viewgeneset(gs_id):
    emphgenes={}
    emphgeneids = []
    user_id = flask.session['user_id']
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))
    geneset = geneweaverdb.get_geneset(gs_id, user_id)
    return flask.render_template('viewgenesetdetails.html', geneset=geneset, emphgeneids=emphgeneids)


@app.route('/mygenesets.html')
def render_viewgenesets():
    # get the genesets belonging to the user
    user_id = flask.session.get('user_id')
    if user_id:
        genesets = geneweaverdb.get_genesets_by_user_id(user_id)
    else:
        genesets = None
    return flask.render_template('mygenesets.html', genesets=genesets)


@app.route('/emphasis.html', methods=['GET', 'POST'])
def render_emphasis():

    '''
    Emphasis_AddGene
    Emphasis_RemoveGene
    Emphasis_RemoveAllGenes
    Emphasis_SearchGene
    '''

    foundgenes={}
    emphgenes={}
    emphgeneids = []
    user_id = flask.session['user_id']
    emphgenes = geneweaverdb.get_gene_and_species_info_by_user(user_id)
    for row in emphgenes:
        emphgeneids.append(str(row['ode_gene_id']))

    if flask.request.method == 'POST' :
        form  = flask.request.form

        if 'Emphasis_SearchGene' in form:
            search_gene = form['Emphasis_SearchGene']
            foundgenes = geneweaverdb.get_gene_and_species_info(search_gene)

    elif flask.request.method == 'GET' :
        args = flask.request.args

        if 'Emphasis_AddGene' in args :
            add_gene = args['Emphasis_AddGene']
            if add_gene:
                geneweaverdb.create_usr2gene(user_id, add_gene)

        if 'Emphasis_AddAllGenes' in args :
            add_all_genes = args['Emphasis_AddAllGenes']
            if add_all_genes:
                genes_list = add_all_genes.split(' ')
                for gene in genes_list:
                    if not str(gene) in emphgeneids :
                        geneweaverdb.create_usr2gene(user_id, gene)


        if 'Emphasis_RemoveGene' in args :
            remove_gene = args['Emphasis_RemoveGene']
            if remove_gene:
                geneweaverdb.delete_usr2gene_by_user_and_gene(user_id, remove_gene)

        if 'Emphasis_RemoveAllGenes' in args :
            if args['Emphasis_RemoveAllGenes'] == 'yes' :
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

@app.route('/search/<string:search_term>/<int:pagination_page>')
def render_search(search_term, pagination_page):
    # do a query of the search term, fetch the matching genesets
    ################################
    # TODO create a pooled connected somewhwere within genewaver
    client = sphinxapi.SphinxClient()
    client.SetServer('localhost', 9312)
    # Set the limit to get all results within the range of 1000
    # Retrieve only the results within the limit of the current page specified
    # in the pagination option
    resultsPerPage = 25
    offset = resultsPerPage * (pagination_page - 1)
    limit = resultsPerPage
    max_matches = 1000
    # Set the limits and query the client
    client.SetLimits(offset, limit, max_matches)
    results = client.Query(search_term)
    # Transform the genesets into geneset objects for Jinga display
    genesets = list()
    for match in results['matches']:
        genesetID = match['id']
        # TODO eliminate database query
        genesets.append(
            geneweaverdb.get_geneset(genesetID, flask.session.get('user_id')))
    # Calculate pagination information for display
    ##############################
    numResults = int(results['total'])
    # Do ceiling integer division
    numPages = ((numResults - 1) // resultsPerPage) + 1
    currentPage = pagination_page
    # Calculate the bouding numbers for pagination
    end_page_number = currentPage + 4
    if end_page_number > numPages:
        end_page_number = numPages
    #
    paginationValues = {'numResults': numResults, 'numPages': numPages, 'currentPage': currentPage,
                        'resultsPerPage': resultsPerPage, 'search_term': search_term, 'end_page_number': end_page_number}
    # render the page with the genesets
    return flask.render_template('search.html', searchresults=results, genesets=genesets, paginationValues=paginationValues)

@app.route('/search.html')
def new_search():
    paginationValues = {'numResults': 0, 'numPages': 1, 'currentPage':
                        1, 'resultsPerPage': 10, 'search_term': '', 'end_page_number': 1}
    print 'search from link'
    return flask.render_template('search.html', paginationValues=None)

@app.route('/search/')
def render_searchFromHome():
    #Get the posted information from the form TODO add a conditional. If there are insufficient url parameters don't do a search, just render the page don't handle forms.
    #TODO check search.html. Make sure that if there is no search data, a blank search page is properly displayed (check values in jinja).
    ##########################
    form = flask.request.form
    #Search term is given from the searchbar in the form
    search_term = request.args.get('searchbar')
    #pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    pagination_page = int(request.args.get('pagination_page'))
    #Build a list of search fields selected by the user (checkboxes) passed in as URL parameters
    #Associate the correct fields with each option given by the user
    field_list = {'searchGenesets': False, 'searchGenes': False, 'searchAbstracts': False, 'searchOntologies': False}
    search_fields = list()
    if(request.args.get('searchGenesets')):
        search_fields.append('name,description,label')
        field_list['searchGenesets'] = True
    if(request.args.get('searchGenes')):
        search_fields.append('genes')
        field_list['searchGenes'] = True
    if(request.args.get('searchAbstracts')):
        search_fields.append('pub_authors,pub_title,pub_abstract,pub_journal')
        field_list['searchAbstracts'] = True
    if(request.args.get('searchOntologies')):
        search_fields.append('ontologies')
        field_list['searchOntologies'] = True
    #Add the default case, at least be able to search these values for all searches
    search_fields.append('gs_id,gsid_prefixed,species,taxid')
    search_fields =  ','.join(search_fields)
    #
    #TODO update get function, then pull parameter checking out to the function
    #userValues = search.getUserFiltersFromApplicationRequest(request.form)
    search_values = search.keyword_paginated_search(search_term, pagination_page, search_fields)
    return flask.render_template('search.html', searchresults=search_values['searchresults'], genesets=search_values['genesets'], paginationValues=search_values['paginationValues'], field_list = field_list, searchFilters=search_values['searchFilters'])

@app.route('/searchFilter.json',methods=['POST'])
#This route will take as an argument, search parameters for a filtered search
def render_search_json():
    #Get the user values from the request
    userValues = search.getUserFiltersFromApplicationRequest(request.form)
    #Get a sphinx search
    #First, print some diangostic information
    search_values = search.keyword_paginated_search(userValues['search_term'], userValues['pagination_page'], userValues['search_fields'], userValues['userFilters'])
    
    #TODO perform a search based on filtered data
    #results = search.(something here)
    return flask.render_template('search.html', searchresults=search_values['searchresults'], genesets=search_values['genesets'], paginationValues=search_values['paginationValues'], field_list = userValues['field_list'], searchFilters=search_values['searchFilters'], userFilters=userValues['userFilters'])

@app.route('/searchsuggestionterms.json')
def render_search_suggestions():
    return flask.render_template('searchsuggestionterms.json')


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
	data = geneweaverdb.genesets_per_tier()
        return json.dumps(data)
    else:
	return flask.render_template('admin/adminForbidden.html')

@app.route('/admin/genesetsperspeciespertier')
def admin_widget_2():  
    if "user" in flask.g and flask.g.user.is_admin:
	data = geneweaverdb.genesets_per_species_per_tier()
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
		temp.update({str(key).split("-")[1]+"/"+str(key).split("-")[2]: data[tool][key]})
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
        return json.dumps(data, default=date_handler)
    else:
	return flask.render_template('admin/adminForbidden.html')

@app.route('/admin/sizeofgenesets')
def admin_widget_6():  
    if "user" in flask.g and flask.g.user.is_admin:
	data = geneweaverdb.size_of_genesets()
	print data	
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

	all_gs_sizes=[]
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
			distinct_sizes.update({size:arr})
		    else:
			arr=distinct_sizes[size]
			arr.append(item['res_id'])
			distinct_sizes.update({size:arr})
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
		    avggenes=geneweaverdb.avg_genes(gs)
		avg = geneweaverdb.avg_tool_times(geneset_sizes[item][num], item)
		geneset_sizes[item][num]={"time":avg.total_seconds()*1000, "genes":avggenes}
		
	
	dat = []
	for tool in geneset_sizes:	    
	    for size in geneset_sizes[tool]:
		temp = dict();
		temp.update({"tool": tool, "size": str(size), "time":str(int(geneset_sizes[tool][size]['time'])), "genes":str(int(geneset_sizes[tool][size]['genes']))})
		dat.append(temp)
	    	
        return json.dumps(dat)
    else:
	return flask.render_template('admin/adminForbidden.html')

@app.route('/admin/adminEdit')
def admin_edit():  
    if "user" in flask.g and flask.g.user.is_admin:
        rargs=request.args
	table = rargs['table']    	
        return AdminEdit().render("admin/adminEdit.html", columns=rargs , table=table)
    else:
        return flask.render_template('admin/adminForbidden.html')

@app.route('/admin/adminSubmitEdit', methods=['POST'])
def admin_submit_edit():
    if "user" in flask.g and flask.g.user.is_admin:
        form=flask.request.form	
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


@app.route('/admin/adminDelete',methods=['POST'])
def admin_delete():
    if "user" in flask.g and flask.g.user.is_admin:
        form=flask.request.form	
	table = form['table']
	prim_keys = geneweaverdb.get_primary_keys(table.split(".")[1])
	keys = []
	for att in prim_keys:
	    temp = form[att['attname']]
	    keys.append(att['attname'] + "=\'" + temp + "\'")		
	result = geneweaverdb.admin_delete(form,keys)
        return json.dumps(result)
    else:
	return flask.render_template('admin/adminForbidden.html')


@app.route('/admin/adminAdd',methods=['POST'])
def admin_add():  
    if "user" in flask.g and flask.g.user.is_admin:
        form=flask.request.form
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

@app.route('/results.html')
def render_user_results():
    user_id = None
    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

        tool_stats = geneweaverdb.tool_stats_by_user(user_id)
        return flask.render_template('results.html', tool_stats=tool_stats)

    return flask.render_template('results.html')


@app.route('/help.html')
def render_help():
    return flask.render_template('help.html')


@app.route('/about.html')
def render_about():
    return flask.render_template('about.html')


@app.route('/register.html', methods=['GET', 'POST'])
def render_register():
    return flask.render_template('register.html')


@app.route('/reset.html', methods=['GET', 'POST'])
def render_reset():
    return flask.render_template('reset.html')

# render home if register is successful


@app.route('/register_submit.html', methods=['GET', 'POST'])
def json_register_successful():
    form = flask.request.form
    if not form['usr_first_name']:
        return flask.render_template('register.html', error="Please enter your first name.")
    elif not form['usr_last_name']:
        return flask.render_template('register.html', error="Please enter your last name.")
    elif not form['usr_email']:
        return flask.render_template('register.html', error="Please enter your email.")
    elif not form['usr_password']:
        return flask.render_template('register.html', error="Please enter your password.")

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

class ToolCombine(restful.Resource):

    def get(self, apikey, homology, genesets):
        return combineblueprint.run_tool_api(apikey, homology, genesets)
        
class ToolCombineProjects(restful.Resource):

    def get(self, apikey, homology, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return combineblueprint.run_tool_api(apikey, homology, genesets)

class ToolPhenomeMap(restful.Resource):

    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, genesets):
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)

class ToolPhenomeMapProjects(restful.Resource):
    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)

class ToolBooleanAlgebra(restful.Resource):
    def get(self, apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return phenomemapblueprint.run_tool_api(apikey, homology, minGenes, permutationTimeLimit, maxInNode, permutations, disableBootstrap, minOverlap, nodeCutoff, geneIsNode, useFDR, hideUnEmphasized, p_Value, maxLevel, genesets)

class ToolBooleanAlgebra(restful.Resource):
    def get(self, apikey, relation, genesets):
        return booleanalgebrablueprint.run_tool_api(apikey, relation, genesets)
  
class ToolBooleanAlgebraProjects(restful.Resource):

    def get(self, apikey, relation, projects):
        genesets = geneweaverdb.get_genesets_by_projects(apikey, projects)
        return booleanalgebrablueprint.run_tool_api(apikey, relation, genesets)      

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
api.add_resource(ToolGenesetViewer, '/api/tool/genesetviewer/<apikey>/<homology>/<supressDisconnected>/<minDegree>/<genesets>/')
api.add_resource(ToolGenesetViewerProjects, '/api/tool/genesetviewer/byprojects/<apikey>/<homology>/<supressDisconnected>/<minDegree>/<projects>/')

api.add_resource(ToolJaccardClustering, '/api/tool/jaccardclustering/<apikey>/<homology>/<method>/<genesets>/')
api.add_resource(ToolJaccardClusteringProjects, '/api/tool/jaccardclustering/byprojects/<apikey>/<homology>/<method>/<projects>/')

api.add_resource(ToolJaccardSimilarity, '/api/tool/jaccardsimilarity/<apikey>/<homology>/<pairwiseDeletion>/<genesets>/')
api.add_resource(ToolJaccardSimilarityProjects, '/api/tool/jaccardsimilarity/byprojects/<apikey>/<homology>/<pairwiseDeletion>/<projects>/')

api.add_resource(ToolCombine, '/api/tool/combine/<apikey>/<homology>/<genesets>/')
api.add_resource(ToolCombineProjects, '/api/tool/combine/byprojects/<apikey>/<homology>/<projects>/')

api.add_resource(ToolPhenomeMap, '/api/tool/phenomemap/<apikey>/<homology>/<minGenes>/<permutationTimeLimit>/<maxInNode>/<permutations>/<disableBootstrap>/<minOverlap>/<nodeCutoff>/<geneIsNode>/<useFDR>/<hideUnEmphasized>/<p_Value>/<maxLevel>/<genesets>/')
api.add_resource(ToolPhenomeMapProjects, '/api/tool/phenomemap/byprojects/<apikey>/<homology>/<minGenes>/<permutationTimeLimit>/<maxInNode>/<permutations>/<disableBootstrap>/<minOverlap>/<nodeCutoff>/<geneIsNode>/<useFDR>/<hideUnEmphasized>/<p_Value>/<maxLevel>/<projects>/')

api.add_resource(ToolBooleanAlgebra, '/api/tool/booleanalgebra/<apikey>/<relation>/<genesets>/')
api.add_resource(ToolBooleanAlgebraProjects, '/api/tool/booleanalgebra/byprojects/<apikey>/<relation>/<projects>/')

# ********************************************
# END API BLOCK
# ********************************************


if __name__ == '__main__':
    app.debug = True
    app.run()
