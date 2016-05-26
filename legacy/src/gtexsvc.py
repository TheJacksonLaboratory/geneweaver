# author: Astrid Moore
# date: 4/14/16
# version: 1.0
#
# [Astrid's notes]
# The purpose of the following file is to manage GTEx data. The first goal is to find a way of piping
# GTEx data efficiently through a GTEx object (with Batch-like handling held here for now, until larger rewrite). The
# second goal is to be able query the website directly using 'requests'. The third goal is to be able to
# "plug-and-play" a series of 'Uploader' objs
# [describe format of file input]

# REQ EDIT [5/12]- pull all tables required ONCE haha + at the beginning...
# limit GTEx Uploader objs to respective 'insert_*' functions
#   - can then simplify entire structure of GTEx Uploader subclasses,
#   replacing any 'SELECT'-based queries with a call to an 'update_tables()' func
#   - use 'update_tables()' to coordinate calls to 'request_*()' methods, which
#   will update a series of global dicts (from setup) [+ write resp. mutators]
#
#   - locate a larger data table in GTEx Portal to satisfy the needs of all
#   'search_*()' functions that are in place now; follow a similar pattern to above

import json
import requests  # downloads JSON files from web
import tarfile
import psycopg2
import config

import time  # TESTING PURPOSES
import progressbar  # TESTING PURPOSES


# import fish  # TESTING PURPOSES - funny progress bar


# class Batch

# class Uploader

# 'GTEx' = of a prospective superclass - Batch - to manage a large GTEx data
#   upload [187265 (27159 unique genes)] to GeneWeaver database

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
        self.all_gene_info = {}  # USAGE: {gene_symbol: {<gene info>},}  -  used in eGene
        # EDIT: rename self.raw_genesets -> self.GeneSets [primp up all these]
        self.raw_genesets = {}  # USAGE: {tissue_name: GTExObject,}

        self.get_tissue_info()  # populates: 'self.STATIC_TISSUES', + builds 'self.tissue_info'
        self.get_tissues_nomen()  # populates: self.tissue_types

        # database connection
        self.connection = None
        self.cur = None

        # publication info:
        #   {pubmed_id: {authors:", title:", abstract:", journal:", vol:", pages:", pmid:"},}
        self.publications = {}  # EDIT: rename self.Publications [+ clean up comments!]
        self.files_uri = {}  # {tissue_name: file_uri,}
        self.added_ids = {}  # {ode_ref_id: ode_gene_id,} - for all pairings added this session

        self.launch_connection()  # launch postgres (to connect with GeneWeaver database)

        # build repository
        # self.database_setup()

    def launch_connection(self):
        """ EDIT

            # ALREADY TESTED
        """
        data = config.get('db', 'database')
        user = config.get('db', 'user')
        password = config.get('db', 'password')
        host = config.get('db', 'host')

        print host

        # set up connection information
        cs = 'host=\'%s\' dbname=\'%s\' user=\'%s\' password=\'%s\'' % (host, data, user, password)

        try:
            self.connection = psycopg2.connect(cs)  # connect to geneweaver database
            self.cur = self.connection.cursor()
        except SyntaxError:  # cs most likely wouldn't be a useable string if wasn't able to connect
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

        # EDIT: do this automatically when you're initally grabbing tissue labels (find)

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

    # EDIT - RENAME: rewrite all functions to match 'request*'

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

        publication['pub_id'] = None
        publication['pub_pubmed'] = str(pubmed_id)
        publication['pub_pages'] = temp[publication['pub_pubmed']]['pages']
        publication['pub_title'] = temp[publication['pub_pubmed']]['title']
        publication['pub_journal'] = temp[publication['pub_pubmed']]['fulljournalname']
        publication['pub_volume'] = temp[publication['pub_pubmed']]['volume']

        authors = ""  # will hold a CSV list
        for auth in temp[publication['pub_pubmed']]['authors']:
            authors += auth['name'] + ', '
        publication['pub_authors'] = authors[:-2]

        if 'Has Abstract' in temp[publication['pub_pubmed']]['attributes']:
            res2 = requests.get(url_abs).content.split('\n\n')[-3]
            publication['pub_abstract'] = res2
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
        """ EDIT

            # conductor: simplify the role of each method call

            only use is to set up geneweaver's database (should be done only once)

            # sets where strength is too low (n<70) are not included

        """
        # self.groom_raw_data()  # [last run: 5/2/16] reads in file and identifies what is useful, writing results
        self.start = time.clock()  # TESTING PURPOSES
        for tissue in self.tissue_info:  # for each tissue (where n >= 70)
            if self.tissue_info[tissue]['has_egenes'] == 'True' and tissue != 'Thyroid' \
                    and tissue != 'Small_Intestine_Terminal_Ileum'  \
                    and tissue != 'Brain_Frontal_Cortex_BA9' and tissue != 'Vagina':
                # if self.tissue_info[tissue]['has_egenes'] == 'True' and tissue != 'Thyroid' and tissue != 'Testis':
                # iterating through the list of tissue files
                self.files_uri[str(tissue)] = {}
                fp = self.SAVE_SEARCH_DIR + tissue + "_Groomed.json"
                self.files_uri[str(tissue)]['file_uri'] = fp  # filename

                with open(fp, 'r') as data_file:
                    # grab file info and store it under a tissue name dict
                    qtls = json.load(data_file)  # load the file info
                    # create GTExGeneSet obj + respective eGenes
                    gs_tissue = GTExGeneSet(self, values=qtls[tissue], tissue_type=str(tissue))

                    # TESTING - remove later (no point storing everything in local memory!)
                    # self.raw_genesets[gs_tissue.tissue_name] = gs_tissue  # store GTExGeneSet obj globally
                    # print tissue, len(self.raw_genesets[gs_tissue.tissue_name].e_genes.keys()), \
                    #     "should equal ", self.tissue_info[gs_tissue.tissue_name]['eGene_count']
                    # # exit()  # TESTING PURPOSES
                    # print "AND should also equal", len(self.all_gene_info)


# Uses a "trickle-down" method for uploading data to GeneWeaver
class GTExGeneSet:  # GTExGeneSetUploaders
    """ ## Acts as an uploader interface for GTEx data -> GeneWeaver database
        ## specify param types, what happens, and how it passes info along

    """

    def __init__(self, batch, values, tissue_type):  # assumes a user file input
        print 'initializing', tissue_type, 'geneset...\n'
        # param input data - formatting checked here

        # inheritance
        self.batch = batch
        self.cur = batch.cur  # psycopg2 cursor obj
        self.connection = batch.connection  # psycopg2 connection obj -> GeneWeaver

        self.raw_values = values
        self.tissue_name = tissue_type  # NOTE: Batch + Uploader classes will handle this differently

        # GENESET - EDIT: put in a dictionary, like file?
        self.name = "[GTEx] " + tissue_type
        self.abbrev_name = batch.tissue_info[self.tissue_name]['tissue_abbrv']
        self.species = 2  # all GTEx is human
        self.thresh_type = '1'
        self.thresh = '0.05'
        self.gdb_id = 9  # gene type of geneset: GTEx
        self.usr_id = 15  # PERSONAL USER NO. ( Astrid )
        self.cur_id = 1  # uploaded as a public resource [might be 2]
        self.pubmed_id = '23715323'  # PubMed ID for GTEx Project
        self.grp_id = 15  # GTExTest [change when successful] - a.k.a gs_groups
        self.attribution_id = 15  # GTEx
        self.description = "GeneSet only representative of significant eGenes found in " \
                           "GTEx tissue '%s'. Each eGene's 'p-value' reflects the " \
                           "probability of the most significant SNP, or eQTL, being expressed " \
                           "in that eGene for this tissue." % self.tissue_name
        self.gs_gene_id_type = 0  # so long as gdb_id='Gene Symbol'

        self.count = None
        self.gs_id = None
        self.gsv_value_list = []
        self.gsv_source_list = []
        self.active_gene_pairs = {}  # {ode_ref_id: ode_gene_id,}  -  identical feature to batch, added_ids{}
        self.genesetID_geneID = {}  # {gs_id: ode_gene_id,}  -  to avoid duplicate values

        self.file = {'file_size': None, 'file_uri': None, 'file_contents': None,
                     'file_comments': None, 'file_id': None}

        self.publication = {}

        self.e_genes = {}  # USAGE: {gencode_id: eGene obj,}  -  gencode Id is tissue dependent
        self.e_qtls = {}  # USAGE: {snp: eQTL obj,} - for top-level access (otherwise already stored in eGene obj)

        self.geneweaver_setup()  # creates eGenes, along with respective eQTL

    def geneweaver_setup(self):
        """ EDIT

            Preps upload if setting up database.  ##
            # leave eQTL creation to eGene obj
            # and access / populate 'self.eQTLs' through each eGene obj
        """
        print 'setting up geneset...\n'
        # TESTING PURPOSES
        bar = progressbar.ProgressBar(maxval=len(self.raw_values)).start()

        # GENERATE GENES
        c = 0  # TESTING
        total = len(self.raw_values)  # TESTING
        for gene_data in self.raw_values:
            c += 1  # TESTING
            bar.update(c)  # TESTING
            time.sleep(0.001)  # TESTING: this is ugly! find an alternative
            self.create_eGene(gene_data)
        bar.finish()  # TESTING

        print "%s: genes created" % self.tissue_name

        # COUNT [file_size]
        self.count = len(self.e_genes)
        print "%s: num genes = %s" % (self.tissue_name, self.count)

        # FILE
        self.create_file()
        print "%s: file created" % self.tissue_name
        self.insert_file()
        print "%s: file inserted" % self.tissue_name

        # PUBLICATION
        self.create_publication()
        print "%s: publication created" % self.tissue_name
        self.insert_publication()  # updates self.publication['pub_id']
        print "%s: publication inserted" % self.tissue_name

        # GENESET
        self.insert_geneset()  # create geneset in GW
        print "%s: geneset inserted" % self.tissue_name

        # GENESET VALUES
        self.insert_geneset_values()  # calls eGene objs to add values
        print "%s: geneset values inserted" % self.tissue_name
        self.update_gsv_lists()  # update values stored for gsv_values_list + gsv_source_list
        print "%s: gsv lists updated" % self.tissue_name

    def create_eGene(self, data_dict):
        """ EDIT

        # data passed in with specific dictionary type (pass along from batch):

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

    def create_file(self):
        """ EDIT

            TEST required
        """

        if self.e_genes:
            contents = ''
            for gene in self.e_genes:
                curline = str(self.e_genes[gene].gene_symbol) + '\t' + str(self.e_genes[gene].max_eQTL.p_value) + '\n'
                contents += curline
            self.file['file_contents'] = contents
            self.file['file_size'] = self.count
            self.file['file_comments'] = ''
            self.file['file_uri'] = self.batch.files_uri[self.tissue_name]['file_uri']
        else:
            # EDIT - add error message that cant add file if there are no eGenes
            #   in GTExGeneSet - and to do that first
            print "FAILED CREATING FILE"

    def create_publication(self):
        """ EDIT

            TEST required
        """
        # EDIT: add error catching for self.pubmed_id entry
        self.publication = self.batch.search_pubmed_info(self.pubmed_id)  # PubMed ID for GTEx Project

    # ----------------------------- GENEWEAVER SETUP ----------------------------- #

    def check_success(self):  # needs updating!

        # gencode_headers = []  # TEMP
        # for gene in self.raw_values:  # TEMP
        #     gencode_headers.append(str(gene['gencodeId']))
        #
        # dup = []
        # for item, count in c.Counter(gencode_headers).items():  # definitely not the fastest way to check, use sets
        #     if count > 1:
        #         dup.append(item)
        #
        # if len(dup):
        #     err = "Error: Duplicate Gencode IDs (per tissue) were found during upload [%s].\n" % dup
        #     self.batch.set_errors(critical=err)
        #     print self.batch.get_errors()
        #     exit()
        # else:
        #     print "Yup\n"

        pass  # EDIT - rewrite

    def add_all_snps(self):

        for gene_name, gene_obj in self.e_genes.iteritems():
            updated = gene_obj.update_qtls()
            self.e_genes[gene_name] = updated

        print "updated genes"

        return self

    # ----------------------------- GENEWEAVER DB HANDLING ----------------------- #
    def insert_file(self):
        """ # EDIT

            Inserts a new row into the file table. Most of the columns for the file
            table are required as arguments.

        Returns
        -------
        file_id: File ID

        """
        self.cur.execute('set search_path = extsrc, production, odestatic;')

        query = 'INSERT INTO production.file ' \
                '(file_size, file_uri, file_contents, file_comments, ' \
                'file_created, file_changes) ' \
                'VALUES (%s, %s, %s, %s, NOW(), \'\') RETURNING file_id;'

        vals = [self.file['file_size'], self.file['file_uri'],
                self.file['file_contents'], self.file['file_comments']]

        self.cur.execute(query, vals)
        self.connection.commit()

        self.file['file_id'] = self.cur.fetchall()[0][0]

    def insert_publication(self):
        """ EDIT

            EDIT - update docstring to match function
            # TEST: not yet run
        """
        query = 'INSERT INTO production.publication ' \
                '(pub_authors, pub_title, pub_abstract, pub_journal, ' \
                'pub_volume, pub_pages, pub_pubmed) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING pub_id;'

        vals = [self.publication['pub_authors'], self.publication['pub_title'],
                self.publication['pub_abstract'], self.publication['pub_journal'],
                self.publication['pub_volume'], self.publication['pub_pages'],
                self.publication['pub_pubmed']]

        self.cur.execute(query, vals)
        self.connection.commit()

        self.publication['pub_id'] = self.cur.fetchall()[0][0]

    def insert_geneset(self):
        """ EDIT

            EDIT: update docstring to match function
            # TEST: not yet run
        """

        search_path = 'SET search_path = extsrc, production, odestatic;'

        query = 'INSERT INTO geneset ' \
                '(file_id, usr_id, cur_id, sp_id, gs_threshold_type, ' \
                'gs_threshold, gs_created, gs_updated, gs_status, ' \
                'gs_count, gs_uri, gs_gene_id_type, gs_name, ' \
                'gs_abbreviation, gs_description, gs_attribution, ' \
                'gs_groups, pub_id) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), \'normal\', ' \
                '%s, \'\', %s, %s, %s, %s, %s, %s, %s) RETURNING gs_id;'

        vals = [self.file['file_id'], self.usr_id, self.cur_id, self.species,
                self.thresh_type, self.thresh, self.count,
                self.gs_gene_id_type, self.name, self.abbrev_name,
                self.description, self.attribution_id, self.grp_id,
                self.publication['pub_id']]

        self.cur.execute(search_path)  # point to tables of interest
        self.cur.execute(query, vals)  # run insertion
        self.connection.commit()  # EDIT: more than one commit?

        self.gs_id = self.cur.fetchall()[0][0]

    def insert_geneset_values(self):
        """ EDIT

            # TEST required
        """
        bar = progressbar.ProgressBar(maxval=len(self.raw_values)).start()  # TESTING PURPOSES

        # send a call for each eGene in self.e_genes to insert_value() into GeneWeaver
        count = 0
        for gene in self.e_genes:
            count += 1
            bar.update(count)
            self.e_genes[gene].insert_gene()
            self.e_genes[gene].insert_value()
        bar.finish()

    def update_gsv_lists(self):  # EDIT: should simplifying this into one call...
        """ EDIT

            # Updates gsv_source_list and gsv_values_list
        """
        # UPDATE GSV_SOURCE_LIST
        query = 'UPDATE extsrc.geneset_value ' \
                'SET gsv_source_list = %s ' \
                'WHERE gs_id = %s;'
        vals = [self.gsv_source_list, self.gs_id]
        self.cur.execute(query, vals)
        self.connection.commit()

        # UPDATE GSV_VALUE_LIST
        query = 'UPDATE extsrc.geneset_value ' \
                'SET gsv_value_list = %s ' \
                'WHERE gs_id = %s;'
        vals = [self.gsv_value_list, self.gs_id]
        self.cur.execute(query, vals)
        self.connection.commit()

        # UPDATE GSV_DATE
        query = 'UPDATE extsrc.geneset_value ' \
                'SET gsv_date = NOW() ' \
                'WHERE gs_id = %s;'
        vals = [self.gs_id]
        self.cur.execute(query, vals)
        self.connection.commit()

    # EDIT
    def update_geneset(self, gs_name=None, gs_abbr=None, gs_description=None, sp_id=None,
                       pub_id=None, gs_groups=None, thresh_type=None, thresh=None,
                       gs_gene_idType=None, gs_count=None):
        """ Using paramaters provided, this function modifies respective global fields, and updates
            its representative GeneSet on GeneWeaver.

            # EDIT - more detail: defaults to global GeneSet params; fix query statement (won't run)
            # NOT TESTED

        Parameters
        ----------
        gs_name: GeneSet name
        gs_abbr: abbreviated GeneSet name
        gs_description: GeneSet description
        sp_id: GeneSet Species ID
        pub_id: GeneSet Publication ID
        gs_groups: GeneSet Group ID
        thresh_type: GeneSet Threshold Type
        thresh: GeneSet Threshold Value
        gs_gene_idType: GeneSet Gene ID Type
        gs_count: number of Genes in GeneSet
        """
        print "Not finished!! (update_geneset)"
        exit()
        # check to see which params entered
        options = [gs_name, gs_abbr, gs_description, sp_id, pub_id,
                   gs_groups, thresh_type, thresh, gs_gene_idType, gs_count]

        # make a dictionary to track general geneset info
        temp = {'gs_name': self.name, 'gs_abbr': self.abbrev_name,
                'gs_description': self.description, 'sp_id': self.species,
                'pub_id': self.publication['pub_id'], 'gs_groups': self.grp_id,
                'thresh_type': self.thresh_type, 'thresh': self.thresh,
                'gs_gene_idType': self.gs_gene_id_type, 'gs_count': gs_count}

        # EDIT - FIX THIS QUERY
        # query = 'UPDATE production.geneset ' \
        #         '(gs_name, gs_abbreviation, gs_description, sp_id, ' \
        #         'pub_id, gs_groups, gs_threshold_type, gs_threshold, ' \
        #         'gs_gene_id_type, gs_count, gs_updated) ' \
        #         'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW()) ' \
        #         'WHERE gs_id = %s'

        for option, count in options, range(len(options)):
            # print count  # EDIT: check to make sure that we are starting at zero
            if not option:
                options[count] = temp[option]  # EDIT: update options to reflect gs vals
                temp[option] = option.value  # EDIT: check to see if this works to update globals
            else:  # TESTING
                # print 'update_geneset param:', option  # TESTING
                pass

        options.append(self.gs_id)  # TESTING see whether this works!
        self.cur.execute(query, options)
        self.connection.commit()


class eGene:
    """ Creates an eGene object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, geneset, data=None):
        # print 'initializing gene...'
        self.geneset = geneset  # GeneSet
        self.batch = geneset.batch
        self.tissue_name = geneset.tissue_name  # NOTE: Batch + Uploader won't assume tissue type like this
        # remember to add a data check here later for a dictionary type with all the right values
        self.raw_data = data

        # DATABASE INFO
        self.cur = geneset.cur
        self.connection = geneset.connection

        # GENE INFO
        self.ode_ref_id = None  # gencode ID
        self.ode_gene_id = None
        self.in_threshold = 't'  # EDIT: double-check this
        self.gencode_id = None
        self.gene_symbol = None
        self.name = None
        self.gene_info = {'chromosome': None, 'description': None, 'end': None,
                          'ensembl_id': None, 'entrez_id': None, 'start': None,
                          'status': None, 'strand': None, 'type': None,
                          'accession': None, 'ode_gene_id': None}

        # store respective eQTL obj [only one stored at the moment, as tissue-specific]
        self.max_eQTL = None  # most significant QTL linked to this gene
        self.SNPs = {}  # {snp_name: eQTL obj,}  -  for later...

        self.found = False  # search progress identifier
        self.already_created = False  # creation identifier
        self.setup_db()

    def setup_db(self):
        """  # sets all the global parameters for eGene obj
            # returns True if ready, returns False if a new gene needs to be created
        """
        # print 'setting up gene...\n'
        self.gencode_id = str(self.raw_data['gene'])
        self.ode_ref_id = self.gencode_id
        self.gene_info['accession'] = str(self.gencode_id)
        self.gene_symbol = str(self.raw_data['gene_name'])
        self.name = str("" + self.gene_symbol + '-GTEx')

        self.create_eQTL()  # assign QTL obj

        # check GTEx gene dictionary / try and find further info online, if self.found=false?
        while True:  # TEST TESTING: This is not working how we want it to
            if self.found:
                break
            self.find_geneID_gtex()
            if self.found:
                break
            self.more_gtex_info()  # returns True if gene_info{} is filled
            if self.found:
                break
            # some queries are contingent upon existence of gene_info{}
            # if self.gene_info['status'] == 'KNOWN':  # EDIT ? trying to narrow it down a little further
            self.find_geneID_entrez()
            if self.found:
                break
            self.find_geneID_ensembl()
            if self.found:
                break
            self.find_geneID_symbol()
            if self.found:
                break
            self.find_geneID_rsid()

            break  # only go through this loop once, terminating if / when self.found = True

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
        # print 'creating eQTL...'
        if not data:
            qtl = eQTL(self, chosen=True)  # assumes that we are only adding the most significant QTL (self.max_eQTL)
            # update global vars
            self.max_eQTL = qtl
            self.SNPs[qtl.name] = qtl  # (just out of good practice, for the moment)
            self.push_to_GeneSet(qtl_name=qtl.name, qtl_obj=qtl)  # keep GTExGeneSet up to date

            # else:  # assumes that we are iterating through a list of SNPs for this gene [LATER]  # EDIT
            #     # use self.max_eQTL to hold most siginificant - check whether 'is_chosen_snp'

    def find_all_tissue_qtls(self):

        # gene_tissues = self.geneset.batch.search_single_tissue_eQTLs(self.tissue_name, self.gene_symbol)
        #
        # for qtl_raw in gene_tissues:
        #     qtl = eQTL(gene=self, beta=qtl_raw['beta'], chromosome=qtl_raw['chromosome'],
        #                p_value=qtl_raw['pValue'], snp_id=qtl_raw['snpId'], start=qtl_raw['start'])
        #     self.SNPs[qtl_raw['snpId']] = qtl
        #     self.update_GeneSet(qtl_raw['snpId'], qtl)  # update list of e_qtls stored in GTExGeneSet
        #
        # return self
        pass

    def push_to_GeneSet(self, qtl_name=None, qtl_obj=None, gene_name=None, gene_obj=None):
        """ # updates GTExGeneSet data storage objs"""

        if qtl_name and qtl_obj:
            # update GTExGeneSet by passing along recently generated qtl
            self.geneset.e_qtls[qtl_name] = qtl_obj

        if gene_name and gene_obj:
            # update GTExGeneSet by passing along recently generated gene
            self.geneset.e_genes[gene_name] = gene_obj

    # ---------------------------- GENEWEAVER HANDLERS ----------------------------#

    def insert_value(self):
        """ EDIT

            # EDIT - lookup ode_gene_id + [ode_ref_id] for 'gene_id', [name] 'below
            # EDIT: append each ode_ref_id (final) to gsv_source_list variable
            #   (stored at GeneSet level)
            # EDIT: make global field for gsv_source_list in GTExGeneSet

            # NOT TESTED
        """
        exists = self.check_geneset_value_exists()
        if exists:
            return

        # print 'starting to insert gene value...'
        query = 'INSERT INTO extsrc.geneset_value ' \
                '(gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list, ' \
                'gsv_value_list, gsv_in_threshold, gsv_date) ' \
                'VALUES (%s, %s, %s, 0, %s, %s, %s, NOW());'

        vals = [self.geneset.gs_id, self.ode_gene_id, self.max_eQTL.p_value,
                [self.ode_ref_id], [float(self.max_eQTL.p_value)], self.in_threshold]

        # if self.geneset.gs_id in self.geneset.genesetID_geneID.keys():
        #     if self.geneset.genesetID_geneID[self.geneset.gs_id] == self.ode_gene_id:
        #         self.delete_gene()  # delete old gene w/ faulty pairing
        #         self.found = False
        #         self.insert_gene()  # insert new gene
        #         self.cur.execute(query, vals)
        #         self.connection.commit()
        # else:
        #     self.cur.execute(query, vals)
        #     self.connection.commit()

        self.cur.execute(query, vals)
        self.connection.commit()

        # Update GeneSet so we can update 'gsv_source_list' + 'gsv_value_list' later
        self.geneset.gsv_source_list.append(self.ode_ref_id)
        self.geneset.gsv_value_list.append(self.max_eQTL.p_value)

    def insert_gene(self):
        """ EDIT

            # NOT TESTED
            # assume that we've searched in every other table for viable ode_gene_id before this

            # ode_pref should only be true in the case where gdb_id = 7 (gene symbol table)

            # make sure that self.found stays up to date! (tracks whether ode_gene_id assigned)
        """
        search_path = 'SET search_path = extsrc, production, odestatic;'
        self.cur.execute(search_path)

        # pres = self.check_gene_exists()  # TESTING: EDIT this is overkill, remove
        # if pres:  # if the gene is already in the geneset, pass
        #     print "gene: ", self.gene_symbol, "has already been added"
        #     return False

        if self.already_created:
            return

        if self.found:  # assumes that we found an ode_gene_id
            # INSERT GENE
            # check to make sure that it's not already in gtex table

            # otherwise, if this pair hasn't been already added...
            query = 'INSERT INTO gene ' \
                    '(ode_gene_id, ode_ref_id, gdb_id, sp_id, ode_pref,' \
                    ' ode_date) VALUES (%s, %s, %s, %s, false, NOW());'
            vals = [self.ode_gene_id, self.ode_ref_id, self.geneset.gdb_id,
                    self.geneset.species]
            self.cur.execute(query, vals)
            self.connection.commit()  # check to see if more than one is required
            self.batch.added_ids[self.ode_ref_id] = self.ode_gene_id
            self.geneset.active_gene_pairs[self.ode_ref_id] = self.ode_gene_id

            # GENE_INFO: if pairing exists, then so does gene info for that ode_gene_id

            print "GENE: %s (%s) successfully inserted!" % (self.gencode_id, self.gene_symbol)

        else:  # assumes that we need to make a new ode_gene_id
            # INSERT GENE  (assumes that ode_ref_id<->ode_gene_id hasn't been made before)
            query_gene = 'INSERT INTO gene ' \
                         '(ode_ref_id, gdb_id, sp_id, ode_pref,' \
                         ' ode_date) VALUES (%s, %s, %s, false, NOW()) ' \
                         'RETURNING ode_gene_id;'
            gene_vals = [self.ode_ref_id, self.geneset.gdb_id, self.geneset.species]

            self.cur.execute(query_gene, gene_vals)  # inserts gene
            self.connection.commit()  # check to see if more than one is required
            self.ode_gene_id = str(self.cur.fetchall()[0][0])  # EDIT: check to make sure
            self.gene_info['ode_gene_id'] = self.ode_gene_id
            print 'new ODE_GENE_ID: %s' % self.ode_gene_id
            self.batch.added_ids[self.ode_ref_id] = self.ode_gene_id
            self.geneset.active_gene_pairs[self.ode_ref_id] = self.ode_gene_id
            self.geneset.genesetID_geneID[self.geneset.gs_id] = self.ode_gene_id
            self.found = True

            # INSERT GENE_INFO  (assumes that this is a new ode_gene_id)
            query_gene_info = 'INSERT INTO gene_info ' \
                              '(ode_gene_id, gi_accession, gi_symbol, gi_name, gi_description,' \
                              ' gi_type, gi_chromosome, gi_start_bp, gi_end_bp,' \
                              ' gi_strand, sp_id, gi_date) ' \
                              'VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW());'
            gene_info_vals = [self.ode_gene_id, self.gene_info['accession'], self.gene_symbol, self.name,
                              self.gene_info['description'], self.gene_info['type'],
                              self.gene_info['chromosome'],
                              self.gene_info['start'], self.gene_info['end'],
                              self.gene_info['strand'], self.geneset.species]

            self.cur.execute(query_gene_info, gene_info_vals)  # inserts gene_info\
            self.connection.commit()  # check to see if more than one is required

            print "GENE: %s (%s) successfully inserted!" % (self.gencode_id, self.gene_symbol)

    def check_gene_exists(self):  # pretty much does exactly the same thing as the gtex searcher
        """EDIT"""

        query = 'SELECT ode_gene_id, ode_ref_id ' \
                'FROM extsrc.gene ' \
                'WHERE ode_gene_id = %s ' \
                'AND ode_ref_id = %s ' \
                'AND gdb_id = %s ' \
                'AND sp_id = %s;'

        vals = [self.ode_gene_id, self.ode_ref_id, self.geneset.gdb_id, self.geneset.species]
        self.cur.execute(query, vals)
        res = self.cur.fetchall()

        if len(res):
            return True
        else:
            return False
            # EDIT: add error message updating (batch)

    def check_geneset_value_exists(self):
        """EDIT"""
        query = 'SELECT ode_gene_id ' \
                'FROM extsrc.geneset_value ' \
                'WHERE ode_gene_id = %s ' \
                'AND gs_id = %s;'

        vals = [self.ode_gene_id, self.geneset.gs_id]
        self.cur.execute(query, vals)
        res = self.cur.fetchall()

        if len(res):
            return True
        else:
            return False
            # EDIT: add error message updating (batch)

    def delete_gene(self):
        """ EDIT
        """

        query = 'DELETE FROM extsrc.gene ' \
                'WHERE ode_ref_id = %s ' \
                'AND ode_gene_id = %s;'

        self.cur.execute(query, [self.ode_ref_id, self.ode_gene_id])
        self.connection.commit()

    def find_geneID_gtex(self):
        """ EDIT

            # "find ode_gene_id in GTEx group in Geneweaver"
            # only looks among those genes that are part of GTEx

            GTEx: gdb_id=9
        """
        # add items using gencode id or symbols (distinct)...
        query = 'SELECT ode_ref_id, ode_gene_id ' \
                'FROM extsrc.gene ' \
                'WHERE sp_id=%s AND gdb_id=%s ' \
                'AND ode_ref_id=%s;'

        vals = [self.geneset.species, 9, self.ode_ref_id]
        self.cur.execute(query, vals)

        res = self.cur.fetchall()
        if len(res):  # then we found results for an existing eGene
            self.already_created = True
            for datum in res:
                if datum[1] in self.geneset.active_gene_pairs.values():
                    continue
                else:
                    self.found = True
                    self.ode_gene_id = res[0][1]
                    self.gene_info['ode_gene_id'] = self.ode_gene_id
                    # print 'found:', 'existing in gtex test set'
                    return True
        return False

    def find_geneID_symbol(self):
        """ EDIT

            # "find ode_gene_id in Gene Symbol group in Geneweaver"
            # only looks among those genes that are part of Gene Symbol table

            Gene Symbol: gdb_id=7
        """
        # GENE SYMBOL
        query = 'SELECT ode_ref_id, ode_gene_id, ode_pref ' \
                'FROM extsrc.gene ' \
                'WHERE sp_id=%s AND gdb_id=%s ' \
                'AND ode_ref_id=%s;'

        geneID_query = 'SELECT ode_ref_id, ode_gene_id ' \
                       'FROM extsrc.gene ' \
                       'WHERE sp_id = %s ' \
                       'AND ode_pref=true ' \
                       'AND gdb_id=%s ' \
                       'AND ode_gene_id IN %s;'

        sym_vals = [self.geneset.species, 7, self.gene_symbol]
        self.cur.execute(query, sym_vals)
        sym_res = self.cur.fetchall()  # [(ode_gene_id, ode_pref)]

        if len(sym_res) and sym_res[0][2] == 't':  # if query is successful + ode_pref=True
            for sym_pair in sym_res:
                if sym_pair[1] in self.geneset.active_gene_pairs.values():
                    continue
                else:
                    self.found = True
                    self.ode_gene_id = sym_res[0][1]
                    self.gene_info['ode_gene_id'] = self.ode_gene_id
                    # print 'found:', 'symbol'
                    return True  # truncate search

        # SWEEP GENE SYMBOL FOR VALID ODE_GENE_ID [where ode_pref=True]
        elif len(sym_res):  # if query successful, but ode_pref=False
            # so, if we were able to find a gene id, but it wasn't preferred...
            # look up the ode_gene_id again, looking for one where ode_pref=True
            gene_ids = []
            for res in sym_res:  # for each (ode_gene_id, ode_ref_id) pairing in results
                gene_ids.append(res[1])

            id_vals = [self.geneset.species, 7, tuple(gene_ids)]
            self.cur.execute(geneID_query, id_vals)  # Gene Symbol lookup by ode_gene_id

            id_res = self.cur.fetchall()
            for id_pair in id_res:
                if id_pair[1] in self.geneset.active_gene_pairs.values():  # check within tissue
                    continue  # no point in taking duplicates for each gene, if we can help it!
                else:
                    self.found = True
                    self.ode_gene_id = id_res[0][1]  # take the first of all results...
                    self.gene_info['ode_gene_id'] = self.ode_gene_id
                    # print "ID SEARCH:", self.ode_ref_id, self.ode_gene_id
                    # print 'found:', 'symbol'
                    return True

        return False

    def find_geneID_entrez(self):
        """ EDIT

            # "find ode_gene_id in Entrez group in Geneweaver"
            # only looks among those genes that are part of Entrez table
            # NOTE: more_gtex_info must be called before 'find' functions

            Entrez: gdb_id = 1
        """
        # ENTREZ
        query = 'SELECT ode_ref_id, ode_gene_id ' \
                'FROM extsrc.gene ' \
                'WHERE sp_id=%s AND gdb_id=%s ' \
                'AND ode_ref_id=%s;'

        if self.gene_info['entrez_id']:
            entrez_vals = [self.geneset.species, 1, str(self.gene_info['entrez_id'])]
            self.cur.execute(query, entrez_vals)
            entrez_res = self.cur.fetchall()

            if len(entrez_res):
                for entrez in entrez_res:
                    if entrez[1] in self.geneset.active_gene_pairs.values():
                        continue
                    else:
                        self.found = True
                        self.ode_gene_id = entrez_res[0][1]
                        self.gene_info['ode_gene_id'] = self.ode_gene_id
                        # print "ENTREZ SEARCH:", self.ode_ref_id, self.ode_gene_id
                        # print 'found: ', 'entrez'
                        return True

        return False

    def find_geneID_ensembl(self):
        """ EDIT

            # "find ode_gene_id in Ensembl group in Geneweaver"
            # only looks among those genes that are part of Ensembl table(s)
            # NOTE: more_gtex_info must be called before 'find' functions

            Ensembl Protein: gdb_id = 3
            Ensembl Gene: gdb_id = 2
        """
        query = 'SELECT ode_ref_id, ode_gene_id ' \
                'FROM extsrc.gene ' \
                'WHERE sp_id=%s AND gdb_id=%s ' \
                'AND ode_ref_id=%s;'

        if self.gene_info['ensembl_id']:
            # ENSEMBL GENE
            gene_vals = [self.geneset.species, 2, str(self.gene_info['ensembl_id'])]
            self.cur.execute(query, gene_vals)
            gene_res = self.cur.fetchall()
            if len(gene_res):
                for gene in gene_res:
                    if gene[1] in self.geneset.active_gene_pairs.values():
                        continue
                    else:
                        self.found = True
                        self.ode_gene_id = gene_res[0][1]
                        self.gene_info['ode_gene_id'] = self.ode_gene_id
                        # print "ENSEMBL SEARCH:", self.ode_ref_id, self.ode_gene_id  # TESTING
                        # print 'found:', 'ensembl gene'
                        return True  # no need to continue searching!

            # ENSEMBL PROTEIN (if Ensembl Gene lookup was unsuccessful)
            protein_vals = [self.geneset.species, 3, str(self.gene_info['ensembl_id'])]
            self.cur.execute(query, protein_vals)
            protein_res = self.cur.fetchall()
            if len(protein_res):
                for protein in protein_res:
                    if protein[1] in self.geneset.active_gene_pairs.values():
                        continue
                    else:
                        self.found = True
                        self.ode_gene_id = protein_res[0][1]
                        self.gene_info['ode_gene_id'] = self.ode_gene_id
                        # print "ENSEMBL SEARCH:", self.ode_ref_id, self.ode_gene_id  # TESTING
                        # print 'found:', 'ensembl protein'
                        return True
        return False

    def find_geneID_rsid(self):
        """ EDIT

            # "find ode_gene_id in Single Nucleotide Polymorphism group in Geneweaver"
            # only looks among those genes that are part of SNP table
            # NOTE: eGene must contain eQTL with an RSID

            Single Nucleotide Polymorphism: gdb_id=26
        """
        # SINGLE NUCLEOTIDE POLYMORPHISM
        query = 'SELECT ode_ref_id, ode_gene_id ' \
                'FROM extsrc.gene ' \
                'WHERE sp_id=%s AND gdb_id=%s ' \
                'AND ode_ref_id=%s;'

        if self.max_eQTL.rsid:  # check to make sure QTL has rsid
            rsid_vals = [self.geneset.species, 26, self.max_eQTL.rsid]
            self.cur.execute(query, rsid_vals)
            rsid_res = self.cur.fetchall()
            if len(rsid_res):
                for rsid in rsid_res:
                    if rsid in self.geneset.active_gene_pairs.values():
                        continue
                    else:
                        self.found = True
                        self.ode_gene_id = rsid_res[0][1]
                        self.gene_info['ode_gene_id'] = self.ode_gene_id
                        # print "RSID SEARCH:", self.ode_ref_id, self.ode_gene_id
                        # print 'found:', 'rsid'
                        return True
        return False

    def more_gtex_info(self):
        """ EDIT

            # NOT TESTED

            # goal is to pull / add info from batch.gene_info{} to reduce the number
            #   of lookups needed (+ speed things up a bit)

            # if it has been looked up before:
            #   take info from self.batch.gene_list{} (avoiding repetitive queries)
            #   update all necessary global vars [GeneSet updates itself]

            # otherwise:
            #   call stuff like self.batch.search_gene_info(), until you get what you need
            #   update all necessary global vars [GeneSet updates itself]
            #   call self.update_GeneSet() to update GTExGeneSet parent
            #   update self.batch.gene_list to include this new entry
        """
        # print 'checking GTEx sources for gene info...'
        # the following is gene-specific info, that doesn't change across tissues
        if self.gencode_id in self.batch.all_gene_info.keys():  # if it has
            self.gene_info['chromosome'] = self.batch.all_gene_info[self.gencode_id]['chromosome']
            self.gene_info['description'] = self.batch.all_gene_info[self.gencode_id]['description']
            self.gene_info['end'] = self.batch.all_gene_info[self.gencode_id]['end']
            self.gene_info['ensembl_id'] = self.batch.all_gene_info[self.gencode_id]['ensembl_id']
            self.gene_info['entrez_id'] = self.batch.all_gene_info[self.gencode_id]['entrez_id']
            self.gene_info['start'] = self.batch.all_gene_info[self.gencode_id]['start']
            self.gene_info['status'] = self.batch.all_gene_info[self.gencode_id]['status']
            self.gene_info['strand'] = self.batch.all_gene_info[self.gencode_id]['strand']
            self.gene_info['type'] = self.batch.all_gene_info[self.gencode_id]['type']

            batch_geneID = self.batch.all_gene_info[self.gencode_id]['ode_gene_id']
            if batch_geneID and (batch_geneID not in self.geneset.active_gene_pairs.values()):
                self.ode_gene_id = self.batch.all_gene_info[self.gencode_id]['ode_gene_id']
                self.found = True
                # print 'found:', 'gtex info'
                return
            else:
                # EDIT: error message handling
                return

        elif not self.found:  # if the ode_gene_id wasn't found... look up more info
            temp = self.batch.search_gene_info(self.gene_symbol)  # search GTEx Portal

            if len(temp):  # if search in GTEx Portal was successful...
                self.gene_info['chromosome'] = str(temp['chromosome'])
                self.gene_info['end'] = str(temp['end'])
                self.gene_info['ensembl_id'] = str(temp['ensemblId'])
                self.gene_info['entrez_id'] = str(temp['entrezGeneId'])
                self.gene_info['start'] = str(temp['start'])
                self.gene_info['status'] = str(temp['status'])
                self.gene_info['type'] = str(temp['type'])
                self.gene_info['description'] = temp['description']

                for gene in self.gene_info:
                    if not self.gene_info[gene]:
                        self.gene_info[gene] = ""

                if not self.gene_info['description']:
                    desc = str("[Ensembl ID: %s] [Entrez ID: %s]" % (self.gene_info['ensembl_id'],
                                                                     self.gene_info['entrez_id']))
                    self.gene_info['description'] = desc

                if str(temp['strand']) == "+":
                    self.gene_info['strand'] = '1'
                elif str(temp['strand']) == "-":
                    self.gene_info['strand'] = '-1'

                self.batch.all_gene_info[self.gencode_id] = self.gene_info
            else:
                # EDIT: Add error handling here
                print "more_gtex_info: Unable to find further information for gene '%s'" % self.gene_symbol


class eQTL:
    """ Creates an eQTL object that holds all representative information identified in
        GTEx Portal. Takes a list of values and assigns each value to its respective
        global variable.
    """

    def __init__(self, gene, chosen=False, data=None):

        self.gene = gene  # eGene obj
        self.geneset = gene.geneset
        self.tissue_name = gene.tissue_name
        self.gencode_id = gene.gencode_id
        self.gene_symbol = gene.gene_symbol

        # still need to inherit database connection info from parent

        # EDIT consolidate the following block -> dict
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

    def setup(self):
        # pull all relevant information from parent, prepare for uploading
        self.raw_data = self.gene.raw_data
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
