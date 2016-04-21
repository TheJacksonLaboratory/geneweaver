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

from selenium import webdriver
from selenium import selenium
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import Select
import time

from bs4 import BeautifulSoup
import requests
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

        # urls for download + search
        self.BASE_URL = 'http://www.gtexportal.org/home/'
        self.DATASETS_INFO_URL = 'http://www.gtexportal.org/home/datasets'
        self.LOOKUP_URL = 'http://www.gtexportal.org/home/eqtls/tissue?tissueName=All'
        self.TISSUE_LOOKUP_URL = 'http://www.gtexportal.org/home/eqtls/tissue?tissueName='
        self.COMPRESSED_QTL_DATA_URL = 'http://www.gtexportal.org/static/datasets/gtex_analysis_v6/' \
                                       'single_tissue_eqtl_data/GTEx_Analysis_V6_eQTLs.tar.gz'
        # errors
        self.crit = []
        self.noncrit = []

        # data processing fields
        self.raw = {}  # {tissue_type, organized per tissue
        self.raw_headers = []
        self.tissue_types = []

        self.tissue_pref = tissue  # need to check this entry in tissue_types before proceeding / method to group tissue

        # group these ^ tissue types manually by tissue? For easier traversal later?

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
        # list of known GTEx tissues
        """ Takes in a tissue label and checks that it is a known GTEx tissue. If it is a known
            tissue, returns 'True'. Otherwise, returns 'False', and adds a critical error message.

        Parameters
        ----------
        tissue: input tissue type (string)

        Returns
        -------
        exists: boolean indicative of inclusion among known GTEx tissue types
        """
        # replace below with list generated from online query, if an option (minus '--' condition)
        tissues = ['All', 'Adipose_Subcutaneous', 'Adipose_Visceral_Omentum', 'Adrenal_Gland',
                   'Artery_Aorta', 'Artery_Coronary', 'Artery_Tibial', 'Brain_Anterior_cingulate_cortex_BA24',
                   'Brain_Caudate_basal_ganglia', 'Brain_Cerebellar_Hemisphere', 'Brain_Cerebellum',
                   'Brain_Cortex', 'Brain_Frontal_Cortex_BA9', 'Brain_Hippocampus', 'Brain_Hypothalamus',
                   'Brain_Nucleus_accumbens_basal_ganglia', 'Brain_Putamen_basal_ganglia',
                   'Breast_Mammary_Tissue', 'Cells_EBV-transformed_lymphocytes',
                   'Cells_Transformed_fibroblasts', 'Colon_Sigmoid', 'Colon_Transverse',
                   'Esophagus_Gastroesophageal_Junction', 'Esophagus_Mucosa', 'Esophagus_Muscularis',
                   'Heart_Atrial_Appendage', 'Heart_Left_Ventricle', 'Liver', 'Lung', 'Muscle_Skeletal',
                   'Nerve_Tibial', 'Ovary', 'Pancreas', 'Pituitary', 'Prostate',
                   'Skin_Not_Sun_Exposed_Suprapubic', 'Skin_Sun_Exposed_Lower_leg',
                   'Small_Intestine_Terminal_Ileum', 'Spleen', 'Stomach', 'Testis', 'Thyroid', 'Uterus',
                   'Vagina', 'Whole_Blood', 'Bladder', 'Brain_Amygdala', 'Brain_Spinal_cord_cervical_c-1',
                   'Brain_Substantia_nigra', 'Cervix_Ectocervix', 'Cervix_Endocervix', 'Fallopian_Tube',
                   'Kidney_Cortex', 'Minor_Salivary_Gland']

        # check to make sure the file is labelled appropriately, + tissue is known GTEx tissue
        if tissue in tissues:
            exists = True
        else:
            self.set_errors(critical="Error: The names of input files should contain the tissue type such"
                                     " that the format mimicks '<tissue_type>_Analysis.snpgenes'. Tissue"
                                     " must already exist among curated GTEx tissues.\n")
            exists = False

        return exists

    def update_tissues(self, tissue):
        """ Updates the list of tissues uploaded in this batch. First checks to make sure that
            the value represents a known GTEx tissue type.

        Parameters
        ----------
        tissue: tissue type to be added to global list (self.tissue_types)
        """
        if self.check_tissue(tissue):  # if header exists
            self.tissue_types.append(tissue)  # add to tissues uploaded in this batch
        else:
            exit()  # error message handled in check_tissue()

    # def update_resources(self):
    #     """ Pulls a list of files to use for GTEx initial setup [from source].
    #     """
    #     # need to test this function when theres more space on comp - doesn't save locally, might also be an issue
    #     r = requests.get(self.COMPRESSED_DATA_URL, stream=True)  # 'True' means that data in stream, not save actually
    #     z = zipfile.ZipFile(StringIO.StringIO(r.content))
    #     z.extractall()
    #     r.ok()

    # def get_annotations(self):
    #     """ Downloads descriptions of each eGene attribute and phenotypic variable.
    #     """

    def get_tissue_types(self):
        """ Returns a list of current tissue types listed in GTEx portal resource.

            Returns
            -------
            curr_tissues: tissue types (list)
        """
        curr_tissues = []  # output

        profile = webdriver.FirefoxProfile()
        # clean up preference setting through that iterative feature used in CS251
        profile.set_preference("browser.download.folderList", 2)
        profile.set_preference("browser.download.dir", self.SAVE_SEARCH_DIR)
        profile.set_preference("browser.helperApps.neverAsk.openFile", "text/html")
        profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/html")
        temp = profile.userPrefs
        print temp
        profile.update_preferences()

        # search GTEx Portal
        search = self.TISSUE_LOOKUP_URL + "All"
        driver = webdriver.Firefox(firefox_profile=profile)
        driver.get(search)
        time.sleep(5)  # debugging purposes

        # NOTE: Adapt the below to match your puroses for listbox item selection
        # select option to show 100 - the fewer rounds of scraping the better!
        # select = Select(driver.find_element_by_name('GeneTable_length'))
        # final_option = None
        # for options in select.options:
        #     final_option = options
        # select.select_by_visible_text(final_option.text)

        return curr_tissues

    # def get_gtex_info(self, gencode_id):
    #     """ Retrieves GTEx info from GTEx Portal.
    #
    #     Parameters
    #     ----------
    #     gencode_id: GTEx Gene Identifier
    #
    #     """
    #
    #     # use 'requests' package to pull info from GTEx
    #     req = requests.get('http://www.gtexportal.org/home/eqtls/tissue?tissueName=All')

    def search_GTEx(self, save=False, tissue=None, gencode_id=None, gene_symbol=None):
        results = None

        # depending on 'save' parameter, save under tissue format (give get_data some use)

        # r = requests.get('http://www.gtexportal.org/home/eqtls/tissue?tissueName=Uterus')
        # print r.headers['Content-Type']
        # return

        # prevent download dialog
        profile = webdriver.FirefoxProfile()
        # clean up preference setting through that iterative feature used in CS251

        profile.set_preference("browser.download.folderList", 2)
        profile.set_preference("browser.download.dir", self.SAVE_SEARCH_DIR)
        # profile.set_preference("browser.download.useDownloadDir", True)

        # profile.set_preference("browser.download.manager.showWhenStarting", False)  # don't need to see download dialog
        # profile.set_preference("browser.download.dir", self.SAVE_SEARCH_DIR + "/output.csv")
        # profile.set_preference("browser.download.panel.shown", False)
        # profile.set_preference("browser.download.manager.retention", 2)

        profile.set_preference("browser.helperApps.neverAsk.openFile", "text/plain")
        profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/plain")
        temp = profile.userPrefs
        print temp
        profile.update_preferences()

        # profile.set_preference("browser.helperApps.neverAsk.openFile", "text/csv,application/vnd.ms-excel")
        # profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "text/csv,application/vnd.ms-excel")

        # profile.set_preference("browser.helperApps.neverAsk.openFile", "application/x-shockwave-flash")
        # profile.set_preference("browser.helperApps.neverAsk.saveToDisk", "application/x-shockwave-flash")

        # profile.set_preference('browser.download.folderList', 2)
        # profile.set_preference('browser.download.panel.shown', False)
        # profile.set_preference('browser.download.dir', self.SAVE_SEARCH_DIR)  # specify where to save search results
        # # only saving most recent search, for now - later change to make it date/time based or something
        # profile.set_preference('browser.helperApps.neverAsk.openFile', self.SAVE_SEARCH_DIR + "output.csv")
        # profile.set_preference('browser.helperApps.neverAsk.saveToDisk', self.SAVE_SEARCH_DIR + "output.csv")
        # profile.set_preference('browser.download.manager.showWhenStarting', False) # don't need to see download dialog

        # using the inputs, search GTEx Portal using selenium
        search = self.TISSUE_LOOKUP_URL + tissue  # search url

        driver = webdriver.Firefox(firefox_profile=profile)
        driver.get(search)
        time.sleep(5)  # debugging purposes

        # select option to show 100 - the fewer rounds of scraping the better!
        select = Select(driver.find_element_by_name('GeneTable_length'))
        final_option = None
        for options in select.options:
            final_option = options
        select.select_by_visible_text(final_option.text)

        time.sleep(5)  # debugging purposes

        # grab from table - click on the CSV button
        driver.find_element_by_id('ZeroClipboard_TableToolsMovie_5').click()

        # save file ?

        time.sleep(10)  # debugging purposes
        driver.close()
        driver.quit()  # check between 'close' + 'quit' - which you need

        return results

    def get_data(self):
        """ Initializes significant eGenes from GTEx Portal. Creates eGene objects for
            each significant gene. ## add distinct file options
        """

        # if dealing with hard files -------------------------------- #
        for fileList in os.walk(self.ROOT_DIR):
            for tissueFile in fileList[2]:
                if tissueFile == 'Uterus_Analysis.snpgenes':  # TEMPORARY: only for testing purposes
                    tissue_name, raw_headers, raw_data = self.readGTExFile(self.ROOT_DIR + tissueFile)
                    self.upload data(raw_data, tissue_name, raw_headers)  # REMEMBER: assumes SNPs [documentation+]

        # if working with online resources -------------------------- #
        page = None

        # depending on 'save' parameter, save under tissue format (give get_data some use)

        # using the inputs, search GTEx Portal using requests
        # with requests.Session() as session:
        #     page = session.get(self.LOOKUP_URL)

    def upload_data(self, data, tissue_name, headers):
        """ Greates a GTExGeneset object that interfaces with the GeneWeaver database.

        Parameters
        ----------
        tissue_name: type of tissue (string)
        headers:
        data:
        """
        self.update_tissues(tissue_name)  # tissue type checked here, will exit if critical error reached
        self.raw[tissue_name] = data  # store raw data per each tissue
        egenes = []  # to store eGene objects

        if not self.raw_headers:
            self.raw_headers = headers  # store raw headers

        gtex_upload = GTExGeneset(data, tissue_type=tissue_name)

        # for gene in self.raw[tissue_name]:
        #     for pos in range(len(self.raw_headers)):
        #         # g = GTExGeneset(gene, tissue_name)  # create an eGene
        #         # eGenes.append(g)
        #         print gene
        #         break  # for editing purposes only
        #     break

    # -------------------------- FOR BATCH [LATER] -------------------------------------------------------------------#
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

    # def createGeneset(self):

# essentailly a model of an Uploader? Uses a "trickle-down" method for uploading ---------------------------------
class GTExGeneset:
    def __init__(self, values, tissue_type=None):

        self.raw_values = values

        self.snp, self.gene, self.beta, self.t_stat, self.se, self.p_value, \
            self.nom_thresh, self.min_p, self.gene_emp_p, self.k, self.n, \
            self.gene_q_value, self.beta_noNorm, self.snp_chrom, self.snp_pos, \
            self.minor_allele_samples, self.minor_allele_count, self.maf, \
            self.ref_factor, self.ref, self.alt, self.snp_id_1kg_project_phaseI_v3, \
            self.rs_id_dbSNP142_GRCh37p13, self.num_alt_per_site, self.has_best_p, \
            self.is_chosen_snp, self.gene_name, self.gene_source, self.gene_chr, \
            self.gene_start, self.gene_stop, self.orientation, self.tss_position, \
            self.gene_type, self.gencode_attributes, self.tss_distance = None

        # data formatting checked here (decipher entry type - can be a 'tissue' file currently)
        # check to make sure values is a list, adding error messages as necessary
        if tissue_type:
            self.setup_tissue(tissue_type)  # if entry type is per tissue, as tissue type must be provided

            # test variable assignment
            print "self.gene: %s\n" % self.gene
            print "self.p_value: %s\n" % self.p_value

        # pull all relevant information from parent, prepare for uploading (as a geneset)

    def setup_tissue(self, tissue):

        # IF: format of file such that values listed as snps, in GTEx formatting (from tissue file)
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

class eGene(GTExGeneset):
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, parent):
        GTExGeneset.__init__(self, values=None, tissue_type=None)

        self.parent = parent

        # core values being used
        self.gencode_id = None
        self.gene_symbol = None
        self.nom_pValue = None
        self.emp_pValue = None
        self.qValue = None
        self.tissue_name = None  # add tissue_type here, make sure to type first

        # error handling
        self.crit = []
        self.noncrit = []

        # pull all relevant information from parent, prepare for uploading


class SNP(eGene):
    def __init__(self, parent):
        eGene.__init__(self, parent)

        # currently assumes a very specific data entry type if called
        self.parent = parent

        # pull all relevant information from parent, prepare for uploading

# --------------------------------------------- TESTs ----------------------------------------------------------#
def test_errors():
    """ Simple test of global error handling capabilites for GTEx obj.
    """
    print "TEST: Simple test of global error handling capabilites for GTEx obj:\n"

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
    print "TEST: Tests batch reading capabilites of GTEx obj:\n"

    g = GTEx()
    g.get_data()

def test_query():
    """ Tests GTEx Portal data scraping.
    """
    print "TEST: Tests GTEx data scraping.\n"

    g = GTEx()
    results = g.search_GTEx(tissue="Uterus")

    print results  # add a better final print statement


if __name__ == '__main__':
    # test_errors()
    test_reading()
    # test_query()
