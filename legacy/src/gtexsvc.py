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

    def __init__(self):
        # type of execution
        self.SINGLE_TISSUE = False
        self.MULTI_TISSUE = True

        # urls for download + search [make a version control checker, as gtex provides options
        #   e.g {"status": 404, "message": "Not Found. You have requested this URI [/v6.3/tissues]
        #           but did you mean /v6.2/tissues or /v6/tissues or /v2/tissues ?"}
        # IDEA: try v6.3 and backtrack?
        self.GTEx_VERSIONS = ['v6', 'v6.2']
        self.SINGLE_TISSUE_INFO_URL = 'http://gtexportal.org/api/v6.2/tissues?username=Anonymous&_=1461355517678&v=clversion'
        self.MULTI_TISSUE_INFO_URL = None
        # ^ needs most up-to-date version of GTEx database, see above for specs on how

        # (updated for Version 6.2 of GTEx data [April 2016]) ^ also relevant
        self.STATIC_TISSUES = []  # list of tissue headers drawn directly from GTEx Portal (where n>=70)
        self.single_tissue_symbols = []
        self.multi_tissue_symbols = []

        # user-interface
        self.crit = []
        self.noncrit = []

        # data processing fields
        self.raw_data = {}  # {tissue_name: values,}  -  values[0] = headers, values[1+] = raw data
        self.tissue_info = {}  # stores data pulled in get_tissue_info()
        self.tissue_types = {}  # {abbrev_name: full_name,}  -  dictionary of all curated GTEx tissues, full + abbrev
        self.gene_info = {}  # USAGE: {gene_symbol: gene info,}

        self.single_tissue_data = {}  # USEAGE: {tissue_name: GTExGeneSet obj,}
        self.multi_tissue_data = {}

        self.get_tissue_info()  # populates: 'self.STATIC_TISSUES', + builds 'self.tissue_info'
        self.get_tissues_nomen()  # populates: self.tissue_types

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

        if type(critical) == (list or tuple):
            for error in critical:
                self.crit.append(error)
                crit_count += 1
        elif type(critical) == str:
            self.crit.append(critical)
            crit_count += 1

        if type(noncritical) == (list or tuple):
            for n in noncritical:
                self.noncrit.append(n)
                noncrit_count += 1
        elif type(noncritical) == str:
            self.noncrit.append(noncritical)
            noncrit_count += 1

        # USER FEEDBACK
        # if crit_count:
        #     print "Critical error messages added [%i]\n" % crit_count
        # if noncrit_count > 0:
        #     print "Noncritical error messages added [%i]\n" % noncrit_count

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

            # iterates through each tissue, instead of 'All', in order to distinguish strong sets (that GTEx
            has precomputed)

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

            self.STATIC_TISSUES = map(lambda l: str(l), list(temp))

            for header in self.STATIC_TISSUES:
                self.tissue_info[header] = {str(key): str(values) for key, values in temp[header].iteritems()}

        if tissue:
            return tissue, self.tissue_info[tissue]
        else:
            return self.tissue_info  # return complete dictionary unless otherwise specified

    # -------------------------- SETUP - UPLOADER HANDLING  ----------------------------------------------------------#

    @staticmethod
    def search_gene_info(gene_symbol):
        """ ### Uses params to pull gene-associated info: basic gene info, significant single-tissue eQTLs per gene,
            METASOFT eQTL posterior probabilities for gene, multi-tissue eQTL posterior probabilities for gene,
            splice QTLs (sQTLSeekeR) for gene, protein truncating variants for gene. [Not all ideas need to be
            acted upon. ###

            # might be a useful way to search GTEx

            # assumes input is a string (+ GTEx Portal Gene Symbol)

            # returns info in a dictionary

        Parameters
        ----------
        gene_symbol: string representing the 'name' of the gene
        """
        gene_search = 'http://gtexportal.org/api/v6/geneId/%s?_=1461862131014&v=clversion' % gene_symbol
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['genes'][0]

        # print "%s data pulled from GTEx Portal\n" % gene_symbol

        return output

    def search_single_tissues(self, tissue):
        """ Returns a dataset containing all the results for a tissue query search. ##

            # assumes that tissue is in GTEx tissue 'label' format, not 'title' (but could try both ways)
            # returns none if sample size too small

        Parameters
        ----------
        tissue: string representing GTEx label format

        Returns
        -------
        tissue: param intput (string)
        output: dictionary of eGene data for respective tissue input
        """
        try:
            numResults = int(self.tissue_info[tissue]['eGene_count'])
        except ValueError:
            err = "Warning: %s has not been added, due to small sample size (n<70).\n" % tissue
            self.set_errors(noncritical=err)
            return None

        # use the link below to target the exact data you want in json format [tissue label, num results]
        tissue_search = "http://gtexportal.org/api/v6/egenes/%s?draw=1&columns=&order=&start=0&length=%i" \
                        "&search=&sortDirection=1&_=1461355517690&v=clversion" % (tissue, numResults)
        r = requests.get(tissue_search).content
        temp = json.loads(r)  # nested dicts
        output = temp['data']

        print "%s data pulled from GTEx Portal release '%s'\n" % (tissue, temp['release'])
        return output

    def search_single_tissue_eQTLs(self, tissue, gene_symbol):
        """  ## returns entire single-tissue dataset for gene symbol entered, across all datasets

        Parameters
        ----------
        gene_symbol
        tissue
        """
        gene_search = 'http://gtexportal.org/api/v6/singleTissueEqtl?geneId=%s&tissueName=%s&username=anonymous&_=1461862131015&v=clversion' % (gene_symbol, tissue)
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['singleTissueEqtl']

        return output

    def search_multi_tissue_eQTLs(self, tissue):
        """ ## returns entire multi-tissue dataset for gene symbol entered """

        gene_search = 'http://gtexportal.org/api/v1/multiTissueEqtl?tissue=Uterus&username=anonymous&_=1461862131016&v=clversion' % gene_symbol
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['multiTissueEQTL']

        return output

    @staticmethod
    def search_gene_rank(self, tissue):
        """ ## Ranks genes by signficance per tissue

        Parameters
        ----------
        self
        tissue

        Returns
        -------

        """
        gene_search = 'http://gtexportal.org/api/v6/geneRanks?tissueId=%s&username=anonymous&_=1461862131023&v=clversion' % tissue
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['multiTissueEQTL']

        return output

    # -------------------------- DATABASE SETUP  ---------------------------------------------------------------#
    # use the below to provide additional eQTL? or just update this too?

    def database_setup(self):
        """ ### Gathers data from online resources. Returns something that
            upload_data nad upload_dataset can deal with ###

            only use is to set up geneweaver's database (should be done only once)

            # sets where strength is too low (n<70) are not included

        """
        # SINGLE-TISSUE SEARCH [add multi-tissue to the exact same inital framework when ready]
        symbols = []
        for tissue in self.tissue_info:  # create all genes
            if self.SINGLE_TISSUE:
                single_data = self.search_single_tissues(tissue)  # search for eGenes for each single-tissue expression
                if single_data:  # only including strong datasets (n>70)
                    # create GTExGeneSet obj, + respective eGenes
                    gs_single_tissue = GTExGeneSet(self, values=single_data, tissue_type=str(tissue))
                    # gs_single_tissue = gs_single_tissue.update_genes()  # uncomment if you want to upload qtls too
                    self.single_tissue_data[str(tissue)] = gs_single_tissue  # update global list of single-tissue data
                    symbols = list(set(symbols + gs_single_tissue.symbol_headers))  # keep track of all significant eGenes
                    # call geneweaver upload

            elif self.MULTI_TISSUE:
                multi_data = self.search_multi_tissue_eQTLs(tissue)  # search for eGenes for each multi-tissue comparison
                # pass data through structure
                # call geneweaver upload
                # add to multi_tissue_symbols
                # add to multi_tissue_data

        self.single_tissue_symbols = symbols

# Uses a "trickle-down" method for uploading
# add error handling that you can push back up to Uploader
class GTExGeneSet:  # GTExGeneSetUploaders
    """ ## Acts as the uploader interface for GTEx and GW
        ## specify param types, what happens, and how it passes info along

    """
    def __init__(self, type, parent, values, classifiers=None, tissue_type=None):  # assumes a user file input

        # all the database startup stuff goes here
        self.batch = parent

        # init for globals - check input types for error catching
        self.raw_values = values
        self.tissue = tissue_type  # might need to change with the multi-tissue option
        self.headers = classifiers  # sort out which kind of classifiers are being supplied BEFORE

        self.e_genes = {}  # USAGE: {gencode_id: eGene obj,}  -  gencode Id is tissue dependent
        self.e_qtls = {}  # USAGE: {snp: eQTL obj,} - for top-level access (otherwise already stored in eGene obj)

        self.symbol_headers = []
        self.gene_ref = {}  # USAGE: {gene_symbol: {gene info},}

        # data formatting checked here
        # check to make sure values is a list, adding error messages as necessary

        self.geneweaver_setup()
            # update self.headers

        # OTHERWISE: put them into the Gene objs for reference? Would need to write a similar method,
        #   just w/out the calls to upload

    def update_genes(self):

        for gene_name, gene_obj in self.e_genes.iteritems():
            updated = gene_obj.update_qtls()
            self.e_genes[gene_name] = updated

        return self

    # ----------------------------- MUTATORS ---------------------------------------- #

    # ----------------------------- GENEWEAVER SETUP ----------------------------- #
    def geneweaver_setup(self):
        """ Preps upload if setting up database.  ##
        """

        # or simplify this, and leave eQTL creation to eGene obj
        # and access / populate 'self.eQTLs' through eGenes

        # SINGLE-TISSUE ONLY - pulled directly from GTEx Portal pull
        if self.batch.SINGLE_TISSUE:
            symbols = []
            for gene_data in self.raw_values:
                gene_obj = eGene(self, data=gene_data)  # create gene
                self.e_genes[gene_obj.gencode_id] = gene_obj  # store globally
                symbols.append(gene_obj.gene_symbol)
            temp = set(self.symbol_headers + symbols)  # avoid duplicates
            self.symbol_headers = list(temp)

        elif self.batch.MULTI_TISSUE:
            pass

        # self.check_success()

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
            err = "Error: Duplicate Gencode IDs (per tissue) were found during upload [%s].\n" % dup
            self.batch.set_errors(critical=err)
            print self.batch.get_errors()
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

        self.parent = parent

        # remember to add a data check here for a dictionary type with all the right values
        self.raw_data = data  # decide what to do with this, needs checking if param data=None
        self.gencode_id = str(data['gencodeId'])
        self.gene_symbol = str(data['geneSymbol'])
        self.p_value = data['pValue']  # nominal p-value
        self.emp_pValue = data['empiricalPValue']  # empirical p-value
        self.q_value = data['qValue']
        self.tissue_name = str(data['tissueName'])

        self.all_data = [self.gencode_id, self.gene_symbol, self.p_value,
                         self.emp_pValue, self.q_value, self.tissue_name]

        # error handling
        self.crit = []
        self.noncrit = []

        # store subsequent eQTLs
        self.eQTLs = {}  # {name: eQTL obj,}

    def update_qtls(self):
        # SINGLE-TISSUE

        if self.parent.batch.SINGLE_TISSUE:
            gene_tissues = self.parent.batch.search_single_tissue_eQTLs(self.tissue_name, self.gene_symbol)

            for qtl_raw in gene_tissues:
                qtl = eQTL(parent=self, beta=qtl_raw['beta'], chromosome=qtl_raw['chromosome'],
                           p_value=qtl_raw['pValue'], snp_id=qtl_raw['snpId'], start=qtl_raw['start'])
                self.eQTLs[qtl_raw['snpId']] = qtl

        elif self.parent.batch.MULTI_TISSUE:
            pass

        return self


    # ------------------------- DATABASE MANAGEMENT / MUTATORS ---------------------- #
    def upload(self):
        # uploads material given -> GeneWeaver
        pass

class eQTL:
    """ Creates an eQTL object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """
    def __init__(self, parent, beta, chromosome, p_value, snp_id, start):

        # currently assumes a very specific data entry type if called
        self.parent = parent
        self.gtex_gs = parent.parent
        self.tissue_name = parent.tissue_name
        self.gencode_id = parent.gencode_id
        self.gene_symbol = parent.gene_symbol

        self.beta = beta
        self.chromosome = chromosome
        self.snp_id = snp_id
        self.start = start
        self.p_value = p_value

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

    g = GTEx()

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

def test_searchGeneInfo():
    g = GTEx()
    g.search_gene_info('PTPLAD2')

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
    # test_searchGeneInfo()

