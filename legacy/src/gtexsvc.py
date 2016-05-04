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
import tarfile
import psycopg2
import config
import datetime


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
        # local dataset filepaths
        self.ROOT_DIR = '/Users/Asti/geneweaver/gtex/datasets/v6/eGenes/GTEx_Analysis_V6_eQTLs.tar.gz'  # change later
        self.SAVE_SEARCH_DIR = "/Users/Asti/geneweaver/gtex/gtex-results/"  # change later

        # urls for download + search [make a version control checker, as gtex provides options
        #   e.g {"status": 404, "message": "Not Found. You have requested this URI [/v6.3/tissues]
        #           but did you mean /v6.2/tissues or /v6/tissues or /v2/tissues ?"}
        # IDEA: try: v6.3 and backtrack by checking other versions? [see GTEx_VERSIONS]
        self.GTEx_VERSIONS = ['v6', 'v6.2']
        self.SINGLE_TISSUE_INFO_URL = 'http://gtexportal.org/api/v6.2/tissues?username=Anonymous&_=' \
                                      '1461355517678&v=clversion'
        # only relevant for single-tissue gene expression results:
        self.COMPRESSED_QTL_DATA_URL = 'http://www.gtexportal.org/static/datasets/gtex_analysis_v6/' \
                                       'single_tissue_eqtl_data/GTEx_Analysis_V6_eQTLs.tar.gz'

        # (updated for Version 6.2 of GTEx data [April 2016]) ^ also relevant
        self.STATIC_TISSUES = []  # list of tissue headers drawn directly from GTEx Portal (where n>=70)
        self.tissue_info = {}  # stores data pulled in get_tissue_info()
        self.tissue_types = {}

        # user-interface
        self.crit = []
        self.noncrit = []

        # data processing fields
        self.raw_data = {}  # {tissue_name: values,}  -  values[0] = headers, values[1+] = raw data
        self.gene_info = {}  # USAGE: {gene_symbol: (description, ensembl_id, entrez_id),}  -  used in eGene
        self.raw_genesets = {}  # USAGE: {tissue_name: GTExObject,}

        self.get_tissue_info()  # populates: 'self.STATIC_TISSUES', + builds 'self.tissue_info'
        self.get_tissues_nomen()  # populates: self.tissue_types

        # database connection
        self.connection = None
        self.cur = None

        # publication info
        self.publications = {}  # {pubmed_id: {authors:", title:", abstract:", journal:", vol:", pages:", pmid:"},}

        self.launch_connection()

        # self.database_setup()



    def launch_connection(self):

        data = config.get('db', 'database')
        user = config.get('db', 'user')
        password = config.get('db', 'password')
        host = config.get('db', 'host')

        # set up connection information
        cs = 'host=\'%s\' dbname=\'%s\' user=\'%s\' password=\'%s\'' % (host, data, user, password)

        try:
            self.connection = psycopg2.connect(cs)  # connect to geneweaver database
            self.cur = self.connection.cursor()
        except SyntaxError:  # cs probably wouldn't be a useable string if wasn't able to connect
            print "Error: Unable to connect to database."
            exit()

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

        # USER FEEDBACK [uncomment selection]
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

    def list_all_tissues(self, label=False, title=False):  # change to reflect info from tissue_info{} (has both)
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
        # temp_full = []
        #
        # # make sure that tissue label reference dictionary is populated
        # if not self.tissue_types:
        #     self.get_tissues_nomen()
        #
        # if not (label or title) or (label and not title):
        #     return self.raw_data.keys()
        # elif title and not label:
        #     for key in self.raw_data.keys():
        #         temp_full.append(self.tissue_types[key])
        #     return temp_full
        # else:
        #     for key in self.raw_data.keys():
        #         temp_full.append(self.tissue_types[key])
        #     return self.raw_data.keys(), temp_full
        pass

    # --------------------------- PORTAL QUERY FUNCTIONS (version control) -------------------------------------- #
    # if setup -> create criteria to iterate over
    # otherwise -> use as a data object for Batch

    def check_version(self):
        # check to see if the version stored matches the version on GTex
        pass

    def pull_all_data(self):
        """ ### Pulls significant Matrix of eQTL results from GTEx Portal resouce ### """
        # somehow control rate of unpacking?
        # read GTEx file
        # * data analysis *

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

    # Combine all of the methods below into one... just use a type identifier

    def search_gene_info(self, gene_symbol):
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

        # print "%s data pulled from GTEx Portal\n" % gene_symbol  # USER FEEDBACK [uncomment selection]

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
        gene_search = 'http://gtexportal.org/api/v6/singleTissueEqtl?geneId=%s' \
                      '&tissueName=%s&username=anonymous&_=1461862131015&v=clversion' % (gene_symbol, tissue)
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['singleTissueEqtl']

        return output

    def search_multi_tissue_eQTLs(self):
        """ ## returns entire multi-tissue dataset per gene symbol entered
            ## restricted to the 13 tissues
            ## values are unc, uc and amean (probabilities)
        """

        gene_search = 'http://gtexportal.org/api/v1/multiTissueEqtl?username=anonymous&_=1461862131016&v=clversion'
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['multiTissueEQTL']

        return output

    def search_gene_rank(self, tissue):
        """ ## Ranks genes by signficance per tissue

        Parameters
        ----------
        tissue

        Returns
        -------

        """
        gene_search = 'http://gtexportal.org/api/v6/geneRanks?tissueId=%s' \
                      '&username=anonymous&_=1461862131023&v=clversion' % tissue
        r = requests.get(gene_search).content
        temp = json.loads(r)
        output = temp['sortedGenes']

        return output

    def search_pubmed_info(self, pubmed_id):  # EDIT: docstring to mirror use
        """ Retrieves Pubmed article info from the NCBI servers using the NCBI eutils.
            The result is a dictionary whose keys are the same as the publication
            table. The actual return value for this function though is a tuple. The
            first member is the dict, the second is any error message.

            # Needs editing to reflect new function

            # NOTE: this will vary from superclass

        Parameters
        ----------
        pubmed_id: PubMed ID
        """
        publication = {}
        # URL for pubmed article summary info
        url = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?'
               'retmode=json&db=pubmed&id=%s') % pubmed_id
        # NCBI eFetch URL that only retrieves the abstract
        url_abs = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
                   '?rettype=abstract&retmode=text&db=pubmed&id=%s') % pubmed_id

        res = requests.get(url).content
        temp = json.loads(res)['result']

        publication['pubmed_id'] = str(pubmed_id)
        publication['pages'] = temp[publication['pubmed_id']]['pages']
        publication['title'] = temp[publication['pubmed_id']]['title']
        publication['journal'] = temp[publication['pubmed_id']]['fulljournalname']
        publication['vol'] = temp[publication['pubmed_id']]['volume']

        authors = ""  # will hold a CSV list
        for auth in temp[publication['pubmed_id']]['authors']:
            authors += auth['name'] + ', '
        publication['authors'] = authors[:-2]

        abstract = None
        if 'Has Abstract' in temp[publication['pubmed_id']]['attributes']:
            res2 = requests.get(url_abs).content.split('\n\n')[-3]
            publication['abstract'] = res2
        else:
            er = ('Error: The PubMed info retrieved from NCBI was incomplete. No '
                  'abstract data will be attributed to this GeneSet.')
            self.set_errors(noncritical=er)

        return publication

    # -------------------------- DATABASE SETUP  ---------------------------------------------------------------#
    # use the below to provide additional eQTL? or just update this too?

    @staticmethod
    def readGTExFile(fp):
        """ Reads the file at the given filepath and returns tissue name (provided by the filename),
            geneset classifiers and related data.

            ## update this to include new features under 'else' that allows you to pass an ExFile? lookup
            ## and define

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
        temp_headers = []  # list of classifiers
        temp_data = []  # list of values

        if type(fp) == "":  # if 'fp' is a string, read as directory file path
            with open(fp, 'r') as file_path:
                lines = file_path.readlines()
                tissue_name = file_path.name  # name is full filepath
                tissue_name = tissue_name.strip().split("/")[-1][:-18]  # grab the tissue type from the filepath
        else:  # otherwise, assume that its an ExFileObj (name? - CHECK) [make this type dependent on that obj]
            lines = fp.readlines()
            tissue_name = fp.name  # name is full filepath
            tissue_name = tissue_name.strip().split("/")[-1][:-18]  # grab the tissue type from the filepath
            fp.close()

        count = 0  # placeholder for temp_headers
        for data in lines:
            data = data.splitlines()
            for datum in data:
                if count == 0:  # if the first row, assume its a list of data classifiers
                    temp_headers = datum.strip().split("\t")  # grab classifiers
                    count += 1
                else:
                    temp_data.append(datum.strip().split("\t"))  # grab eGene dataset

        return tissue_name, temp_headers, temp_data

    def groom_raw_data(self):
        """ # will be useful later for snps - only started, not completed"""
        self.raw_data = {}

        with tarfile.open(self.ROOT_DIR, 'r:gz') as tar:
            for tarinfo in tar.getmembers():
                output = {}
                f = tar.extractfile(tarinfo)  # file auto-closed in self.readGTExFile() below
                tissue, headers, data = self.readGTExFile(f)
                if self.tissue_info[tissue]['has_egenes'] == 'True':
                    fp_out = self.SAVE_SEARCH_DIR + tissue + "_Groomed.json"
                    output[tissue] = []
                    with open(fp_out, 'w') as file_path:
                        for datum in data:
                            if datum[25] == '1':  # if this snp-gene pair is signficicant
                                output[tissue].append({headers[x]: datum[x] for x in range(len(headers))})

                        json.dump(output, fp=file_path)

                        print tissue, ": count ", len(output[tissue]), " should equal ", \
                            self.tissue_info[tissue]['eGene_count']

    def database_setup(self):
        """ ### Gathers data from online resources. Returns something that
            upload_data nad upload_dataset can deal with ###

            only use is to set up geneweaver's database (should be done only once)

            # sets where strength is too low (n<70) are not included

        """
        # self.groom_raw_data()  # [last run: 5/2/16] reads in file and identifies what is useful, writing results

        for tissue in self.tissue_info:
            if self.tissue_info[tissue]['has_egenes'] == 'True':  # for each tissue (where n >= 70)
                # iterate through the list of tissue files
                fp = self.SAVE_SEARCH_DIR + tissue + "_Groomed.json"

                with open(fp, 'r') as data_file:
                    qtls = json.load(data_file)  # load the file info
                    # create GTExGeneSet obj + respective eGenes
                    gs_tissue = GTExGeneSet(self, values=qtls[tissue], tissue_type=str(tissue))
                    self.raw_genesets[gs_tissue.tissue_name] = gs_tissue  # store GTExGeneSet obj globally
                    print tissue, len(self.raw_genesets[gs_tissue.tissue_name].e_genes.keys()), \
                        "should equal ", self.tissue_info[gs_tissue.tissue_name]['eGene_count']
                    exit()

# Uses a "trickle-down" method for uploading data to GeneWeaver
# add error handling that you can push back up to Uploader
class GTExGeneSet:  # GTExGeneSetUploaders
    """ ## Acts as an uploader interface for GTEx data -> GeneWeaver database
        ## specify param types, what happens, and how it passes info along

    """
    def __init__(self, parent, values, tissue_type):  # assumes a user file input

        # param input data - formatting checked here

        # inheritance
        self.batch = parent
        self.cur = parent.cur  # psycopg2 cursor obj
        self.connection = parent.connection  # psycopg2 connection obj -> GeneWeaver

        self.name = "[GTEx] " + tissue_type
        self.abbrev_name = parent.tissue_info[self.tissue_name]['tissue_abbrv']
        self.species = 2  # all GTEx is human
        self.groups = ""
        self.thresh_type = 1
        self.threshold = '0.05'
        self.gene_id_type = 7  # gdb_id
        self.usr_id = 0  # technically 'guest'
        self.cur_id = 1  # uploaded as a public resource [might be 2]

        self.description, self.publication_id, self.values, self.count = None

        # init for globals - check input types
        self.raw_values = values
        self.tissue_name = tissue_type  # NOTE: Batch + Uploader classes will handle this differently

        self.e_genes = {}  # USAGE: {gencode_id: eGene obj,}  -  gencode Id is tissue dependent
        self.e_qtls = {}  # USAGE: {snp: eQTL obj,} - for top-level access (otherwise already stored in eGene obj)
        self.publication = None
        self.pubmed_id = None

        # check to make sure values is a list, adding error messages as necessary

        self.geneweaver_setup()  # creates eGenes, along with respective eQTL
        # required fields for GeneWeaver

    def create_eGene(self, data_dict):
        """ # data passed in with specific dictionary type (pass along from batch):

        {snp_id_1kg_project_phaseI_v3: RSID, orientation: str, gene_chr: int, rs_id_dbSNP142_GRCh37p13: RSID,
            gene_stop: int, tss_position: int, gene_q_value: float, alt: str, ref_factor: int,
            num_alt_per_site: int, minor_allele_count: int, min_p: float, snp_chrom: int, tss_distance: int,
            minor_allele_samples: int, gencode_attributes: str, ref: str, nom_thresh: float, is_chosen_snp: int,
            beta: float, snp: str, maf: float, gene_emp_p: float, p_value: float, has_best_p: int,
            gene: Gencode ID, gene_start: int, snp_pos: int, k: int, gene_source: str, n: int, se: float,
            gene_type: str, beta_noNorm: float, gene_name: Gene Symbol, t_stat: float}

        Parameters
        ----------
        data_dict
        """
        gene = eGene(self, data=data_dict)  # initialize eGene obj
        self.e_genes[gene.gencode_id] = gene  # store gene obj in global dict

    # ----------------------------- GENEWEAVER SETUP ----------------------------- #
    def geneweaver_setup(self):
        """ Preps upload if setting up database.  ##
            # leave eQTL creation to eGene obj
            # and access / populate 'self.eQTLs' through each eGene obj
        """
        # PUBLICATION
        self.pubmed_id = str(23715323)  # PubMed ID for GTEx Project
        self.publication = self.batch.search_pubmed_info(self.pubmed_id)  # PubMed ID for GTEx Project
        # self.insert_publication()  # updates self.publication_id

        # GENESET
        self.update_geneset_info()  # fill in required fields for GeneWeaver
        # create geneset in GW

        # GENESET VALUES
        for gene_data in self.raw_values:
            self.create_eGene(gene_data)
        # gene lookup - via Gene Symbol
            # geneset values - gsv -> self.values [see gsv handling in batch]
            #   gene_symbols -> ode_gene_id mapping first
            # self.values = ?

        # self.check_success()  # needs updating following new approach / probably isn't necessary here

    def check_success(self):  # needs updating!

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

    def update_geneset_info(self):

        if self.batch.tissue_info[self.tissue_name]['eGene_count'] == len(self.e_genes):
            self.count = len(self.e_genes)
        else:  # EDIT: add error handling in case the eGene count is not the same
            print "NO!"

        # self.description = # what it contains + # tissue name + # what it contains + # script name/date run

    def upload_all(self, genes=False, qtls=False):
        # uploads this geneset to GeneWeaver

        if genes and not qtls:
            for gene in self.e_genes:
                gene.upload()
        # if genes:
        # for gene in self.e_genes:
        #   gene.upload()

        # if genes & qtls:

        # if there's a problem with this, add to errors
        # push errors up to batch errors (just call that nice batch function 'set_errors')
        pass



    def add_all_snps(self):

        for gene_name, gene_obj in self.e_genes.iteritems():
            updated = gene_obj.update_qtls()
            self.e_genes[gene_name] = updated

        print "updated genes"

        return self

    # ----------------------------- MUTATORS ---------------------------------------- #

    # ----------------------------- GENEWEAVER DB HANDLING ----------------------- #
    def insert_publication(self):
        """ Given a dict whose keys refer to columns of the publication table,
            this function inserts a new publication into the db.
            Don't forget to commit changes after calling this function.

            # EDIT: update docstring to match function
        """
        query = 'INSERT INTO production.publication ' \
                '(pub_authors, pub_title, pub_abstract, pub_journal, ' \
                'pub_volume, pub_pages, pub_pubmed) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING pub_id;'

        vals = [self.publication['authors'], self.publication['title'],
                self.publication['abstract'], self.publication['journal'],
                self.publication['vol'], self.publication['pages'],
                self.publication['pubmed_id']]

        self.cur.execute(query, vals)

        pub_id = self.cur.fetchall()[0][0]
        self.publication_id = pub_id

class eGene:
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, parent, data=None):

        self.parent = parent
        self.batch = parent.batch
        self.tissue_name = parent.tissue_name  # NOTE: Batch + Uploader won't assume tissue type like this

        # still need to inherit database connection info from parent

        # remember to add a data check here for a dictionary type with all the right values
        self.raw_data = data
        self.gencode_id = None
        self.gene_symbol = None

        # additional gene info (probably not needed so long as gene already in GW)
        self.description = None
        self.ensembl_id = None
        self.entrez_id = None

        # error handling
        self.crit = []
        self.noncrit = []

        # store respective eQTL obj [only one stored at the moment, as tissue-specific]
        self.max_eQTL = None  # most significant QTL linked to this gene
        self.SNPs = {}  # {snp_name: eQTL obj,}  -  for later...

        self.setup_db()

    def setup_db(self):
        """  # sets all the global parameters for eGene obj
        """
        self.gencode_id = str(self.raw_data['gene'])
        self.gene_symbol = str(self.raw_data['gene_name'])

        self.create_eQTL()

    def create_eQTL(self, data=None):
        """ # data passed in with specific dictionary type (pass along from batch):

        {snp_id_1kg_project_phaseI_v3: RSID, orientation: str, gene_chr: int, rs_id_dbSNP142_GRCh37p13: RSID,
            gene_stop: int, tss_position: int, gene_q_value: float, alt: str, ref_factor: int,
            num_alt_per_site: int, minor_allele_count: int, min_p: float, snp_chrom: int, tss_distance: int,
            minor_allele_samples: int, gencode_attributes: str, ref: str, nom_thresh: float, is_chosen_snp: int,
            beta: float, snp: str, maf: float, gene_emp_p: float, p_value: float, has_best_p: int,
            gene: Gencode ID, gene_start: int, snp_pos: int, k: int, gene_source: str, n: int, se: float,
            gene_type: str, beta_noNorm: float, gene_name: Gene Symbol, t_stat: float}
        """
        if not data:
            qtl = eQTL(self, chosen=True)  # assumes that we are only adding the most significant QTL (self.max_eQTL)
            # update global vars
            self.max_eQTL = qtl
            self.SNPs[qtl.name] = qtl  # (just out of good practice, for the moment)
            self.update_GeneSet(qtl_name=qtl.name, qtl_obj=qtl)

        else:  # assumes that we are iterating through a list of SNPs for this gene [LATER]
            # use self.max_eQTL to hold most siginificant - check whether 'is_chosen_snp'
            pass

        pass

    def find_all_tissue_qtls(self):

        gene_tissues = self.parent.batch.search_single_tissue_eQTLs(self.tissue_name, self.gene_symbol)

        for qtl_raw in gene_tissues:
            qtl = eQTL(parent=self, beta=qtl_raw['beta'], chromosome=qtl_raw['chromosome'],
                       p_value=qtl_raw['pValue'], snp_id=qtl_raw['snpId'], start=qtl_raw['start'])
            self.SNPs[qtl_raw['snpId']] = qtl
            self.update_GeneSet(qtl_raw['snpId'], qtl)  # update list of e_qtls stored in GTExGeneSet

        return self

    def update_GeneSet(self, qtl_name=None, qtl_obj=None, gene_name=None, gene_obj=None):
        """ # updates GTExGeneSet data storage objs"""

        if qtl_name and qtl_obj:
            # update GTExGeneSet by passing along recently generated qtl
            self.parent.e_qtls[qtl_name] = qtl_obj

        if gene_name and gene_obj:
            # update GTExGeneSet by passing along recently generated gene
            self.parent.e_genes[gene_name] = gene_obj

    # def search_all_info(self):
    #     """ # goal is to pull / add info from batch.gene_info{} to reduce the number
    #         #   of lookups needed (+ speed things up a bit)
    #     """
    #     # the following is gene-specific info, that doesn't change across tissues
    #
    #     # check self.batch.gene_list to see if its already been looked up
    #     if self.gene_symbol in self.batch.gene_info.keys():  # if it has
    #         self.description = self.batch.gene_info[self.gene_symbol][0]
    #         self.ensembl_id = self.batch.gene_info[self.gene_symbol][1]
    #         self.entrez_id = self.batch.gene_info[self.gene_symbol][2]
    #         self.update_GeneSet(gene_name=self.gencode_id, gene_obj=self)
    #         print "REPEAT"
    #     else:
    #         temp = self.batch.search_gene_info(self.gene_symbol)
    #         print temp
    #         self.description = temp['description']
    #         self.ensembl_id = temp['ensemblId']
    #         self.entrez_id = temp['entrezGeneId']
    #         self.update_GeneSet(gene_name=self.gencode_id, gene_obj=self)
    #         self.batch.gene_info[self.gene_symbol] = (self.description, self.ensembl_id, self.entrez_id)
    #
    #     # if it has been looked up before:
    #     #   take info from self.batch.gene_list{} (avoiding repetitive queries)
    #     #   update all necessary global vars [GeneSet updates itself]
    #
    #     # otherwise:
    #     #   call stuff like self.batch.search_gene_info(), until you get what you need
    #     #   update all necessary global vars [GeneSet updates itself]
    #     #   call self.update_GeneSet() to update GTExGeneSet parent
    #     #   update self.batch.gene_list to include this new entry
    #
    #     pass

    # ------------------------- DATABASE MANAGEMENT / MUTATORS ---------------------- #

    def upload(self, add_all_snps=False):
        # uploads gene info -> GeneWeaver

        # if not add_all_snps:
            # call max qtl upload + upload this gene

        # if add_qtls & self.eQTLs:
        #   for each qtl in self.eQTLs
        #       qtl.upload()

        # else:
        #   upload self + all associated info (make calls to db functions)

        pass

class eQTL:
    """ Creates an eQTL object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """
    def __init__(self, parent, chosen=False, data=None):

        self.parent = parent
        self.gtex_gs = parent.parent
        self.tissue_name = parent.tissue_name
        self.gencode_id = parent.gencode_id
        self.gene_symbol = parent.gene_symbol

        # still need to inherit database connection info from parent
        self.raw_data = None
        self.name = None  # SNP identifier
        self.rsid = None
        self.p_value = None
        self.beta = None  # effect size
        self.snp_chrom = None
        self.snp_pos = None
        self.maf = None
        self.gene_type = None  # use when uploading

        # deal with 'None' condition | deal with data condition
        if chosen and not data:
            self.setup()
        else:  # come back to this later
            pass

        # pull all relevant information from parent, prepare for uploading

    def setup(self):
        self.raw_data = self.parent.raw_data
        self.name = str(self.raw_data['snp'])
        self.rsid = str(self.raw_data['rs_id_dbSNP142_GRCh37p13'])
        self.p_value = float(self.raw_data['p_value'])
        self.beta = float(self.raw_data['beta'])
        self.snp_chrom = self.raw_data['snp_chrom']
        self.snp_pos = self.raw_data['snp_pos']
        self.maf = self.raw_data['maf']
        self.gene_type = self.raw_data['gene_type']  # use when uploading

        # print "raw data", self.raw_data
        # print "name", self.name
        # print "rsid", self.rsid
        # print "p-val", self.p_value
        # print "beta", self.beta
        # print "snp_chrom", self.snp_chrom
        # print "snp_pos", self.snp_pos
        # print "maf", self.maf
        # print "gene type", self.gene_type

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
    g.database_setup()

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
    # g.search_gene_info('PTPLAD2')

def test_grooming():
    g = GTEx()
    g.groom_raw_data()

def test_search_pubmed():
    g = GTEx()
    g.search_pubmed_info(g.publication['pubmed_id'])

if __name__ == '__main__':
    # ACTIVELY WRITING / DEBUGGING METHODS
    # test_reading()
    # test_query()
    test_dbSetup()
    # test_grooming()
    # test_search_pubmed()

    # FUNCTIONING METHODS
    # test_errors()
    # test_getTissue()
    # test_getCurrTissue()
    # test_getTissueInfo()
    # test_searchGeneInfo()

