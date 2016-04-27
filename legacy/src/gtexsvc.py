# author: Astrid Moore
# date: 4/14/16
# version: 1.0
#
# [Astrid's notes]
# The purpose of the following file is to manage GTEx batch data. The first goal is to find a way of piping
# GTEx data through a GTEx object (with Batch-like handling held here for now, until larger rewrite). The
# second goal is to be able query the website directly using 'requests'. The third goal is to be able to
# "plug-and-play" these data objects (like GTEx) straight into a Batch object.
# [describe format of file input]

import json
import requests  # downloads JSON files from web
import collections as c


# class Batch

# could make this of a new class - "Uploader" - to act as a GTEx-specific Uploader so that we can
#   differentiate between PubMed input types ect., helping with version control + establishment of
#   reference objs

# treat as if a "Data" object
class GTEx:
    """ Creates a GTEx object representative of significant 'eGenes' drawn from
        GTEx Portal [http://www.gtexportal.org/home/eqtls]

        If a tissue type is specified, search pulls significant 'eGenes' for that
        tissue.
    """

    def __init__(self, setup=False):
        # type of execution
        self.SETUP = setup

        # urls for download + search [make a version control checker, as gtex provides options
        #   e.g {"status": 404, "message": "Not Found. You have requested this URI [/v6.3/tissues]
        #           but did you mean /v6.2/tissues or /v6/tissues or /v2/tissues ?"}
        # IDEA: try v6.3 and backtrack?
        self.GTEx_VERSIONS = ['v6', 'v6.2']
        self.SINGLE_TISSUE_INFO_URL = 'http://gtexportal.org/api/v6.2/tissues?username=Anonymous&_=1461355517678&v=clversion'
        self.MULTI_TISSUE_INFO_URL = None
        # ^ needs most up-to-date version of GTEx database, see above for specs on how

        # (updated for Version 6.2 of GTEx data [April 2016]) ^ also relevant
        self.STATIC_TISSUES = ['All']  # populated with call to 'self.get_tissue_info()'

        # errors
        self.crit = []
        self.noncrit = []

        # data processing fields
        self.raw_data = {}  # {tissue_name: values,}  -  values[0] = headers, values[1+] = raw data
        self.raw_headers = []  # list of GTEx classifers
        self.tissue_info = {}  # stores data pulled in get_tissue_info()
        self.tissue_types = {}  # {abbrev_name: full_name,}  -  dictionary of all curated GTEx tissues, full + abbrev

        self.single_tissue_data = {}  # USEAGE: {tissue_name: GTExGeneSet obj,}
        self.multi_tissue_data = {}

        self.get_tissue_info()  # populates: 'self.STATIC_TISSUES', + builds 'self.tissue_info'
        self.get_tissues_nomen()  # populates: self.tissue_types

        if self.SETUP:
            self.database_setup()

        # otherwise, use this as a reference obj / way to make sure GeneWeaver has the most recent version

    # --------------------------------- MUTATORs ------------------------------------------------- #

    def get_errors(self, critical=False, noncritical=False):
        """ Returns error messages. If no additional parameters are filled, or if both
            'crit' and 'noncrit' are set to 'True', both critical and
            noncritical error messages are returned for the user.

            Otherwise, if either 'crit' or 'noncrit' are set to 'True', only that
            respective error type will be returned.

        Parameters
        ----------
        crit (optional): boolean
        noncrit (optional): boolean

        Returns
        -------
        critical (optional): list of critical error messages generated [self.crit]
        noncritical (optional): list of noncritical error messages generated [self.noncrit]
        """
        if critical and noncritical:
            return self.crit, self.noncrit
        elif critical:
            return self.crit
        elif noncritical:
            return self.noncrit
        else:
            return self.crit, self.noncrit

    def set_errors(self, critical=None, noncritical=None):
        """ Sets error messages, printing confirmation when new errors are added. Parameters
            'crit' and 'noncrit' can take either a string, appended onto respective global
            variable, a list or a tuple. In the case that a list or tuple is provided, function
            iterates through and appends to global error messages accordingly.

        Parameters
        ----------
        critical: string or list
        noncritical: string or list
        """
        crit_count = 0
        noncrit_count = 0

        if type(critical) == list or type(critical) == tuple:
            for c in critical:
                self.crit.append(c)
                crit_count += 1
        else:
            self.crit.append(critical)
            crit_count += 1

        if type(noncritical) == list or type(noncritical) == tuple:
            for n in noncritical:
                self.noncrit.append(n)
                noncrit_count += 1
        else:
            self.noncrit.append(noncritical)
            noncrit_count += 1

        if crit_count:
            print "Critical error messages added [%i]\n" % crit_count
        if noncrit_count > 0:
            print "Noncritical error messages added [%i]\n" % noncrit_count

    def get_tissues_nomen(self):
        """ Returns a dictionary of all tissues listed in GTEx portal eQTL resource. For each tissue,
            an abbreviated 'label' is mapped against a full 'title'.

            Returns
            -------
            self.tissue_types: dictionary of GTEx curated tissue types {abbrev_label: full_label,}
        """
        for header in self.STATIC_TISSUES:
            self.tissue_types[header] = self.tissue_info[header]['tissue_name']

        return self.tissue_types

    def list_all_tissues(self, label=False, title=False):
        """ Returns a list of tissue names that have been processed for querying. If 'label', returns a list
            GTEx tissue labels that contain no whitespace or additional information [e.g. "Whole_Blood"]. If
            'title', returns a list of full titles that match the options given for GTEx Portal's eQTL
            service [e.g. "Whole Blood (n=338)"].

            If no params entered, returns a list of GTEx tissue labels. If both params set to 'True',
            returns two lists, one for each respective name (label, title).

            In the case that the user wants a list of the full name tissue type labels [e.g. "Whole Blood (n=338)"]
            instead of "Whole_Blood"], but 'self.tissue_types' hasn't been populated, calls 'get_tissues_nomen()'
            to build this dictionary.

        Parameters
        ----------
        label: boolean indicative of return type style (tissue labels with no whitespace or additional info)
        title: boolean indicative of return type style (full tissue titles)

        Returns
        -------
        output_labels: list of current GTEx tissues ['label' type]
        output_titles: list of current GTEx tissues ['title' type]

        """
        temp_full = []

        # make sure that tissue label reference dictionary is populated
        if not self.tissue_types:
            self.get_tissues_nomen()

        if not (label or title) or (label and not title):
            return self.raw_data.keys()
        elif title and not label:
            for key in self.raw_data.keys():
                temp_full.append(self.tissue_types[key])
            return temp_full
        else:
            for key in self.raw_data.keys():
                temp_full.append(self.tissue_types[key])
            return self.raw_data.keys(), temp_full

    # --------------------------- PORTAL QUERY FUNCTIONS (version control) -------------------------------------- #
    # if setup -> create criteria to iterate over
    # otherwise -> use as a data object for Batch

    def check_version(self):
        # check to see if the version stored matches the version on GTex
        pass

    def get_tissue_info(self, tissue=None):
        """ Retrieves GTEx tissue information. If no tissue is specified in the parameters, it populates
            'self.STATIC_TISSUES', and builds 'self.tissue_info'. If a tissue is specified, assumes that
            the tissue is GTEx and the label is abbreviated [e.g. "Whole_Blood"].

            Assumes param 'tissue' is an existing GTEx 'label'. Control a user's functional access at top
            level.

            Dictionary structure for 'self.tissue_info' is such that:
                {tissue_name: {'has_genes': boolean, 'expressed_gene_count': int, 'tissue_color_hex': str,
                'tissue_abbrv': str, 'tissue_name': str, 'tissue_id': str, 'tissue_color_rgb': str,
                'eGene_count': int, 'rna_seq_sample_count': int, 'rna_seq_and_genotype_sample_count': int},}

        Parameters
        ----------
        tissue: string representing GTEx label format

        Returns
        -------
        tissue, self.tissue_info[tissue]: input string, tissue info  -  if 'tissue'
        self.tissue_info: dictionary of all tissues + respective info  -  if not 'tissue'
        """

        if not self.tissue_info:
            r = requests.get(self.SINGLE_TISSUE_INFO_URL).content
            temp = json.loads(r)  # nested dicts
            self.STATIC_TISSUES = map(lambda l: str(l), list(temp))  # list of headers to iterate through dictionary

            for header in self.STATIC_TISSUES:
                self.tissue_info[header] = {str(key): str(values) for key, values in temp[header].iteritems()}

        if tissue:
            return tissue, self.tissue_info[tissue]
        else:
            return self.tissue_info  # return complete dictionary unless otherwise specified

    # def search_gene_info(self, gene_symbol=None):
    #     """ ### Uses params to pull gene-associated info: basic gene info, significant single-tissue eQTLs per gene,
    #         METASOFT eQTL posterior probabilities for gene, multi-tissue eQTL posterior probabilities for gene,
    #         splice QTLs (sQTLSeekeR) for gene, protein truncating variants for gene. [Not all ideas need to be
    #         acted upon. ###
    #
    #         if none, returns all results
    #
    #         for use when users upload files later
    #
    #     Parameters
    #     ----------
    #     gene_symbol: string representing the 'name' of the gene
    #     """
    #     # grab data from something like this / find source files:
    #     search = "http://www.gtexportal.org/home/gene/EFCAB2"
    #     # + find a way to make these searches more flexible (using their original source code)
    #     pass

    # -------------------------- SETUP - UPLOADER HANDLING  ----------------------------------------------------------#

    def search_single_tissues(self, tissue):
        """ Returns a dataset containing all the results for a tissue query search. ##

            # assumes that tissue is in GTEx tissue 'label' format, not 'title' (but could try both ways)

        Parameters
        ----------
        tissue: string representing GTEx label format

        Returns
        -------
        tissue: param intput (string)
        output: dictionary of eGene data for respective tissue input
        """
        numResults = int(self.tissue_info[tissue]['eGene_count'])
        # use the link below to target the exact data you want in json format [tissue label, num results]
        tissue_search = "http://gtexportal.org/api/v6/egenes/%s?draw=1&columns=&order=&start=0&length=%i" \
                        "&search=&sortDirection=1&_=1461355517690&v=clversion" % (tissue, numResults)
        r = requests.get(tissue_search).content
        temp = json.loads(r)  # nested dicts
        output = temp['data']

        print "%s data for GTEx release '%s'\n" % (tissue, temp['release'])
        return output

    def search_multi_tissues(self, gene):  # need to figure out what you mean exactly by 'gene'
        """ ## returns entire multi-tissue dataset """

        # find location again for this JSON datatable
        pass
    # -------------------------- DATABASE SETUP  ---------------------------------------------------------------#
    # use the below to provide additional eQTL? or just update this too?
    def database_setup(self):
        """ ### Gathers data from online resources. Returns something that
            upload_data nad upload_dataset can deal with ###

            only use is to set up geneweaver's database (should be done only once)

        """
        print "starting database_setup for single-tissue expression\n"
        not_working = []
        for tissue in self.tissue_info:  # self.tissue_info (populated in 'init')
            try:
                tissue_data = self.search_single_tissues(tissue)  # search for eGenes for each tissue
                gs_single_tissue = GTExGeneSet(self, values=tissue_data, tissue_type=str(tissue))
                self.single_tissue_data[str(tissue)] = gs_single_tissue
            except:
                # print "nope: %s\n" % tissue
                not_working.append(tissue)

        print not_working
        print self.STATIC_TISSUES

        # this is missing those with too small of sets

# Uses a "trickle-down" method for uploading
# add error handling that you can push back up to Uploader
class GTExGeneSet:  # GTExGeneSetUploaders
    """ ## Acts as the uploader interface for GTEx and GW
        ## specify param types, what happens, and how it passes info along

    """
    def __init__(self, parent, values, classifiers=None, tissue_type=None):  # assumes a user file input

        # all the database startup stuff goes here
        self.batch = parent

        # init for globals - check input types for error catching
        self.raw_values = values
        self.e_genes = {}  # USAGE: {gene_symbol: eGene obj,}
        self.e_qtls = {}  # USAGE: {snp: eQTL obj,} - for top-level access (otherwise already stored in eGene obj)
        self.tissue = tissue_type  # might need to change with the multi-tissue option
        self.headers = classifiers

        # data formatting checked here
        # check to make sure values is a list, adding error messages as necessary

        if self.batch.SETUP:
            self.geneweaver_setup_handler()
            # update self.headers

        # OTHERWISE: put them into the Gene objs for reference? Would need to write a similar method,
        #   just w/out the calls to upload

    # ----------------------------- MUTATORS ---------------------------------------- #

    # ----------------------------- GENEWEAVER SETUP ----------------------------- #
    def geneweaver_setup_handler(self):
        """ Preps upload if setting up database.  ##
        """

        # or simplify this, and leave eQTL creation to eGene obj
        # and access / populate 'self.eQTLs' through eGenes

        # SINGLE-TISSUE ONLY - pulled directly from GTEx Portal pull
        gene_obj = None
        for gene_data in self.raw_values:
            gene_obj = eGene(self, data=gene_data)  # create gene
            self.e_genes[gene_obj.gencode_id] = gene_obj  # add to global variables

        self.check_success()

        # self.upload_all()

    def check_success(self):

        gencode_headers = []  # TEMP
        for gene in self.raw_values:  # TEMP
            gencode_headers.append(str(gene['gencodeId']))

        dup = []
        for item, count in c.Counter(gencode_headers).items():  # definitely not the fastest way to check, use sets
            if count > 1:
                dup.append(item)

        if len(dup):
            err = "Error: Duplicate Gencode IDs found during upload [%s].\n" % dup
            self.batch.set_errors(critical=err)
            self.batch.get_errors()
            exit()
        else:
            print "Yup\n"

    def upload_all(self):
        # uploads this geneset to GeneWeaver

        # for gene in self.e_genes
        #   gene.upload()

        # if there's a problem with this, add to errors
        # push errors up to Data parent

        pass

class eGene:
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, parent, data=None):

        self.GTExGS = parent

        # remember to add a data check here for a dictionary type with all the right values
        self.raw_data = data  # decide what to do with this, needs checking if param data=None
        self.gencode_id = str(data['gencodeId'])
        self.gene_symbol = str(data['geneSymbol'])
        self.pValue = data['pValue']  # nominal p-value
        self.emp_pValue = data['empiricalPValue']  # empirical p-value
        self.qValue = data['qValue']
        self.tissue_name = str(data['tissueName'])

        # error handling
        self.crit = []
        self.noncrit = []

        # store subsequent eQTLs
        self.eQTLs = {}  # {name: eQTL obj,}

    # ------------------------- DATABASE MANAGEMENT / MUTATORS ---------------------- #
    def upload(self):
        # uploads material given -> GeneWeaver
        pass

class eQTL:
    """ Creates an eQTL object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """
    def __init__(self, parent):

        # currently assumes a very specific data entry type if called
        self.e_gene_obj = parent
        self.gtex_gs = parent.parent

        self.gencode_id = None
        self.gene_symbol = None
        self.p_value = None
        self.effect_size = None
        self.tissue = None
        self.rs_id = None

        # variables = [self.snp, self.gene, self.beta, self.t_stat, self.se, self.p_value,
        #              self.nom_thresh, self.min_p, self.gene_emp_p, self.k, self.n,
        #              self.gene_q_value, self.beta_noNorm, self.snp_chrom, self.snp_pos,
        #              self.minor_allele_samples, self.minor_allele_count, self.maf,
        #              self.ref_factor, self.ref, self.alt, self.snp_id_1kg_project_phaseI_v3,
        #              self.rs_id_dbSNP142_GRCh37p13, self.num_alt_per_site, self.has_best_p,
        #              self.is_chosen_snp, self.gene_name, self.gene_source, self.gene_chr,
        #              self.gene_start, self.gene_stop, self.orientation, self.tss_position,
        #              self.gene_type, self.gencode_attributes, self.tss_distance]

        # pull all relevant information from parent, prepare for uploading

    # ------------------------- DATABASE MANAGEMENT / MUTATORS ---------------------- #
    def upload(self):
        # upload qtl to GeneWeaver
        pass


# --------------------------------------------- TESTs ----------------------------------------------------------#
def test_errors():
    """ Simple test of global error handling capabilites for GTEx obj.
    """
    print "TEST: Global error handling capabilites for GTEx obj:\n"

    test = GTEx()
    crit = ("Luke, I am your father.", "May the force be with you.")
    noncrit = "beepboop. boop."

    test.set_errors(critical=crit, noncritical=noncrit)
    results = test.get_errors()

    print "Value of global variable 'self.crit' %s\nshould match %s\n& %s\n" % (test.crit, crit, results[0])
    print "Value of global variable 'self.noncrit' %s\nshould match %s\n& %s\n" % (test.noncrit, noncrit, results[1])

def test_reading():
    """ Tests batch reading capabilites of GTEx obj (later make readGTExFile part of GTEx Batch handling).
    """
    print "TEST: Batch reading capabilites of GTEx obj:\n"

    g = GTEx()
    # g.get_data()

def test_query():
    """ Tests GTEx Portal data scraping.
    """
    print "TEST: GTEx data scraping.\n"

    g = GTEx()
    g.search_single_tissues(tissue="Uterus")  # ammend after full changes are made

    # results = g.search_GTEx(tissue="Uterus")  # ammend after full changes are made
    # print results  # add a better final print statement

def test_dbSetup():
    """ Tests the setup process for primary GeneWeaver upload."""

    g = GTEx(setup=True)

def test_getCurrTissue():
    """ Tests the functionality of get_curr_tissues(). """
    print "Tests the functionality of get_curr_tissues().\n"

    g = GTEx()
    g.raw_data = {'Thyroid': "placeholder", "Spleen": "placeholder", "Stomach": "placeholder"}

    # TEST CASES
    g.list_all_tissues()  # CASE 1
    g.list_all_tissues(label=True)  # CASE 2
    g.list_all_tissues(title=True)  # CASE 3
    g.list_all_tissues(label=True, title=True)  # CASE 4

    # EXPECTED OUTPUTS
    # CASE 1 = "abbrev: ['Thyroid', 'Stomach', 'Spleen']
    # CASE 2 = "abbrev: ['Thyroid', 'Stomach', 'Spleen']"
    # CASE 3 = "full: ['Thyroid (n=278)', 'Stomach (n=170)', 'Spleen (n=89)']"
    # CASE 4 = "abbrev + full!
    #           abbrev: ['Thyroid', 'Stomach', 'Spleen']
    #           full: ['Thyroid (n=278)', 'Stomach (n=170)', 'Spleen (n=89)']"

def test_getTissueInfo():
    """ Tests the functionality of get_tissue_info(). """

    g = GTEx()
    t = g.get_tissue_info()
    print t

    print "Passed\n"

if __name__ == '__main__':
    # ACTIVELY WRITING / DEBUGGING METHODS
    # test_reading()
    # test_query()
    test_dbSetup()

    # FUNCTIONING METHODS
    # test_errors()
    # test_getTissue()
    # test_getCurrTissue()
    # test_getTissueInfo()
