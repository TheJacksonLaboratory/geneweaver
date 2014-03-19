import collections
import flask
import os

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
    # ("June 2012: GeneWeaver user publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/22371272\">Quantitative trait loci for sensitivity to ethanol intoxication in a C57BL/6Jx129S1/SvImJ inbred mouse cross.</a> Chesler EJ, Plitt A, Fisher D, Hurd B, Lederle L, Bubier JA, Kiselycznyk C, Holmes A. Mamm Genome 23(5-6):305-21"),
    # ("Apr 2012: GeneWeaver user publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/23123364\">Accelerating discovery for complex neurological and behavioral disorders through systems genetics and integrative genomics in the laboratory mouse.</a> Bubier JA, Chesler EJ. Neurotherapetuics. 9(2):338-48"),
    # ("Jul 2012: ISMB Presentation", "GeneWeaver was presented at ISMB 2012 in Long Beach, California (<a href=\"https://www.iscb.org/cms_addon/conferences/ismb2012/technologytrack.php\">TT32</a>). Thanks to everyone who attended! If you didn't get to talk to Jeremy, feel free to email any of us with questions. (addresses at the bottom of the page)"),
    # ("Jan 2012: GeneWeaver user publication", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/22239914\">Chloride intracellular channels modulate acute ethanol behaviors in Drosophila, Caenorhabditis elegans and mice.</a> Bhandari P, Hill JS, Farris SP, Costin B, Martin I, Chan CL, Alaimo JT, Bettinger JC, Davies AG, Miles MF, Grotewiel M. Genes Brain Behav. 2012 Jan 13."),
    # ("Oct 2011: Gene Weaver publication", "<a href=\"http://nar.oxfordjournals.org/content/40/D1/D1067.full\">GeneWeaver: A web-based system for integrative functional genomics.</a> Article in Nucleic Acids Research."),
    # ("Sep 2011: ODE renamed to Gene Weaver", "The Ontological Discovery Environment has been renamed to Gene Weaver, to better articulate our features and tools. <a href=\"http://ontologicaldiscovery.org/index.php?action=help&cmd=view&docid=faq\">Read more about the change.</a>"),
    # ("Jul 2011: ISMB Presentation", "A short talk and poster was presented at <a href=\"http://www.iscb.org/ismbeccb2011\">ISMB 2011</a> in Vienna, Austria."),
    # ("Apr 2011: Autism article using ODE", "<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/21397722\">Autism candidate genes via mouse phenomics. Journal of Biomedical Informatics.</a> This paper illustrates the use of the Ontological Discovery Environment to augment a set of known disease related genes with predictions of disease associated genes."),
    # ("Mar 2011: Database Update", "ODE now contains <i>C. elegans</i> and <i>Saccharomyces cerevisiae S288c</i> gene identifiers and Affymetrix arrays."),
    # ("Jan 2011: Full Database Update", "ODE has had a full update to the newest gene identifiers and ontologies. Please note that some sets or analysis results may change due to new genes and/or new homology information."),
    # ("Dec 2010: GO/MP Ontologies updated", "Gene Ontology and Mammalian Phenotype GeneSets have been updated, and now also include indirect associations. If you have the old sets in your projects, use the provided icon to transition to the new data."),
    # ("Nov 2010: Presentations", "ODE presented at the 2010 Society for Neuroscience Annual Meeting, and the NIDA 2010 Frontiers in Addiction Research."),
    # ("Sep 2010: New Microarrays Added", "New Microarrays have been added. Our process has also been streamlined to pull <a href=\"http://www.ncbi.nlm.nih.gov/geo/query/browse.cgi?mode=findplatform\">GEO Platform definitions</a>. If you would like to see a specific GPL, please <a href=\"index.php?action=help&cmd=report\">request it</a>."),
    # ("Aug 2010: New Tutorial", "A new <a href=\"docs/tutorial.pdf\">ODE Tutorial</a> was made for the Short Course on Genetics of Addiction at the Jackson Laboratory."),
    # ("Jul 2010: Upcoming presentation", "ODE at the Workshop on Informatics for Data and Resource Discovery in Addiction Research"),
    # ("Jun 2010: Upcoming presentation", "ODE at the NIAAA Systems Biology satellite to the Research Society on Alcoholism Annual Meeting"),
    # ("Mar 2010: Large Data Set Available", "Gene expression to behavior correlates from 7 brain regions and 250 behavioral phenotypes in both sexes added to ODE (<a href=\"http://www.ncbi.nlm.nih.gov/pubmed/19958391\">Philip et al, 2010</a>)."),
    # ("Sep 2009: ODE paper published", '<a href="http://www.ncbi.nlm.nih.gov/pubmed/19733230">"ODE: A system for integrating gene-phenotype associations"</a> paper published in Genomics.'),
    # ("Sep 2009: Rhesus Macaque added", 'Genes and the Affymetrix microarray for Rhesus Macaque (Macaca mulatta) have been added to ODE.'),
    # ("Aug 2009: Gene Database Updated", "Our database has been updated to include the most recent NCBI data, and we now include many genes directly from species' respective genome databases. Updates will continue regularly."),
    # ("Jul 2009: New ODE Demo Video", "There is a new <a href='/docs/video/'>Demo Video</a> available to walk you through the ODE website and tools."),
    # ("Jun 2009: New GeneSet Upload page available", "This beta Upload page will hopefully make it easier to get data sets into ODE."),
    # ("Mar 2009: ODE presented at the UT-ORNL-KBRIN Bioinformatics Summit", "Improvements and new features of the ODE tools were presented at the 2009 Bioinformatics Summit"),
    # ("Nov 2008: ODE presented at the IMGC", "ODE tools were presented at the 22nd annual International Mammalian Genome Conference in Prague, Czech Republic"),
    # ("Oct 2008: Stastical Analysis of HiSim Graphs", "We now calculate p-values for all HiSim Graphs generated on the ODE"),
    # ("Jul 2008: Many New GeneSets uploaded, More Species", "TMGC gene expression correlates to behavior and MP terms are now available in the database, and we now support 5 different species: Mouse, Rat, Human, Zebrafish, and Fly"),
    # ("Mar 2008: Ontology Annotation tool", "You can now annotate your GeneSets with ontologies available from the OBO."),
    # ("Feb 2008: New Design and Layout", "New design featuring re-organized site structure, drop-down menus, wider layout, and prettier pages."),
    # ("Jul 2007: First public release of the ODE.", "Welcome."),
    # ("Aug 2006: First Version of <i>Ontological Discovery Environment</i> released", "This is the initial release of the website for the ODE project. <i>Festina lente</i>."),
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

@app.route('/index.html')
def render_home_template():
    print 'cmd=', get_cmd()
    print flask.render_template('index.html')
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
