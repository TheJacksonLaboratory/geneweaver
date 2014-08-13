import flask
import genesetblueprint
import geneweaverdb

app = flask.Flask(__name__)
app.register_blueprint(genesetblueprint.geneset_blueprint)

#meixiao: app.config['DEBUG']=true
#meixiao: app.debug = true
#meixiao: app.config['SECRET_KEY']='lkajfkdsjfiadfakfjdas'
#meixiao: config is a dictionary object in flask. It has a lot of build-in values, such as
#meixiao:   DEBUG, TESTING, SECRET_KEY, SESSION_COOKIE_NAME, SESSION_COOKIE_DOMAIN etc. Those values can be changes.
#meixiao: We can have multiple configuration files. If we have an external config file called "config.py"
#meixiao: We can use app.config.from_object('config') to read from that file

#meixiao: Python tuple: tup=('physics', 'chemistry', 1997, 2000), tuple values cannot be changes
#meixiao: Python list: list=['a', 'b', 'c', 'd']
#meixiao: Python dictionary: dict={'Alice':'2341', 'Beth':'9012', 'Cecil':'3258'}
#meixiao: Python dictionary is also associate arrays or hash tables.

# TODO this key must be changed to something secret (ie. not committed to the repo).
#      Comment out the print message when this is done
print '==================================================='
print 'THIS VERSION OF GENEWEAVER IS NOT SECURE. YOU MUST'
print 'REGENERATE THE SECRET KEY BEFORE DEPLOYMENT. SEE'
print '"How to generate good secret keys" AT'
print 'http://flask.pocoo.org/docs/quickstart/ FOR DETAILS'
print '==================================================='
app.secret_key = '\x91\xe6\x1e \xb2\xc0\xb7\x0e\xd4f\x058q\xad\xb0V\xe1\xf22\xa5\xec\x1e\x905'

# TODO the newsArray should probably be moved to a configuration file
#meixiao: newsArray is an array, with tuples as its elements.
#meixiao: If we want to move this news array into an external file, should we use a json file to hold all the news
#meixiao: so the reading and parsing will be easier?
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
#meixiao: jinja2 and flask obvious share some global variables such as: config, request, session, g, url_for(), get_flashed_messages()
#meixiao: To inject new variables automatically into the context of a template, context processors exist in Flask.
#meixiao:  Context processors run before the template is rendered and have the ability to inject new values into the template context.
#meixiao:  A context processor is a function that returns a dictionary.
#meixiao:  The keys and values of this dictionary are then merged with the template context, for all templates in the app:
@app.context_processor
def inject_globals():
    # TODO you need to care about escaping
    global_map = {
        'newsArray': newsArray
    }

    # lookup the current user
    session = flask.session
    user_id = session.get('user_id')
    if user_id:
        if flask.request.remote_addr == session.get('remote_addr'):
            global_map['user'] = geneweaverdb.get_user(user_id)
        else:
            # if IP addresses don't match we're going to reset the session for
            # a bit of extra safety
            _logout(session)

    return global_map


def _logout(session):
    try:
        del session['user_id']
    except KeyError:
        pass

    try:
        del session['remote_addr']
    except KeyError:
        pass


def _form_login():
    user = None
    _logout(flask.session)

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


#meixiao: register the user
def _form_register():
    user = None
    _logout(flask.session)

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
    _logout(flask.session)
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
    return flask.render_template('analyze.html')


@app.route('/search.html')
def render_search():
    return flask.render_template('search.html')


@app.route('/manage.html')
def render_manage():
    return flask.render_template('my_genesets.html')


@app.route('/help.html')
def render_help():
    return flask.render_template('help.html')


#meixiao: render the register page
@app.route('/register.html', methods=['GET', 'POST'])
def render_register():
    print flask.request.json
    print flask.request.form
    return flask.render_template('register.html')

#meixiao: render home if register is successful
@app.route('/register_result.html', methods=['GET', 'POST'])
def json_register_successful():
    print flask.request.json
    print flask.request.form
    json_result=dict()
    user =_form_register()
    if user is None:
        return flask.render_template('register.html', register_not_successful = True)
    else:
        return flask.render_template('index.html', user = user)

@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    return flask.render_template('index.html')

if __name__ == '__main__':
    app.debug = True
    app.run()
