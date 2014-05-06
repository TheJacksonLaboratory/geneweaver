import collections
import flask
import os
import geneweaverdb
import re

source_dir = os.path.dirname(os.path.realpath(__file__))
app = flask.Flask(
    __name__,
    static_folder=os.path.join(source_dir, '..', 'static'),
    static_url_path='',
    template_folder=os.path.join(source_dir, '..', 'templates'))

# TODO this is a hack do something better with the news array
newsArray = [
    #("Weekend Maintenance", "ODE will be down for database updates and maintenance this weekend."),
    #("Maintenance", "GeneWeaver will undergo minor system maintenance from 8:00-8:15am EST on February 23rd."),
    #("Maintenance", "GeneWeaver will go down at 5pm Saturday April 28th for a sever move, we do not expect this to take more than 15 minutes."),
    ("2013: GeneWeaver user publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/23123364\">Potential translational targets revealed by linking mouse grooming behavioral phenotypes to gene expression using public databases</a> Andrew Roth, Evan J. Kyzar, Jonathan Cachat, Adam Michael Stewart, Jeremy Green, Siddharth Gaikwad, Timothy P. O'Leary, Boris Tabakoff, Richard E. Brown, Allan V. Kalueff. Progress in Neuro-Psychopharmacology & Biological Psychiatry 40:313-325."),
    ("2013: GeneWeaver user publication (Includes Deposited Data)", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/23329330\">Mechanistic basis of infertility of mouse intersubspecific hybrids</a> Bhattacharyya T, Gregorova S, Mihola O, Anger M, Sebestova J, Denny P, Simecek P, Forejt J. PNAS 2013 110 (6) E468-E477."),
    ("2012: GeneWeaver Publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/23195309\">Cross species integration of functional genomics experiments.</a>Jay, JJ. Int Rev Neurobiol 104:1-24."),
    ("Oct 2012: GeneWeaver user publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/22961259\">The Mammalian Phenotype Ontology as a unifying standard for experimental and high-throughput phenotyping data.</a> Smith CL, Eppig JT. Mamm Genome. 23(9-10):653-68"),
]

def page_selector(page, pages):
    pagelist = '<span name="page_selector" style="float: right">'
    pagelist += 'Page: '
    page_dict = {1 : '1', pages : str(pages)}
    for i in xrange(10, pages, 10):
        page_dict[i] = '. ' + str(i) + ' . '

    pstart = 1 if page-5 < 1 else page-5
    pend = pages if page+5 > pages else page+5
    for i in xrange(pstart, pend + 1):
        page_dict[i] = str(i)

    for k in sorted(page_dict.keys()):
        if page == k:
            pagelist += str(k) + ' '
        else:
            pagelist += '<a href="" data-page="' + str(k) + '">' + page_dict[k] + '</a> '

    pagelist += '</span>'

    return pagelist

def ode_link(action='', cmd='', other=''):

    url = 'index.html' if action == 'home' or not action else action + '.html'

    if cmd:
        url += '&cmd=' + cmd
    if other:
        url += '&' + other

    return url

def get_cmd():
    return flask.request.args.get('cmd')

@app.context_processor
def inject_globals():
    # TODO you need to care about escaping
    return {
        'ode_link': ode_link,
        'title': '',
        'topmenu': collections.OrderedDict([
            (ode_link('home'), 'Home'),
            (ode_link('search'), 'Search'),
            (ode_link('manage'), 'Manage GeneSets'),
            (ode_link('analyze'), 'Analyze GeneSets'),
            (ode_link('help', 'view', 'docid=acknowledgements'), 'About'),
        ]),
        'topsubmenu': {
            'Home': dict(),
            'About': dict(),
            'Search': collections.OrderedDict([
                (ode_link('search'), 'for GeneSets'),
                (ode_link('search', 'genes'), 'for Genes (ABBA)'),
            ]),
            'Manage GeneSets': collections.OrderedDict([
                (ode_link('manage', 'listgenesets'), 'My GeneSets'),
                (ode_link('manage', 'uploadgeneset'), 'Upload GeneSet'),
                (ode_link('manage', 'batchgeneset'), 'Batch Upload GeneSets'),
            ]),
            'Analyze GeneSets': collections.OrderedDict([
                (ode_link('analyze'), 'My Projects'),
                (ode_link('analyze', 'shared'), 'Shared Projects'),
                (ode_link('analyze', 'listresults'), 'Results'),
            ]),
        },
        'newsArray': newsArray,
        'persName': 'TODO ADD NAME',
    }


@app.route('/analyze.html')
def render_analyze():
    return flask.render_template('analyze.html')


@app.route('/uploadgeneset.html')
def render_uploadgeneset():
    return flask.render_template(
        'uploadgeneset.html',
        gs=dict(),
        all_species=geneweaverdb.get_all_species())


def tokenize_lines(candidate_sep_regexes, lines):
    """
    This function will tokenize all of the following lines and in doing so will attempt to infer which
    among the given candidate_sep_regexes is used as a token separator.
    """

    detected_sep_regex = None
    for line_num, curr_line in enumerate(lines):
        curr_line = curr_line.strip()

        # if the line is empty or just whitespace we're not going to skip it
        if curr_line:
            tokenized_line = None

            # if we haven't yet detected a separator try now
            if not detected_sep_regex:
                for candidate_regex in candidate_sep_regexes:
                    tokenized_line = re.split(candidate_regex, curr_line)
                    if len(tokenized_line) >= 2:
                        detected_sep_regex = candidate_regex
                        break
            else:
                tokenized_line = re.split(detected_sep_regex, curr_line)

            tokenized_line = [tok.strip() for tok in tokenized_line]
            yield tokenized_line


@app.route('/creategeneset.html', methods=['POST'])
def create_geneset():
    # TODO START IMPLEMENTATION NOTES (remove these once impl is complete)
    #
    # in php code this corresponds to the Manage.php::editgeneset(...) function with $cmd set to "uploadgeneset"
    # uploadTemplate followed by uploadTemplate_step2 seems to do the main work (NOTE: 'file_text' request
    # variable contains all IDs)
    #
    # END IMPLEMENTATION NOTES

    #print 'REQUEST FORM:', flask.request.form
    form = flask.request.form
    sp_id = int(form['sp_id'])

    file_text = form['file_text']
    file_lines = file_text.splitlines()
    candidate_sep_regexes = ['\t', ',', ' +']

    for curr_toks in tokenize_lines(candidate_sep_regexes, file_lines):
        # TODO php code allows multiple IDs per line. Do we need to continue to allow this? for now expecting 1 ID per line
        curr_id = ''
        curr_val = None
        counts_by_source = dict()
        all_results = []
        if len(curr_toks) >= 1:
            curr_id = curr_toks[0]
            if len(curr_toks) >= 2:
                try:
                    curr_val = float(curr_toks[1])

                    # We'll get results from both the gene table and platform table. We'll decide later which to use
                    # based on the number of results returned.
                    gene_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, gdb_id AS source, ode_ref_id AS ref_id
                            FROM gene
                            WHERE sp_id=%s AND LOWER(ode_ref_id)=%s;
                            ''',
                            (sp_id, curr_id)
                        )
                        gene_results = list(geneweaverdb.dictify_cursor(cursor))
                        all_results += gene_results
                        if gene_results:
                            result_sources = set()

                            for curr_result in gene_results:
                                key_tuple = (True, curr_result['source'])
                                curr_counts = None
                                try:
                                    curr_counts = counts_by_source[key_tuple]
                                except KeyError:
                                    curr_counts = [0, 0]
                                    counts_by_source[key_tuple] = curr_counts

                                # we need to make sure not to double count a source here
                                if curr_result['source'] not in result_sources:
                                    curr_counts[0] += 1
                                curr_counts[1] += 1

                    platform_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, m.pf_id AS source, prb_ref_id AS ref_id, pf_set
                            FROM platform m,probe p,probe2gene p2g
                            WHERE p.pf_id=m.pf_id AND p2g.prb_id=p.prb_id AND m.sp_id=%s AND LOWER(prb_ref_id)=%s
                            GROUP BY ode_gene_id, m.pf_id, prb_ref_id, m.pf_set;
                            ''',
                            (sp_id, curr_id)
                        )
                        platform_results = list(cursor)
                        if platform_results:
                            first_result = platform_results

                    if not (gene_results or platform_results):
                        # TODO tell user we didn't find a match for curr_id
                        pass

                except ValueError:
                    # TODO error reporting here
                    pass


    return flask.render_template(
        'uploadgeneset.html',
        gs=dict(),
        all_species=geneweaverdb.get_all_species())


@app.route('/search.html')
def render_search():
    return flask.render_template('search.html')


@app.route('/index.html')
def render_home():
    return flask.render_template('index.html')

# //Functions located at the bottom of this page
# switch ($cmd){
#  case "updategenesetthreshold": ACTION_Account::verifyLoggedIn("You must be logged in to edit GeneSets!");
#                        $this->editgenesetthreshold();
#                        break;
#  case "updategenesetontologies": ACTION_Account::verifyLoggedIn("You must be logged in to edit GeneSets!");
#                        $this->editgenesetontologies();
#                        break;
#  case "updategeneset": ACTION_Account::verifyLoggedIn("You must be logged in to edit GeneSets!");
#                        $this->editgeneset();
#                        break;
#
#  case "batchgeneset": ACTION_Account::verifyLoggedIn("You must be registered and logged in to upload GeneSets!");
#                       $this->batchgeneset();
#                       break;
#
#  case "batcheditgeneset": ACTION_Account::verifyLoggedIn("You must be registered and logged in to edit GeneSets!");
#                       $this->batcheditgeneset();
#                       break;
#
#  case "importgeneset": ACTION_Account::verifyLoggedIn("You must be registered and logged in to import a GeneSet!  Once logged in, you will have to resubmit the dataset again.  Sorry for the inconvience.");
#                        $this->importgeneset();
#
#                        break;
#  case "uploadgenesetNew":// ACTION_Account::verifyLoggedIn("You must be registered and logged in to upload a GeneSet!");
#                        $this->editgeneset_new();
#                        break;
#  case "uploadgeneset": ACTION_Account::verifyLoggedIn("You must be registered and logged in to upload a GeneSet!");
#                        $this->editgeneset();
#                        break;
#  case "similargenesets": // no check_login required
#                        $this->similargenesets();
#                        break;
#  case "viewgeneset": // no check_login required
#                        $this->viewgeneset();
#                        break;
#  case "addtoemphasis": // no check_login required
#                        $this->addtoemphasis();
#                        break;
#  case "viewpub": // no check_login required
#                        $this->viewpub();
#                        break;
#  case "viewgene": // no check_login required
#                        $this->viewgene();
#                        break;
#  case "downloadgeneset": $this->downloadgeneset_File();
#                        break;
#  default:
#  case "listgenesets": ACTION_Account::verifyLoggedIn("This feature is only available to registered and logged in users.");
#                       $this->listgenesets();
#                       break;
# }
@app.route('/manage.html')
def render_manage():
    return flask.render_template('my_genesets.html')

if __name__ == '__main__':
    app.debug = True
    app.run()
