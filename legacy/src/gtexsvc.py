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
from selenium.webdriver.common.keys import Keys
import time

from bs4 import BeautifulSoup
import zipfile
import StringIO
import os


class GTEx:
    """ Creates a GTEx object representative of significant 'eGenes' drawn from
        GTEx Portal [http://www.gtexportal.org/home/eqtls]

        If a tissue type is specified, search pulls significant 'eGenes' for that
        tissue.
    """

    def __init__(self, tissue='All'):
        # local dataset filepath
        self.root_dir = '/Users/Asti/geneweaver/gtex/datasets/v6/eGenes/GTEx_Analysis_V6_eQTLs/'  # change later
        # type of execution
        self.SETUP = True

        # urls for download and search
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
        self.raw = {}
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

    # def get_tissue_types(self):
    #     """ Returns a list of current tissue types listed in GTEx portal resource.
    #
    #         Returns
    #         -------
    #         curr_tissues: tissue types (list)
    #     """
    #     prim_url_ext = 'eqtls/tissue?tissueName=All'
    #
    #     # find the list of entries for the selection box under prim_url_ext
    #     # iterate through and add them to a list
    #     # return the list
    #
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

        # using the inputs, search GTEx Portal using requests
        # add safety check when connecting (status_code==200)
        # with requests.Session() as session:
        #     if tissue and self.check_tissue(tissue):  # must be in the GTEx label format (not even groom GTEx format)
        #         response = session.get(self.TISSUE_LOOKUP_URL + tissue)
        #         soup = BeautifulSoup(response.text, "lxml")
        #         content = soup.find_all('td')
        #
        #         print content
        search = self.TISSUE_LOOKUP_URL + tissue
        print search

        driver = webdriver.Firefox()
        driver.get(search)
        time.sleep(5)  # debugging purposes
        # search_box = driver.find_element_by_name('q')
        # search_box.send_keys('ChromeDriver')
        # search_box.submit()
        # time.sleep(5)  # Let the user actually see something!
        driver.quit()


        # driver = webdriver.Chrome()
        # driver.get(self.TISSUE_LOOKUP_URL + tissue)
        # elem = driver.find_element_by_class_name("odd")

        print elem

        return results

    def get_data(self):
        """ Initializes significant eGenes from GTEx Portal. Creates eGene objects for
            each significant gene. ## add distinct file options
        """

        # if dealing with hard files -------------------------------- #
        for fileList in os.walk(self.root_dir):
            for tissueFile in fileList[2]:
                if tissueFile == 'Uterus_Analysis.snpgenes':
                    tissue_name, raw_headers, raw_data = self.readGTExFile(self.root_dir + tissueFile)
                    self.create_eGenes(tissue_name, raw_headers, raw_data)

        # if working with online resources -------------------------- #
        page = None

        # depending on 'save' parameter, save under tissue format (give get_data some use)

        # using the inputs, search GTEx Portal using requests
        with requests.Session() as session:
            page = session.get(self.LOOKUP_URL)

    def create_eGenes(self, tissue_name, headers, data):
        """ Creates eGene objects (list global organizational structures too) ##

        Parameters
        ----------
        tissue_name:
        headers:
        data:
        """
        self.update_tissues(tissue_name)  # tissue type checked here, will exit if critical error reached
        self.raw[tissue_name] = data  # store raw data per each tissue
        eGenes = []  # to store eGene objects

        if not self.raw_headers:
            self.raw_headers = headers  # store raw headers

        for gene in self.raw[tissue_name]:
            for pos in range(len(self.raw_headers)):
                g = eGene(gene, tissue_name)  # create an eGene
                eGenes.append(g)
                print g.raw_values
                break  # for editing purposes only
            break

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

class eGene:
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, values, tissue_type):
        # core values being used
        self.gencode_id = None
        self.gene_symbol = None
        self.nom_pValue = None
        self.emp_pValue = None
        self.qValue = None
        self.tissue_name = None  # add tissue_type here, checking type first

        # error handling
        self.crit = []
        self.noncrit = []

        print len(values)

        # check to make sure values is a list, adding error messages as necessary
        if len(values) == 36:
            self.raw_values = values

            # additional values (if needed later on)
            self.snp = values[0]
            self.gene = values[1]
            self.beta = values[2]
            self.t_stat = values[3]
            self.se = values[4]
            self.p_value = values[5]
            self.nom_thresh = values[6]
            self.min_p = values[7]
            self.gene_emp_p = values[8]
            self.k = values[9]
            self.n = values[10]
            self.gene_q_value = values[11]
            self.beta_noNorm = values[12]
            self.snp_chrom = values[13]
            self.snp_pos = values[14]
            self.minor_allele_samples = values[15]
            self.minor_allele_count = values[16]
            self.maf = values[17]
            self.ref_factor = values[18]
            self.ref = values[19]
            self.alt = values[20]
            self.snp_id_1kg_project_phaseI_v3 = values[21]
            self.rs_id_dbSNP142_GRCh37p13 = values[22]
            self.num_alt_per_site = values[23]
            self.has_best_p = values[24]
            self.is_chosen_snp = values[25]
            self.gene_name = values[26]
            print self.gene_name
            self.gene_source = values[27]
            self.gene_chr = values[28]
            self.gene_start = values[29]
            self.gene_stop = values[30]
            self.orientation = values[31]
            self.tss_position = values[32]
            self.gene_type = values[33]
            self.gencode_attributes = values[34]
            self.tss_distance = values[35]

        else:
            # add error message
            print "nope\n"
            pass


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
    # test_reading()
    test_query()
