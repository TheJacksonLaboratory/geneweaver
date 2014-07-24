import flask
import genesetblueprint
import geneweaverdb

app = flask.Flask(__name__)
app.register_blueprint(genesetblueprint.geneset_blueprint)

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


@app.before_request
def check_for_user_login():
    form = flask.request.form
    if 'usr_email' in form:
        # TODO deal with login failure
        user = geneweaverdb.get_user(form['usr_email'], form['usr_password'])
        if user is not None:
            flask.session['user'] = user
        elif 'user' in flask.session:
            del flask.session['user']

    # TODO do I need to update flask.g.user or is session good enough?


# the context processor will inject global variables for us so that we can refer to them from our flask templates
@app.context_processor
def inject_globals():
    # TODO you need to care about escaping
    return {
        'newsArray': newsArray
    }


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


@app.route('/index.html', methods=['GET', 'POST'])
@app.route('/', methods=['GET', 'POST'])
def render_home():
    return flask.render_template('index.html')

if __name__ == '__main__':
    app.debug = True
    app.run()
