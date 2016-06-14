# author: Astrid Moore
# date: 5/9/16
# version: 1.0

import progressbar
import time
import config
import psycopg2
import requests
import json

class PsyGeNET:

	def __init__(self):
		# directory fields
		self.ROOT_DIR = '/Users/Asti/geneweaver/psygenet/datasets/psygenet.txt'
		self.SAVE_DIR = '/Users/Asti/geneweaver/psygenet/psygenet-results/'

		# database connection fields
		self.connection = None
		self.cur = None

		# data processing fields
		self.raw_data = {}	# {Gene_Id: {Gene_Symbol, Gene_Description, Disease_Id, DiseaseName, 
							#			 PsychiactricDisorder, Source_Id, 'Score'},}
		self.raw_headers = [] 
		self.disorder_genesets = {}	 # {disease_id: PsyGeneSet obj,}
		self.disease_map = {}  # {disease_id: [disease_name, psych_disorder],}
		self.source_types = {'CTD': [2], 'ALL': [1, 2, 3], 'CURATED': [2], 'MODELS': [1, 3], \
							 'PsyCUR': [2], 'GAD': [2]}	 # {source_id: sp_id,}

		# error handling
		self.crit = []
		self.noncrit = []

		# launch connection to GeneWeaver database
		self.launch_connection()

		# gather PubMed info about Psygenet
		self.publication = {}
		self.pubmed_id = 25964630
		self.search_pubmed(self.pubmed_id)

		self.test_count = {}  # TESTING PURPOSES

	def launch_connection(self):
		""" EDIT

			# ALREADY TESTED
		"""
		data = config.get('db', 'database')
		user = config.get('db', 'user')
		password = config.get('db', 'password')
		host = config.get('db', 'host')

		print host  # TESTING

		# set up connection information
		cs = 'host=\'%s\' dbname=\'%s\' user=\'%s\' password=\'%s\'' % (host, data, user, password)

		try:
			self.connection = psycopg2.connect(cs)	# connect to geneweaver database
			self.cur = self.connection.cursor()
		except SyntaxError:	 # cs most likely wouldn't be a useable string if wasn't able to connect
			print "Error: Unable to connect to database."
			exit()

	def search_pubmed(self, pmid):
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
		# URL for pubmed article summary info
		url = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?'
			   'retmode=json&db=pubmed&id=%s') % str(pmid)
		# NCBI eFetch URL that only retrieves the abstract
		url_abs = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
				   '?rettype=abstract&retmode=text&db=pubmed&id=%s') % str(pmid)

		res = requests.get(url).content
		temp = json.loads(res)['result']

		self.publication['pub_id'] = None
		self.publication['pub_pubmed'] = str(pmid)
		self.publication['pub_pages'] = temp[self.publication['pub_pubmed']]['pages']
		self.publication['pub_title'] = temp[self.publication['pub_pubmed']]['title']
		self.publication['pub_journal'] = temp[self.publication['pub_pubmed']]['fulljournalname']
		self.publication['pub_volume'] = temp[self.publication['pub_pubmed']]['volume']

		authors = ""  # will hold a CSV list
		for auth in temp[self.publication['pub_pubmed']]['authors']:
			authors += auth['name'] + ', '
		self.publication['pub_authors'] = authors[:-2]

		if 'Has Abstract' in temp[self.publication['pub_pubmed']]['attributes']:
			res2 = requests.get(url_abs).content.split('\n\n')[-3]
			self.publication['pub_abstract'] = res2
		else:
			er = ('Error: The PubMed info retrieved from NCBI was incomplete. No '
				  'abstract data will be attributed to this GeneSet.')
			self.set_errors(noncritical=er)

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

	def read_file(self, fp):
		""" Reads in from a source text file and outputs organized data	 # EDIT

		# separate each column into lists (make sure the same length before proceeding)

		Parameters
		----------
		fp: filepath to read (string)

		Returns
		-------
		psy_ids: list of Psygenet IDs
		symbols: list of Gene Symbols
		descs: list of Gene Descriptions
		disease_ids: list of Psygenet Disease IDs
		disease_names: list of Psygenet Disease Names
		psych_disorders: list of Psygenet Psychiatric Disorders 
		source_ids: list of Psygene Source IDs
		scores: list of Psygenet Scores (relative gene rank ratio)

		"""
		# temporary fields
		psy_ids = []
		symbols = []
		descs = []
		disease_ids = []
		disease_names = []
		psych_disorders = []
		source_ids = []
		scores = []

		with open(fp, 'r') as file_path:
			lines = file_path.readlines()
			self.raw_headers = lines[0].strip().split('\t')

			for line in lines[1:]:	# for all the lines following the headers
				tmp = line.strip().split('\t')
				psy_ids.append(tmp[0])
				symbols.append(tmp[1])
				descs.append(tmp[2])
				disease_ids.append(tmp[3])
				disease_names.append(tmp[4])
				psych_disorders.append(tmp[5])
				source_ids.append(tmp[7])
				scores.append(tmp[8])

				if tmp[3] not in self.disease_map.keys():
					self.disease_map[tmp[3]] = [tmp[4], tmp[5]]

			check_inputs = set([len(symbols), len(descs), len(disease_ids), 
							len(disease_names), len(psych_disorders),
							len(source_ids), len(scores), len(psy_ids)])

			if len(check_inputs) > 1:
				self.set_errors(critical = 'Error: cannot take empty values. Check the check_input' \
											' and please try again.')
				print self.batch.get_errors()[0]  # print critical errors for the user
				exit()
			
		return psy_ids, symbols, descs, disease_ids, disease_names, psych_disorders, source_ids, scores

	def groom_raw_data(self):
		# adds info to existing PsyGeneSet / creates a new one and adds more to it
		psy_ids, symbols, descs, disease_ids, disease_names, psych_disorders, \
			source_ids, scores = self.read_file(self.ROOT_DIR)	

		print "Creating PsyGeneSets..."	 # TESTING PURPOSES
		bar = progressbar.ProgressBar(maxval=len(symbols)).start()	# TESTING PURPOSES
		
		# traverse lists in parallel
		for x in range(len(symbols)):  # for each row of raw data
			# if PsyGeneSet obj doesn't yet exist for that disorder
			if disease_ids[x] not in self.disorder_genesets.keys() and source_ids[x] not in ['ALL', 'CURATED']:
				geneset = PsyGeneSet(self, disease_ids[x])	# make a new PsyGeneSet obj
				# populate new geneset with this row of data
				geneset.add_gene(symbol=symbols[x], desc=descs[x], score=scores[x],
					source_id=source_ids[x], psy_id=psy_ids[x])
				# add new PsyGeneSet obj to self.disorder_genesets
				self.disorder_genesets[disease_ids[x]] = geneset
			elif source_ids[x] not in ['ALL', 'CURATED']: # otherwise, PsyGeneSet obj already exists
				# update PsyGeneSet obj with new info
				self.disorder_genesets[disease_ids[x]].add_gene(symbol=symbols[x], 
					desc=descs[x], score=scores[x], source_id=source_ids[x], psy_id=psy_ids[x])

			bar.update(x)  # TESTING PURPOSES
			time.sleep(0.001)  # TESTING PURPOSES: ugly though
		bar.finish()  # TESTING PURPOSES

	def database_setup(self):
		self.groom_raw_data()

		# iterate through PyGeneSets, making calls to upload them to GeneWeaver
		for name, geneset in self.disorder_genesets.iteritems():
			geneset.geneweaver_setup()	# prep GeneWeaver fields in PsyGeneSet
			geneset.upload()  # upload all PsyGeneSets to GeneWeaver

		print 'number of disorders added:', len(self.test_count)  # TESTING PURPOSES
		total_count = 0  # TESTING PURPOSES
		for title, gs_count in self.test_count.iteritems():  # TESTING PURPOSES
			total_count += gs_count  # TESTING PURPOSES
		print 'total number of genes added:', total_count  # TESTING PURPOSES

class PsyGeneSet:

	def __init__(self, batch, disease_id):
		self.test = True  # UI

		# inherited fields
		self.batch = batch
		self.cur = batch.cur
		self.connection = batch.connection
		self.publication = batch.publication
		self.pubmed_id = batch.pubmed_id

		# identifiers
		self.disease_id = disease_id
		self.disease_name = batch.disease_map[disease_id][0]
		self.psych_disorder = batch.disease_map[disease_id][1]

		# primary data processing fields
		self.genes = {}	 # {(gene_symbol, source): Gene obj,}

		# GENEWEAVER identifiers
		self.sp_id = '0'  # NOTE: geneset species is different to that of each Gene
		self.thresh_type = '1'	# EDIT: check to make sure this works
		self.thresh = '0'  # EDIT: check to make sure this works
		self.gdb_id = '18'	# gdb_name = PsyGeNET 
		self.usr_id = '15'	# PERSONAL USER NO. ( Astrid )
		self.cur_id = '1'  # uploaded as a public resource
		self.grp_id = '5'  # grp_name = PsyGeNET_Test
		self.attribution_id = '5'  # at_name = PsyGeNET
		self.description = 'GeneSet representative of a collection of Genes ' \
						   'that were linked to %s. Overall, these Genes were sourced from ' \
						   'PsyCUR, CTD, RGD, MGD, + GAD (PsyGenNET).' % self.disease_name
		self.gs_gene_id_type = 0  # EDIT: should only be '0' for those entered as Symbol... 
		self.name = None
		self.abbrev_name = None
		self.count = None
		self.gs_id = None
		self.gsv_value_list = []
		self.gsv_source_list = []
		self.file = {'file_size': None, 'file_uri': None, 'file_contents': None,
					 'file_comments': None, 'file_id': None}

		self.create_name()

		self.batch.test_count[self.name] = 0  # TESTING PURPOSES
		self.existing_refs = []  # ERROR CATCHING PURPOSES (probably keep)

	def geneweaver_setup(self):
		print 'setting up geneset...\n'
		# COUNT [file_size]
		self.count = len(self.genes)
		print "%s: num genes = %s" % (self.disease_name, self.count)

		# FILE
		self.create_file()
		print "%s: file created" % self.disease_name
		self.insert_file()
		print "%s: file inserted" % self.disease_name

		# # PUBLICATION
		self.insert_publication()  # updates self.publication['pub_id']
		print "%s: publication inserted" % self.disease_name

	def upload(self):
		# GENESET
		self.insert_geneset()	 # create geneset in GW
		print "%s: geneset inserted" % self.disease_name

		# GENESET VALUES
		self.insert_geneset_values()	# calls eGene objs to add values
		print "%s: geneset values inserted" % self.disease_name
		self.update_gsv_lists()	 # update values stored for gsv_values_list + gsv_source_list
		print "%s: gsv lists updated\n" % self.disease_name

	def add_gene(self, psy_id, symbol, desc, score, source_id):
		# check to make sure that this gene doesn't already exist in this PsyGeneSet
		if (symbol, source_id) in self.genes.keys():
			self.batch.set_errors(critical='Error: attempted to add duplicate Gene to PsyGeneSet.')
			print self.batch.get_errors()[0]  # print critical errors for user
			exit()

		# creates Gene obj
		g = Gene(self)

		# updates vals for Gene obj
		g.set_psyID(psy_id)
		g.set_symbol(symbol)
		g.set_description(desc)
		g.set_score(score)
		g.set_source(source_id)

		# adds Gene to self.genes
		self.genes[(symbol, source_id)] = g

	def create_name(self):
		# use the PsyGeNET DisorderName
		self.name = self.disease_name.strip().replace(' ', '_') # remove whitespace

		# remove any commas, + put anything after comma at the beginning
		tmp = self.name.split(',')
		if len(tmp) > 1:
			self.name = tmp[1] + tmp[0]

		# remove 1 from 'MajorAffectiveDisorder1'
		if self.name == 'MajorAffectiveDisorder1':
			self.name = 'MajorAffectiveDisorder'

		self.abbrev_name = self.name.replace('_', '')

	def create_file(self):
		""" # creates a file for GeneWeaver # EDIT
		"""
		if self.genes:
			contents = ''
			for gene in self.genes:
				curline = str(gene) + '\t' + str(self.genes[gene].score) + '\n'
				contents += curline
			self.file['file_contents'] = contents
			self.file['file_size'] = self.count
			self.file['file_comments'] = ''
			self.file['file_uri'] = 'astridmoore' + 'Psygenet-' + self.name
		else:
			self.batch.set_errors(critical='Error: cannot add file if there are no Genes in PsyGeneSet.')
			print "FAILED CREATING FILE"
			exit()

	def insert_file(self):
		""" # EDIT

			Inserts a new row into the file table. Most of the columns for the file
			table are required as arguments.

		Returns
		-------
		file_id: File ID

		"""
		query = 'INSERT INTO production.file ' \
				'(file_size, file_uri, file_contents, file_comments, ' \
				'file_created, file_changes) ' \
				'VALUES (%s, %s, %s, %s, NOW(), \'\') RETURNING file_id;'

		vals = [self.file['file_size'], self.file['file_uri'],
				self.file['file_contents'], self.file['file_comments']]

		self.cur.execute(query, vals)
		self.commit()

		self.file['file_id'] = self.cur.fetchall()[0][0]

	def insert_publication(self):
		""" # inserts publication into GeneWeaver once, skips if its done it before 
			# EDIT
		"""
		if self.publication['pub_id']:	# if publication already added to GeneWeaver, skip
			return

		query = 'INSERT INTO production.publication ' \
				'(pub_authors, pub_title, pub_abstract, pub_journal, ' \
				'pub_volume, pub_pages, pub_pubmed) ' \
				'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING pub_id;'

		vals = [self.publication['pub_authors'], self.publication['pub_title'],
				self.publication['pub_abstract'], self.publication['pub_journal'],
				self.publication['pub_volume'], self.publication['pub_pages'],
				self.publication['pub_pubmed']]

		self.cur.execute(query, vals)
		self.commit()

		pub_id = self.cur.fetchall()[0][0]
		self.publication['pub_id'] = str(pub_id)
		self.batch.publication['pub_id'] = str(pub_id)

	def insert_geneset(self):
		query = 'INSERT INTO geneset ' \
				'(file_id, usr_id, cur_id, sp_id, gs_threshold_type, ' \
				'gs_threshold, gs_created, gs_updated, gs_status, ' \
				'gs_count, gs_uri, gs_gene_id_type, gs_name, ' \
				'gs_abbreviation, gs_description, gs_attribution, ' \
				'gs_groups, pub_id) ' \
				'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), \'normal\', ' \
				'%s, \'\', %s, %s, %s, %s, %s, %s, %s) RETURNING gs_id;'
		
		vals = [self.file['file_id'], self.usr_id, self.cur_id, self.sp_id,
				self.thresh_type, self.thresh, self.count,
				self.gs_gene_id_type, self.name, self.abbrev_name,
				self.description, self.attribution_id, self.grp_id,
				self.publication['pub_id']]

		self.cur.execute(query, vals)
		self.commit()

		self.gs_id = self.cur.fetchall()[0][0]

	def insert_geneset_values(self):
		# make calls to Gene to upload itself and it's value to GW
		bar = progressbar.ProgressBar(maxval=len(self.genes)).start()  # TESTING PURPOSES

		count = 0  # TESTING PURPOSES
		for gene in self.genes:
			count += 1	# TESTING PURPOSES
			bar.update(count)  # TESTING PURPOSES
			self.genes[gene].insert_gene()
			self.genes[gene].insert_gene_info()
			self.genes[gene].insert_value()
		bar.finish()  # TESTING PURPOSES

		print 'real count: ', self.batch.test_count[self.name]  # TESTING PURPOSES

	def update_gsv_lists(self):
		# update gsv_source_list
		query = 'UPDATE extsrc.geneset_value ' \
				'SET gsv_source_list = %s ' \
				'WHERE gs_id = %s;'
		vals = [self.gsv_source_list, self.gs_id]
		self.cur.execute(query, vals)
		self.commit()

		# update gsv_value_list
		query = 'UPDATE extsrc.geneset_value ' \
				'SET gsv_value_list = %s ' \
				'WHERE gs_id = %s;'
		vals = [self.gsv_value_list, self.gs_id]
		self.cur.execute(query, vals)
		self.commit()

	def commit(self):
		if self.test == True:
			return
		else:
			self.connection.commit()
			
class Gene:

	def __init__(self, geneset):
		self.geneset = geneset
		self.batch = geneset.batch
		self.connection = geneset.batch.connection
		self.cur = geneset.batch.cur

		self.psy_id = None
		self.gene_symbol = None
		self.description = None
		self.score = None
		self.source_id = None
		self.species = None	 # list to try! (not final sp_id)
		
		self.ode_gene_id = None
		self.ode_ref_id = None
		self.sp_id = None  # not necessarily the same as parent
		self.gdb_id = None	# not necessarily the same as parent
		self.ode_pref = False  # False unless found in Gene Symbol table

		self.found_ode_gene = False
		self.already_added = False

	def set_psyID(self, psy):
		self.psy_id = psy

	def set_symbol(self, symbol):
		self.gene_symbol = symbol

	def set_description(self, desc):
		self.description = desc

	def set_score(self, val):
		self.score = val

	def set_source(self, source):
		self.source_id = source
		self.species = self.batch.source_types[source]

	def insert_gene(self):

		# if there's more than one possible species
		if len(self.species) > 1:
			for animal in self.species:
				# while ode_gene_id still not found, continue querying
				if not self.found_ode_gene:	 
					self.sp_id = str(animal)
					# search geneweaver for ode_gene_id for this species 
					self.search_geneweaver()
				else:
					break  # if found, continue
		else:
			self.sp_id = str(self.species[0])
			# search geneweaver for ode_gene_id
			self.search_geneweaver()

		if self.already_added:
			return	# don't add duplicates, just the value to the geneset

		# otherwise, add the new gene
		if not self.found_ode_gene:
			self.ode_ref_id = self.psy_id  # PsyGeNET ID
			self.gdb_id = self.geneset.gdb_id  # PsyGeNET 

			query = 'INSERT INTO extsrc.gene ' \
					'(ode_ref_id, gdb_id, sp_id, ode_pref,' \
					' ode_date) VALUES (%s, %s, %s, false, NOW()) ' \
					'RETURNING ode_gene_id;'
			vals = [self.ode_ref_id, self.gdb_id, self.sp_id]
			
			self.cur.execute(query, vals)
			self.geneset.commit()
			self.ode_gene_id = self.cur.fetchall()[0][0]

		else:
			query = 'INSERT INTO extsrc.gene ' \
					'(ode_gene_id, ode_ref_id, gdb_id, sp_id, ode_pref,' \
					' ode_date) VALUES (%s, %s, %s, %s, false, NOW());'
			vals = [self.ode_gene_id, self.ode_ref_id, self.gdb_id, self.sp_id]

			self.cur.execute(query, vals)
			self.geneset.commit()

	def insert_gene_info(self):
		if self.already_added:
			return

		query = 'INSERT INTO extsrc.gene_info ' \
				'(ode_gene_id, gi_accession, gi_symbol, gi_description,' \
				' sp_id, gi_date) ' \
				'VALUES (%s, %s, %s, %s, %s, NOW());'
		vals = [self.ode_gene_id, self.psy_id, self.gene_symbol, 
				self.description, self.sp_id]

		self.cur.execute(query, vals)
		self.geneset.commit()

	def insert_value(self):

		if self.psy_id not in self.geneset.existing_refs:
			# insert the value
			query = 'INSERT INTO extsrc.geneset_value ' \
					'(gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list, ' \
					'gsv_value_list, gsv_in_threshold, gsv_date) ' \
					'VALUES (%s, %s, %s, 0, %s, %s, true, NOW());'

			vals = [self.geneset.gs_id, self.ode_gene_id, self.score,
					[self.ode_ref_id], [float(self.score)]]
			
			self.cur.execute(query, vals)
			self.geneset.commit()

			# update PsyGeneSet so that we can update these vals later
			self.geneset.gsv_source_list.append(str(self.ode_ref_id))
			self.geneset.gsv_value_list.append(float(self.score))

			self.batch.test_count[self.geneset.name] += 1  # TESTING PURPOSES
			self.geneset.existing_refs.append(self.psy_id)

	def search_geneweaver(self):
		# check in the dedicated table for PsyGeNET
		self.check_gw_psygenet()
		# check in Gene Symbol table
		self.check_gw_symbols()

	def check_gw_psygenet(self):
		if self.found_ode_gene:
			return

		# check for existing ode_ref_id
		# goal is to get an ode_gene_id without having to create it
		query = 'SELECT ode_gene_id, ode_ref_id ' \
				'FROM extsrc.gene ' \
				'WHERE gdb_id = %s AND ' \
				'sp_id = %s AND ' \
				'ode_ref_id = %s;'

		vals = [self.geneset.gdb_id, self.sp_id, self.psy_id]
		self.cur.execute(query, vals)

		res = self.cur.fetchall()

		if len(res):  # if obtained result, only one instance in table
			self.ode_gene_id = str(res[0][0])
			self.ode_ref_id = str(self.psy_id)	# make ID specific to PsyGeNET
			self.gdb_id = self.geneset.gdb_id  # PsyGeNET gdb_id
			self.found_ode_gene = True

			# ode_gene_id, ode_ref_id pairing already exists in PsyGeNET table
			self.already_added = True  

	def check_gw_symbols(self):
		if self.found_ode_gene:
			return

		query = 'SELECT ode_gene_id, ode_ref_id, ode_pref ' \
				'FROM extsrc.gene ' \
				'WHERE gdb_id = %s AND ' \
				'sp_id = %s AND ' \
				'ode_ref_id = %s AND ' \
				'ode_pref = true;'

		vals = ['7', self.sp_id, self.gene_symbol]
		self.cur.execute(query, vals)

		res = self.cur.fetchall()

		# end querying if found nothing at all in Gene Symbol table
		if not len(res):
			return

		elif len(res) == 1:
			if res[0][2] == True:  
				self.ode_gene_id = str(res[0][0])
				self.ode_ref_id = self.gene_symbol	# Gene Symbol ID
				self.gdb_id = '7'
				self.found_ode_gene = True
				self.already_added = True
				return	# end querying if found ode_gene_id to use
			else:
				self.ode_gene_id = str(res[0][0])
				self.ode_ref_id = self.psy_id  # PsyGeNET ID
				self.gdb_id = self.geneset.gdb_id
				self.found_ode_gene = True
				return

		# check results for ode_pref = True
		for r in res:
			if r[2] == True:
				self.ode_gene_id = str(res[0][0])
				self.ode_ref_id = self.gene_symbol	# Gene Symbol ID
				self.gdb_id = '7'
				self.found_ode_gene = True
				return	# end querying if found any ode_gene_id to use

		# if found results, but all ode_pref = False
		self.ode_gene_id = str(res[0][0])
		self.ode_ref_id = self.psy_id  # PsyGeNET ID
		self.gdb_id = self.geneset.gdb_id
		self.found_ode_gene = True

def test_readFile():
	psy = PsyGeNET()
	psy.read_file(psy.ROOT_DIR)

def test_groomRaw():
	psy = PsyGeNET()
	psy.groom_raw_data()

def test_dbSetup():
	psy = PsyGeNET()
	psy.database_setup()

if __name__ == '__main__':
	# ACTIVELY WRITING / DEBUGGING METHODS
	test_dbSetup()

	# FUNCTIONING METHODS
	# test_readFile()
	# test_groomRaw()