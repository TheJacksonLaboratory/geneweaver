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

from pyvirtualdisplay import Display
from selenium import selenium
from selenium import webdriver as wd  # launches + controls web browser
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time  # debugging purposes only

import json

from bs4 import BeautifulSoup  # parses HTML
import requests  # downloads files + web pages
import zipfile
import StringIO
import os


# could make this of a superclass - "Batch" to differentiate between PubMed ect
# treat as if a "Data" object
class GTEx:
    """ Creates a GTEx object representative of significant 'eGenes' drawn from
        GTEx Portal [http://www.gtexportal.org/home/eqtls]

        If a tissue type is specified, search pulls significant 'eGenes' for that
        tissue.
    """

    def __init__(self, tissue='All'):
        # local dataset filepaths
        self.ROOT_DIR = '/Users/Asti/geneweaver/gtex/datasets/v6/eGenes/GTEx_Analysis_V6_eQTLs/'  # change later
        self.SAVE_SEARCH_DIR = "/Users/Asti/geneweaver/gtex/gtex-results"  # change later

        # type of execution
        self.SETUP = True

        # urls for download + search [make a version control checker, as gtex provides options
        #   e.g {"status": 404, "message": "Not Found. You have requested this URI [/v6.3/tissues]
        #           but did you mean /v6.2/tissues or /v6/tissues or /v2/tissues ?"}
        # IDEA: try v6.3 and backtrack?
        self.GTEx_VERSIONS = ['v6', 'v6.2']
        self.BASE_URL = 'http://www.gtexportal.org/home/'
        self.DATASETS_INFO_URL = 'http://www.gtexportal.org/home/datasets'
        self.LOOKUP_URL = 'http://www.gtexportal.org/home/eqtls/tissue?tissueName=All'
        self.TISSUE_LOOKUP_URL = 'http://www.gtexportal.org/home/eqtls/tissue?tissueName='
        self.COMPRESSED_QTL_DATA_URL = 'http://www.gtexportal.org/static/datasets/gtex_analysis_v6/' \
                                       'single_tissue_eqtl_data/GTEx_Analysis_V6_eQTLs.tar.gz'
        self.TISSUE_INFO_URL = 'http://gtexportal.org/api/v6.2/tissues?username=Anonymous&_=1461355517678&v=clversion'
        # ^ needs most up-to-date version of GTEx database, see above for specs on how

        # (updated for Version 6.2 of GTEx data [April 2016]) ^ also relevant
        self.STATIC_TISSUES = ['All']

        # empty Display obj for headless browser testing
        self.display = Display(visible=1, size=(800, 600))
        self.profile = None  # placeholder for FirefoxProfile object

        # errors
        self.crit = []
        self.noncrit = []

        # data processing fields
        self.raw_data = {}  # {tissue: values,}  -  values[0] = headers, values[1+] = raw data
        self.raw_headers = []  # list of GTEx classifers
        self.tissue_info = {}  # stores data pulled in get_tissue_info()
        self.tissue_types = {}  # {abbrev_name: full_name,}  -  dictionary of all curated GTEx tissues, full + abbrev

        # self.tissue_pref = tissue  # need to check this entry in tissue_types before proceeding to organize tissue

        # SETUP
        # self.launch_FirefoxProfile()  # REMOVE
        self.get_tissue_info()  # populates: 'self.STATIC_TISSUES', + builds 'self.tissue_info'
        self.get_tissues_nomen()  # populates: self.tissue_types

    def update(self):
        # sets up all the variables needed [add to init + replace SETUP]
        pass

    def setup_uploader(self):
        # will probably end up containing content in database_setup() test method
        pass

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

    def check_tissue(self, tissue):
        """ Takes in a tissue label and checks that it is a known GTEx tissue. If it is a known
            tissue, returns 'True'. Otherwise, returns 'False', and adds a critical error message.

            Assumes that global list 'self.STATIC_TISSUES' has been populated (for now).

        Parameters
        ----------
        tissue: input tissue type (string)

        Returns
        -------
        exists: boolean indicative of inclusion among known GTEx tissue types
        """
        # check to make sure the file is labelled appropriately, + tissue is known GTEx tissue
        if tissue in self.STATIC_TISSUES:
            exists = True
        else:
            self.set_errors(critical="Error: The names of input files should contain the tissue type such"
                                     " that the format mimicks '<tissue_type>_Analysis.snpgenes'. Tissue"
                                     " must already exist among curated GTEx tissues, and contain no"
                                     " whitespace.\n")
            exists = False
        return exists

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

# --------------------------- ONLINE QUERY FUNCTIONS --------------------------------------------------------------- #
        # if setup -> create criteria to iterate over
        # otherwise -> use these to cross check user's file input

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
            r = requests.get(self.TISSUE_INFO_URL).content
            temp = json.loads(r)  # nested dicts
            self.STATIC_TISSUES = map(lambda l: str(l), list(temp))  # list of headers to iterate through dictionary

            for header in self.STATIC_TISSUES:
                self.tissue_info[header] = {str(key): str(values) for key, values in temp[header].iteritems()}

        if tissue:
            return tissue, self.tissue_info[tissue]
        else:
            return self.tissue_info  # return complete dictionary unless otherwise specified

    def search_tissues(self, tissue=None):
        """ Returns a dataset containing all the results for a tissue query search. ##

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
        return tissue, output

    def search_gene_symbol(self, gene_symbol=None):
        """ ### Uses params to pull gene-associated info: basic gene info, significant single-tissue eQTLs per gene,
            METASOFT eQTL posterior probabilities for gene, multi-tissue eQTL posterior probabilities for gene,
            splice QTLs (sQTLSeekeR) for gene, protein truncating variants for gene. [Not all ideas need to be
            acted upon. ###

            if none, returns all results

            for use when users upload files later

        Parameters
        ----------
        gene_symbol: string representing the 'name' of the gene
        """
        # grab data from something like this:
        search = "http://www.gtexportal.org/home/gene/EFCAB2"
        pass

    def search_GTEx(self, tissue=None, gencode_id=None, gene_symbol=None):
        """ Direct query search of GTEx, using the params provided ####

        Parameters
        ----------
        tissue
        gencode_id
        gene_symbol

        Returns
        -------
        tissue, temp['data']:
        """
        # search GTEx - use constituent methods to help build

        if tissue:  # used for get_data() query pull
            return self.search_tissues(tissue)

        # elif gencode_id:  # used for other query types
        # elif gene_symbol:
        # elif rsid:

    def update_resources(self):
        """ Pulls a list of files to use for GTEx initial setup [from source].
        """
        # # need to test this function when theres more space on comp - doesn't save locally, might also be an issue
        # r = requests.get(self.COMPRESSED_DATA_URL, stream=True)  # 'True' means that data in stream, not save actually
        # z = zipfile.ZipFile(StringIO.StringIO(r.content))
        # z.extractall()
        # r.ok()

        # code above not tested at all
        pass

    def update_annotations(self):
        """ Downloads annotations for each eGene attribute and phenotypic variable.
        """
        # need to login to get this feature
        # pull fileset from v6 release
        pass

    # -------------------------- UPLOADER HANDLING  ----------------------------------------------------------#

    def upload_data(self, data, tissue_name, headers):
        """ Greates a GTExGeneSet object that interfaces with the GeneWeaver database.

            # for uses other than initial db setup

        Parameters
        ----------
        tissue_name: type of tissue (string)
        headers:
        data:
        """
        if self.check_tissue(tissue_name):  # tissue type checked here, adds critical error if reached
            self.raw_data[tissue_name] = data[1:]  # store raw data per each tissue
            print self.raw_data
            egenes = []  # to store eGene objects

            if not self.raw_headers:
                self.raw_headers = headers  # store raw headers

                # pass data to GTExGeneSet for upload to database
                # gtex_upload = GTExGeneSet(self, data, tissue_type=tissue_name)

                # for gene in self.raw[tissue_name]:
                #     for pos in range(len(self.raw_headers)):
                #         # g = GTExGeneset(gene, tissue_name)  # create an eGene
                #         # eGenes.append(g)
                #         print gene
                #         break  # for editing purposes only
                #     break

    def upload_dataset(self, dataset, tissue_name, headers):
        """ Initializes significant eGenes from GTEx Portal. Creates eGene objects for
            each significant gene. ## add distinct file options

            # for uses other than initial db setup
        """
        # use get_data to retrieve what you want to upload

        # iterate through each eSNP line of the data, calling upload_data()
        # if dealing with hard files -------------------------------- #
        #   SEE - GTEx Data Structure: Dataset in NOTES
        # for each eSNP line of data
        # self.upload data(raw_data, tissue_name, raw_headers)  # REMEMBER: assumes SNPs [documentation+]

        # if working with online resources -------------------------- #
        #   SEE - GTEx Data Structure: Dataset in NOTES
        page = None
        # walk through each tissue in tissue_info{}
        # use search_GTEx to gather info

        # depending on 'save' parameter, save under tissue format (give get_data some use)
        #   SEE - GTEx Data Structure: Dataset in NOTES

        # using the inputs, search GTEx Portal using requests
        # with requests.Session() as session:
        #     page = session.get(self.LOOKUP_URL)
        pass

    # -------------------------- DATABASE SETUP  ---------------------------------------------------------------#
    # use the below to provide additional eQTL? or just update this too?
    @staticmethod
    def readGTExFile(fp):
        """ Reads the file at the given filepath and returns tissue name (provided by the filename),
            geneset classifiers and related data.

        Parameters
        ----------
        fp: filepath to read (string)

        Returns
        -------
        tissue_name: name of tissue type for eGene (string)
        temp_headers: list of all classifiers for eGene
        temp_data: list of data for each eGene
        """
        # add this method to class batch later!
        temp_headers = []  # list of geneset classifiers
        temp_data = []  # list of geneset values

        with open(fp, 'r') as file_path:
            lines = file_path.readlines()
            tissue_name = file_path.name  # name is full filepath
            tissue_name = tissue_name.strip().split("/")[-1][:-18]  # grab the tissue type from the filepath

        count = 0  # placeholder for temp_headers
        for data in lines:
            data = data.splitlines()
            for datum in data:
                if count == 0:
                    temp_headers = datum.strip().split("\t")  # grab eGene classifiers
                    count += 1
                else:
                    temp_data.append(datum.strip().split("\t"))  # grab eGene dataset

        return tissue_name, temp_headers, temp_data

    def databse_setup(self, hard=None, online=None):
        """ ### Gathers data from hard files, or from online resources. Returns something that
            upload_data nad upload_dataset can deal with ###

            only use is to set up geneweaver's database (should be done only once)

        """
        gtex_sets = {}
        # if this is how you decide to leave it, make sure that you're linking the appropriate headers
        # and stuff, otherwise this may as well be its own class!

        # if dealing with hard files -------------------------------- #
        if hard:
            for fileList in os.walk(self.ROOT_DIR):
                for tissueFile in fileList[2]:
                    if tissueFile == 'Uterus_Analysis.snpgenes':  # TEMPORARY: only for testing purposes
                        tissue_name, raw_headers, raw_data = self.readGTExFile(self.ROOT_DIR + tissueFile)
                        g = GTExGeneSet(values=raw_data, tissue_type=tissue_name, batch='hard_file')
                        gtex_sets[tissue_name] = g

        # if working with online resources -------------------------- #
        elif online:
            pass
            # walk through each tissue in tissue_info{}
            # use search_GTEx to gather info
        return gtex_sets


# essentailly a model of an Uploader? Uses a "trickle-down" method for uploading ---------------------------------
# add error handling
class GTExGeneSet:
    """ ### Acts as the uploader interface for GTEx and GW ###
            specify param types, what happens, and how it passes info along

    """
    # right now, per tissue for setup hard_file

    def __init__(self, values, tissue_type=None, batch='file'):  # assumes a user file input
        # file = values are from a user file for SQL upload to GeneWeaver
        # [DEV] hardFile = values are from a database setup file
        # online = values are from direct online queries (see GTEx)

        # all the database startup stuff goes here

        self.raw_values = values
        self.batch_type = batch  # DELETE? currently - tissues
        self.eGenes = {}
        self.eQTLs = {}
        self.tissue = tissue_type

        # data formatting checked here
        # check to make sure values is a list, adding error messages as necessary
        if self.batch_type == 'hard_file':
            # create eGene objects, storing in self.eGenes
            # create eQTL objects, storing in self.eQTLs

            self.snp, self.gene, self.beta, self.t_stat, self.se, self.p_value, \
                self.nom_thresh, self.min_p, self.gene_emp_p, self.k, self.n, \
                self.gene_q_value, self.beta_noNorm, self.snp_chrom, self.snp_pos, \
                self.minor_allele_samples, self.minor_allele_count, self.maf, \
                self.ref_factor, self.ref, self.alt, self.snp_id_1kg_project_phaseI_v3, \
                self.rs_id_dbSNP142_GRCh37p13, self.num_alt_per_site, self.has_best_p, \
                self.is_chosen_snp, self.gene_name, self.gene_source, self.gene_chr, \
                self.gene_start, self.gene_stop, self.orientation, self.tss_position, \
                self.gene_type, self.gencode_attributes, self.tss_distance = None

            self.geneweaver_setup_handler()  # if entry type is per tissue, as tissue type must be provided
            # pull all relevant information from parent, prepare for uploading (as a geneset)

        elif self.batch_type == 'online':
            # create eGene objects, storing in self.eGenes
            self.online_handler()

        elif self.batch_type == 'file':
            self.file_handler()

    def geneweaver_setup_handler(self):
        """ Preps upload if using hard files to upload data.
        """
        # IF: format of file such that values listed as snps, in GTEx formatting (from tissue file)
        # NOTE: below has not been tested
        if len(self.raw_values) == 36:

            # additional values (if needed later on)
            variables = [self.snp, self.gene, self.beta, self.t_stat, self.se, self.p_value,
                         self.nom_thresh, self.min_p, self.gene_emp_p, self.k, self.n,
                         self.gene_q_value, self.beta_noNorm, self.snp_chrom, self.snp_pos,
                         self.minor_allele_samples, self.minor_allele_count, self.maf,
                         self.ref_factor, self.ref, self.alt, self.snp_id_1kg_project_phaseI_v3,
                         self.rs_id_dbSNP142_GRCh37p13, self.num_alt_per_site, self.has_best_p,
                         self.is_chosen_snp, self.gene_name, self.gene_source, self.gene_chr,
                         self.gene_start, self.gene_stop, self.orientation, self.tss_position,
                         self.gene_type, self.gencode_attributes, self.tss_distance]

            for v in range(len(self.raw_values)):
                variables[v] = self.raw_values[v]
        else:
            # add error message
            print "nope\n"
            pass
            # create one gene and snp at a time, so iterate through each line

    def online_handler(self):
        """ Preps upload if using GTEx source to upload data. """
        # slightly different format? or should aim to do it all?
        # might be useful for making genesets for users - for cross checking?
        pass

    def file_handler(self):
        """ Preps upload if using user-input file as a source for data uploading. """
        # slightly different format? or should aim to do it all?
        # might be useful for making genesets for users - for cross checking?
        pass

    def create_genes(self):
        """ eGene object init
        """
        # create eGene
        pass

    def create_qtls(self):
        """ eQTL object init"""
        pass

    def upload_genes(self):
        """ Uploads to GW DB using SQl"""
        pass

    def upload_qtls(self):
        """ Uploads to GW DB using SQL"""
        pass

class eGene(GTExGeneSet):
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, parent):
        GTExGeneSet.__init__(self, values=None, tissue_type=None)

        self.parent = parent

        # core values being used - REMEMBER: pass along from parent, don't leave these as 'None'
        self.gencode_id = None
        self.gene_symbol = None
        self.nom_pValue = None
        self.emp_pValue = None
        self.qValue = None
        self.tissue_name = None  # add tissue_type here, make sure to type first

        # error handling
        self.crit = []
        self.noncrit = []

        # store subsequent eQTLs
        self.eQTLs = {}  # {name: eQTL obj,}

        # pull all relevant information from parent, prepare for uploading

class eQTL(eGene):
    def __init__(self, parent):
        eGene.__init__(self, parent)

        # currently assumes a very specific data entry type if called
        self.parent = parent
        self.gencode_id = None
        self.gene_symbol = None
        self.p_value = None
        self.effect_size = None
        self.tissue = None

        self.rsid = None

        # pull all relevant information from parent, prepare for uploading


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
    g.get_data()


def test_query():
    """ Tests GTEx Portal data scraping.
    """
    print "TEST: GTEx data scraping.\n"

    g = GTEx()
    g.search_GTEx(tissue="Uterus")  # ammend after full changes are made

    # results = g.search_GTEx(tissue="Uterus")  # ammend after full changes are made
    # print results  # add a better final print statement

def test_dbSetup():
    """ Tests the setup process for primary GeneWeaver upload."""

    g = GTEx()
    result = g.setup


def test_getTissue():
    """ Tests the functionality of get_tissue_types(). """
    print "TEST: Functionality of get_tissue_types().\n"

    g = GTEx()
    g.get_tissue_types()


def test_getCurrTissue():
    """ Tests the functionality of get_curr_tissues(). """
    print "Tests the functionality of get_curr_tissues().\n"

    g = GTEx()
    g.raw_data = {'Thyroid': "placeholder", "Spleen": "placeholder", "Stomach": "placeholder"}

    # TEST CASES
    g.get_curr_tissues()  # CASE 1
    # g.get_curr_tissues(abbrev=True)  # CASE 2
    # g.get_curr_tissues(full=True)  # CASE 3
    # g.get_curr_tissues(abbrev=True, full=True)  # CASE 4

    # OUTPUTS
    # CASE 1 = "abbrev: ['Thyroid', 'Stomach', 'Spleen']
    # CASE 2 = "abbrev: ['Thyroid', 'Stomach', 'Spleen']"
    # CASE 3 = "full: ['Thyroid (n=278)', 'Stomach (n=170)', 'Spleen (n=89)']"
    # CASE 4 = "abbrev + full!
    #           abbrev: ['Thyroid', 'Stomach', 'Spleen']
    #           full: ['Thyroid (n=278)', 'Stomach (n=170)', 'Spleen (n=89)']"


def test_getTissueInfo():
    """ Tests the functionality of get_tissue_info(). """

    g = GTEx()
    g.get_tissue_info()

    print "Passed\n"


if __name__ == '__main__':
    # ACTIVELY WRITING / DEBUGGING METHODS
    # test_reading()
    test_query()

    # FUNCTIONING METHODS
    # test_errors()
    # test_getTissue()
    # test_getCurrTissue()
    # test_getTissueInfo()
