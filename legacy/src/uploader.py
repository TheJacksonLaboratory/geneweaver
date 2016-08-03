# file: uploader.py
# date: 6/20/16
# version: 1.0

import config
import psycopg2
import requests
import json
# import progressbar  # TESTING


class Uploader:
	def __init__(self, parent):  # EDIT: remove usr_id from params - inherit

		# query fields
		self.connection = None
		self.cur = None

		# testing fields
		self.test = False

		# inherited
		self.parent = parent
		self.err = parent.errors  # opt.
		self.user = parent.user_id

	def launch_connection(self):
		""" Launches psql connection to GeneWeaver database.
		"""
		data = config.get('db', 'database')
		user = config.get('db', 'user')
		password = config.get('db', 'password')
		host = config.get('db', 'host')

		print host  # TESTING

		# set up connection information
		cs = 'host=\'%s\' dbname=\'%s\' user=\'%s\' password=\'%s\'' % (host, data, user, password)

		try:
			self.connection = psycopg2.connect(cs)  # connect to geneweaver database
			self.cur = self.connection.cursor()
		except SyntaxError:  # cs most likely wouldn't be a usable string if wasn't able to connect
			print "Error: Unable to connect to database."
			exit()

	def commit(self):
		""" If test, does nothing. Otherwise, commits the query.
		"""
		if self.test:
			return
		else:
			self.connection.commit()

	def get_geneTypes(self):
		""" Queries GeneWeaver for a list of gene types, populating global var
			'gene_types'. The name of the gene type is mapped against gene type ID. 
			All gene type names are converted to lowercase, for ease of practice.
		"""
		# QUERY: get a tuple of gene types by id + name
		query = 'SELECT gdb_id, gdb_name ' \
		        'FROM odestatic.genedb;'

		# run query
		self.cur.execute(query)
		# fetch results
		results = self.cur.fetchall()

		output = {}
		for tup in results:
			output[tup[1].lower()] = tup[0]

		return output

	def get_microArrayTypes(self):
		""" Queries GeneWeaver for a list of microarray platforms, populating global
			var 'micro_types'. The name of the microarray type is mapped against 
			it's respective microarray ID. All microarray types are converted to 
			lowercase, for ease of practice. 
		"""
		# QUERY: get a tuple of microarray types by id + name
		query = 'SELECT pf_id, pf_name ' \
		        'FROM odestatic.platform;'

		# run query
		self.cur.execute(query)
		# fetch results
		results = self.cur.fetchall()

		output = {}
		for tup in results:
			output[tup[1].lower()] = tup[0]

		return output

	def get_speciesTypes(self):
		""" Queries GeneWeaver for a list of species types, populating global var
			'species_types'. The name of the species is mapped against it's 
			respective species ID. All species types are converted to lowercase, 
			for ease of practice.
		"""
		# QUERY: get a list of species types by id + name
		query = 'SELECT sp_id, sp_name ' \
		        'FROM odestatic.species;'

		# run query
		self.cur.execute(query)
		# fetch results
		results = self.cur.fetchall()

		output = {}
		for tup in results:
			output[tup[1].lower()] = tup[0]

		return output

	def get_platformProbes(self, pfid, refs):
		""" Returns a mapping of prb_ids -> prb_ref_ids for the given platform
			+ probe references.
		"""
		# error handling for input types
		try:
			pfid = int(pfid)
			gene_refs = tuple(refs)
		except ValueError:
			err = "Error: Incorrect input type(s) entered into Batch.query_platformProbes. " \
			      "Paramter 'refs' should be a tuple or a list, 'pfid' should be an int."
			self.err.set_errors(critical=err)

		# set up query
		query = 'SELECT prb_id, prb_ref_id ' \
		        'FROM odestatic.probe ' \
		        'WHERE pf_id = %s ' \
		        'AND prb_ref_id IN %s;'

		# execute query
		self.cur.execute(query, [pfid, gene_refs])

		# results in a list of tuples [(prb_ref_id, prb_id),]
		res = self.cur.fetchall()

		# cast to dictionary  {prb_ref_id: [prb_id,],}
		results = {}
		for r in res:
			# if the prb_ref_id not in results, add it
			if r[1] not in results:
				results[r[1]] = [r[0]]
			# otherwise, append additional prb_id
			else:
				results[r[1]].append(r[0])

		# check to make sure all were found
		diff = set(refs) - set(results.keys())

		if not diff:
			return results
		elif len(diff) == len(refs):
			err = 'Error: unable to find any genes that match those provided in the file. ' \
			      'Please check the geneset gene id type and try again.'
			self.err.set_errors(critical=err)
		else:
			err = 'Warning: some prb_ref_ids were not ' \
			      'found, + therefore will not be included in the ' \
			      'geneset. \nNOT_FOUND=', diff
			self.err.set_errors(noncritical=err)
			return results

	def get_probe2gene(self, prbids):
		""" Returns a mapping of platform IDs against ode gene IDs, for the given set
			of platform probes.
		"""
		print 'querying probe2gene...'

		# error handling for input types
		try:
			prb_ids = tuple(prbids)
		except ValueError:
			err = "Error: Incorrect input type(s) entered into Batch.query_probe2gene. " \
			      "Paramter 'refs' should be a tuple or a list, 'pfid' should be an int."
			self.err.set_errors(critical=err)

		# set up query
		query = 'SELECT prb_id, ode_gene_id ' \
		        'FROM extsrc.probe2gene ' \
		        'WHERE prb_id IN %s;'

		# execute query
		self.cur.execute(query, [prb_ids])

		# returns a list of tuples [(prb_id, ode_gene_id),]
		res = self.cur.fetchall()

		# cast to dictionary {prb_id: [ode_gene_id,],}
		results = {}
		for r in res:
			# if prb_id not in results, add it
			if r[0] not in results.keys():
				results[r[0]] = [r[1]]
			# otherwise, append additional ode_gene_id
			else:
				results[r[0]].append(r[1])

		# EDIT: put duplicate detection here if required

		# check to make sure all were found
		diff = set(prbids) - set(results.keys())
		if not diff:
			return results
		else:
			err = 'Warning: some prb_ids were not ' \
			      'found, + therefore will not be included in the ' \
			      'geneset. \nNOT_FOUND=%s' % diff
			self.err.set_errors(noncritical=err)
			return results

	def get_ode_genes(self, sp_id, poss_refs):
		""" Queries database for possible ode_gene_ids. Returns a dictionary
			containing ode_ref_ids mapped to a nested array.
		"""
		print 'querying ode_gene_ids...'
		# set up the query
		query = 'SELECT ode_ref_id, ode_gene_id, ode_pref, gdb_id ' \
		        'FROM extsrc.gene ' \
		        'WHERE sp_id = %s ' \
		        'AND ode_ref_id IN %s;'

		# execute the query
		self.cur.execute(query, [sp_id, tuple(poss_refs)])

		# returns a list of tuples [(ode_ref_id, ode_gene_id, ode_pref, gdb_id'),]
		res = self.cur.fetchall()

		if not len(res):  # EDIT: change here if you want to allow for novel user input
			err = "Error: Unable to upload batch file as no genes were found.\n" \
			      "Check text file input before reattempting the batch file upload.\n"
			self.err.set_errors(critical=err)

		# cast result to a dictionary {(ode_ref_id, ode_pref, gdb_id): [ode_gene_id,]}
		results = {}
		xrefs = []
		for r in res:
			r = list(r)
			xrefs += [r[0]]
			key = tuple([r[0]] + r[2:])
			# if (ode_ref_id, ode_pref, gdb_id) not in results, add it
			if key not in results.keys():
				results[key] = [r[1]]
			else:
				results[key].append(r[1])
		xrefs = set(xrefs)

		# check to make sure that all refs were found
		diff = set(poss_refs) - xrefs
		if not diff:
			return results
		else:
			err = 'Warning: some ode_ref_ids were not found, + will therefore ' \
			      'not be included in the geneset. \nNOT_FOUND=%s' % diff
			self.err.set_errors(noncritical=err)
			return results

	def get_prefRef(self, sp_id, gdb_id, ode_ids):
		""" Looks up ode_gene_ids, given global query criteria.
		"""
		print 'querying preferred reference ids...'
		# error handling for input types
		ode_ids = tuple(ode_ids)

		# set up query
		query = 'SELECT ode_gene_id, ode_ref_id ' \
		        'FROM extsrc.gene ' \
		        'WHERE sp_id = %s ' \
		        'AND gdb_id = %s ' \
		        'AND ode_pref = TRUE ' \
		        'AND ode_gene_id IN %s;'

		# execute query
		self.cur.execute(query, [sp_id, gdb_id, ode_ids])

		# returns a list of tuples [(ode_gene_id, ode_ref_id),]
		res = self.cur.fetchall()

		# cast as a dictionary {ode_gene_id: [ode_ref_id,],}
		results = {}
		for (gene_id, ref_id) in res:
			if gene_id not in results.keys():
				results[gene_id] = [ref_id]
			else:
				results[gene_id].append(ref_id)

		# check to make sure that all the refs were found
		diff = set(ode_ids) - set(results.keys())
		if not diff:
			return results
		else:
			err = 'Warning: some ode_gene_ids were not found. ' \
			      '\nNOT_FOUND=%s' % diff
			self.err.set_errors(noncritical=err)
			return results

	def search_pubmed(self, pmid):

		print 'looking up PubMed ID...'
		# URL for pubmed article summary info
		url = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?'
		       'retmode=json&db=pubmed&id=%s') % str(pmid)
		# NCBI eFetch URL that only retrieves the abstract
		url_abs = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
		           '?rettype=abstract&retmode=text&db=pubmed&id=%s') % str(pmid)

		res = requests.get(url).content
		temp = json.loads(res)['result']

		self.parent.publication['pub_id'] = None
		self.parent.publication['pub_pubmed'] = str(pmid)
		self.parent.publication['pub_pages'] = temp[self.parent.publication['pub_pubmed']]['pages']
		self.parent.publication['pub_title'] = temp[self.parent.publication['pub_pubmed']]['title']
		self.parent.publication['pub_journal'] = temp[self.parent.publication['pub_pubmed']]['fulljournalname']
		self.parent.publication['pub_volume'] = temp[self.parent.publication['pub_pubmed']]['volume']

		authors = ""  # will hold a CSV list
		for auth in temp[self.parent.publication['pub_pubmed']]['authors']:
			authors += auth['name'] + ', '
		self.parent.publication['pub_authors'] = authors[:-2]

		if 'Has Abstract' in temp[self.parent.publication['pub_pubmed']]['attributes']:
			res2 = requests.get(url_abs).content.split('\n\n')[-3]
			self.parent.publication['pub_abstract'] = res2
		else:
			err = 'Warning: The PubMed info retrieved from NCBI was incomplete. No ' \
			      'abstract data will be attributed to this GeneSet.'
			self.err.set_errors(noncritical=err)

	def insert_publication(self):
		print 'handling publication insertion...'

		if self.parent.publication:
			# set up query
			query = 'INSERT INTO production.publication ' \
			        '(pub_authors, pub_title, pub_abstract, pub_journal, ' \
			        'pub_volume, pub_pages, pub_pubmed) ' \
			        'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING pub_id;'

			vals = [self.parent.publication['pub_authors'], self.parent.publication['pub_title'],
			        self.parent.publication['pub_abstract'], self.parent.publication['pub_journal'],
			        self.parent.publication['pub_volume'], self.parent.publication['pub_pages'],
			        self.parent.publication['pub_pubmed']]

			# execute query
			self.cur.execute(query, vals)
			self.commit()

			res = self.cur.fetchall()[0][0]
			self.parent.publication['pub_id'] = str(res)

	def insert_file(self, geneset):
		print "inserting file..."
		# gather contents
		contents = ''
		for gene, score in geneset.geneset_values.iteritems():
			curline = str(gene) + '\t' + str(score) + '\n'
			contents += curline

		# set up query
		query = 'INSERT INTO production.file ' \
		        '(file_size, file_uri, file_contents, file_comments, ' \
		        'file_created, file_changes) ' \
		        'VALUES (%s, %s, %s, %s, NOW(), \'\') RETURNING file_id;'

		vals = [geneset.count, geneset.name, contents, '']

		# execute query
		self.cur.execute(query, vals)
		self.commit()

		return self.cur.fetchall()[0][0]

	def insert_geneset(self, geneset):
		print 'inserting geneset...'

		# set up query
		query = 'INSERT INTO geneset ' \
		        '(file_id, usr_id, cur_id, sp_id, gs_threshold_type, ' \
		        'gs_threshold, gs_created, gs_updated, gs_status, ' \
		        'gs_count, gs_uri, gs_gene_id_type, gs_name, ' \
		        'gs_abbreviation, gs_description, gs_attribution, ' \
		        'gs_groups, pub_id) ' \
		        'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), \'normal\', ' \
		        '%s, \'\', %s, %s, %s, %s, 0, %s, %s) RETURNING gs_id;'

		vals = [geneset.file_id, geneset.batch.user_id, geneset.batch.cur_id,
		        geneset.species, geneset.score_type, geneset.threshold, geneset.count,
		        geneset.gs_gene_id_type, geneset.name, geneset.abbrev_name,
		        geneset.description, geneset.group, geneset.batch.publication['pub_id']]

		# execute query
		self.cur.execute(query, vals)
		self.commit()

		return self.cur.fetchall()[0][0]

	def insert_geneset_values(self, geneset):
		print 'inserting geneset values...'
		# set up query
		query = 'INSERT INTO extsrc.geneset_value ' \
		        '(gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list, ' \
		        'gsv_value_list, gsv_in_threshold, gsv_date) ' \
		        'VALUES (%s, %s, %s, 0, %s, %s, %s, NOW());'

		# TESTING / UI
		# bar = progressbar.ProgressBar(maxval=len(geneset.geneset_values)).start()
		# counter = 0  # TESTING

		# iterate through geneset_values
		for gene_id, value in geneset.geneset_values.iteritems():
			# find the right ode_gene_id associated w/ gene
			ode_gene = geneset.ode_info[gene_id]

			# check to see if value is within the threshold
			if float(value) <= float(geneset.threshold):
				gsv_in_thresh = True
			else:
				gsv_in_thresh = False

			# update gsv_source_list + gsv_value_list after this
			search_vals = [geneset.gs_id, ode_gene, value, [], [], gsv_in_thresh]
			self.cur.execute(query, search_vals)
			self.commit()

			# counter += 1  # TESTING
			# bar.update(counter)  # TESTING

		# bar.finish()  # TESTING

		# update the value count for geneset
		self.modify_geneset_count(geneset.gs_id, geneset.count)

	def modify_gsv_lists(self, geneset):
		print 'updating gsv lists...'
		# set up query
		query = 'UPDATE extsrc.geneset_value ' \
		        'SET (gsv_source_list, gsv_value_list, ' \
		        'gsv_date) = (%s, %s, NOW()) ' \
		        'WHERE gs_id = %s;'

		vals = [geneset.geneset_values.keys(), geneset.geneset_values.values(),
		        geneset.gs_id]

		# execute + commit query
		self.cur.execute(query, vals)
		self.commit()

	def modify_geneset_count(self, gs_id, count):
		print 'modifying geneset count...'
		# set up query
		query = 'UPDATE geneset ' \
		        'SET gs_count = %s ' \
		        'WHERE gs_id = %s'

		vals = [gs_id, count]

		# execute + commit query
		self.cur.execute(query, vals)
		self.commit()