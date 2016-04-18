import requests
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

        # urls for download and search
        self.BASE_URL = 'http://www.gtexportal.org/home/'
        self.DATASETS_INFO_URL = 'http://www.gtexportal.org/home/datasets'
        self.LOOKUP_URL = 'http://www.gtexportal.org/home/eqtls/tissue?tissueName=All'
        self.COMPRESSED_DATA_URL = 'http://www.gtexportal.org/static/datasets/gtex_analysis_v6/' \
                                   'single_tissue_eqtl_data/GTEx_Analysis_V6_eQTLs.tar.gz'

        self.tissue_pref = tissue  # need to check this entry in tissue_types before proceeding

        # create an option to update this list of tissue types - using get_data to grab file headers?
        self.tissue_types = ['All', 'Adipose_Subcutaneous', 'Adipose_Visceral_Omentum',
                             'Adrenal_Gland', 'Artery_Aorta', 'Artery_Coronary',
                             'Artery_Tibial', 'Brain_Anterior_cingulate_cortex_BA24',
                             'Brain_Caudate_basal_ganglia', 'Brain_Cerebellar_Hemisphere',
                             'Brain_Cerebellum', 'Brain_Cortex', 'Brain_Frontal_Cortex_BA9',
                             'Brain_Hippocampus', 'Brain_Hypothalamus',
                             'Brain_Nucleus_accumbens_basal_ganglia',
                             'Brain_Putamen_basal_ganglia', 'Breast_Mammary_Tissue',
                             'Cells_EBV-transformed_lymphocytes', 'Cells_Transformed_fibroblasts'
                             'Colon_Sigmoid', 'Colon_Transverse',
                             'Esophagus_Gastroesophageal_Junction', 'Esophagus_Mucosa',
                             'Esophagus_Muscularis', 'Heart_Atrial_Appendage',
                             'Heart_Left_Ventricle', 'Liver', 'Lung', 'Muscle_Skeletal',
                             'Nerve_Tibial', 'Ovary', 'Pancreas', 'Pituitary',
                             'Prostate', 'Skin_Not_Sun_Exposed_Suprapubic',
                             'Skin_Sun_Exposed_Lower_leg', 'Small_Intestine_Terminal_Ileum',
                             'Spleen', 'Stomach', 'Testis', 'Thyroid', 'Uterus', 'Vagina',
                             'Whole_Blood', 'Bladder', 'Brain_Amygdala',
                             'Brain_Spinal_cord_cervical_c-1', 'Brain_Substantia_nigra',
                             'Cervix_Ectocervix', 'Cervix_Endocervix', 'Fallopian_Tube',
                             'Kidney_Cortex', 'Minor_Salivary_Gland']
        # group these ^ tissue types manually by tissue? For easier traversal later?

    # def updateResources(self):
    #     """ Pulls a list of files to use for GTEx initial setup [from source].
    #     """
    #     # need to test this function when theres more space on comp - doesn't save locally, might also be an issue
    #     r = requests.get(self.COMPRESSED_DATA_URL, stream=True)  # 'True' means that data in stream, not save actually
    #     z = zipfile.ZipFile(StringIO.StringIO(r.content))
    #     z.extractall()
    #     r.ok()

    def get_data(self):
        """ Initializes significant eGenes from GTEx Portal. Creates eGene objects for
            each significant gene.
        """
        for fileList in os.walk(self.root_dir):
            for tissueFile in fileList[2]:
                if tissueFile == 'Uterus_Analysis.snpgenes':
                    self.readGTExFile(self.root_dir+tissueFile)

    def readGTExFile(self, fp):
        """ Reads the file at the given filepath and returns all the lines that
            comprise the file.

        Parameters
        ----------
        fp: filepath to read (string)

        Returns
        -------
        lines: list of strings containing each line of the file

        """
        # add this method to class batch later!

        with open(fp, 'r') as file_path:
            lines = file_path.readlines()

        for info in lines[0].splitlines():  # parameters from batch file
            temp = info.strip().split("\t")

        # identify what from above you want to use for eGene object
        # make a new eGene for each item
        # add each eGene to tissue dictionary
        # add each eGene reference to other possible parameter dictionaries, for fast lookup

        return lines

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


class eGene:
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal.
    """

    def __init__(self):
        self.gencodeId = None
        self.geneSymbol = None
        self.pValue = None
        self.qValue = None
        self.tissueName = None

if __name__ == '__main__':
    g = GTEx()
    g.get_data()
