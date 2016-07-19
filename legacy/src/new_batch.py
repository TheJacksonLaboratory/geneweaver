# file: batch.py
# date: 6/10/16
# version: 1.1

import config
import psycopg2
import requests
import json
import sys
import progressbar
import error_handler as e
import uploader as u


# allow unique user input? keep it private always?

class Batch:
	def __init__(self, input_filepath=None, usr_id=0):

		self.user_id = usr_id
		self.cur_id = '1'  # uploaded as a public resource

		# EDIT: DESIGN DECISION - for now, pretend that input file is req
		self.input_file = input_filepath
		self.file_toString = None  # concatenated version of string input

		# error handling
		self.errors = e.ErrorHandler()

		# database connection fields
		self.gene_types = {}  # {gdb_name: gdb_id,}
		self.micro_types = {}  # {pf_name: pf_id,}
		self.platform_types = {}  # {prb_ref_id: prb_id,}
		self.species_types = {}  # {sp_name: sp_id,}

		# GeneSet obj fields
		self.genesets = {}  # {gs_abbrev: UploadGeneSet,}
		self.gs_gene_id_type = ''  # gs_gene_id_type (in case label changes)
		self.pubmed = ''  # PubMed ID
		self.privacy = ''  # group (public or private)
		self.score_type = ''  # gs_threshold_type
		self.threshold = ''  # gs_threshold
		self.species = ''  # sp_id
		self.publication = {'pub_id': None, 'pub_pubmed': None, 'pub_pages': None,
		                    'pub_title': None, 'pub_journal': None, 'pub_volume': None,
		                    'pub_authors': None, 'pub_abstract': None}  # {pub_*: val,}
		self.microarray = None

		# launch connection to GeneWeaver database
		self.uploader = u.Uploader(self, usr_id=0)
		self.uploader.launch_connection()
		self.populate_dictionaries()

		self.run_batch()  # initiates upload processing

	# -------------------------SESSION DATA---------------------------------------#

	def run_batch(self):
		print "initiating upload to GeneWeaver..."
		# read in the input file
		self.read_file(self.input_file)  # creates UploadGeneSet objs

		# create a new session, depending on handling approach
		if self.microarray:
			self.handle_platform()
			self.uploader.insert_publication()
			for gs_name, gs in self.genesets.iteritems():
				# TESTING PURPOSES:
				print
				print gs_name
				print 'of length:', len(gs.geneset_values)
				print
				gs.upload()
		else:
			self.handle_symbols()
			self.uploader.insert_publication()
			for gs_name, gs in self.genesets.iteritems():
				gs.upload()

			# TEST check to make sure that the changes are kept

	def handle_platform(self):
		""" Handles microarray condition.
        """
		print 'handling platform assignment...'
		# for each geneset
		for gs_abbrev, geneset in self.genesets.iteritems():
			# look up prb_ids for each prb_ref_id
			query_probes = self.uploader.get_platformProbes(
				geneset.gs_gene_id_type,
				geneset.geneset_values.keys())
			# print '\nquery_platformProbes:\n', query_probes

			# isolate probes, refs
			probes = []  # prb_ids
			probe_headers = query_probes.keys()  # prb_ref_ids
			for ref_probe, ids_probe in query_probes.iteritems():
				probes += ids_probe

			# look up ode_gene_ids for each prb_id
			query_odes = self.uploader.get_probe2gene(probes)
			# print '\nquery_probe2gene:\n', query_odes

			prb_results = {}  # (prb_ref_id: prb_id,}
			ode_results = {}  # (prb_ref_id: ode_gene_id,}

			# first, give priority to prb_ref_ids with only one prb_id
			for probe_ref, probe_ids in query_probes.iteritems():
				prb_results[probe_ref] = None
				size_poss = len(probe_ids)

				if size_poss != 1:
					continue  # prioritize potentially tricky items first
				elif probe_ids[0] not in prb_results.values():
					# print 'appended solo prb_id'
					prb_results[probe_ref] = probe_ids[0]
					probe_headers.remove(probe_ref)

			# second, process the remainder
			for header in probe_headers:
				pids = query_probes[header]

				for pid in pids:
					if pid not in prb_results.values():
						# print 'appended add. prb_id'
						prb_results[header] = pid
						probe_headers.remove(header)
						break

			# print prb_results
			# print probe_headers

			# next, go through prb_results for ode check
			adjusted_headers = set(query_probes.keys()) - set(probe_headers)
			ode_headers = list(adjusted_headers)
			for xref in adjusted_headers:
				xprobes = query_probes[xref]
				ode_results[xref] = None

				for xprobe in xprobes:
					if xprobe in query_odes.keys():
						odes = query_odes[xprobe]
						for ode in odes:
							if ode not in ode_results.values():
								ode_results[xref] = ode
								ode_headers.remove(xref)
								break

			# print ode_results
			# print ode_headers

			# TESTING
			if len(ode_results) != len(prb_results):
				print 'somethings gone wrong at the end of handle_platforms...'
				exit()

			# next, update geneset
			adjusted_headers = list(set(adjusted_headers) - set(ode_headers))
			geneset.update_geneset_values(adjusted_headers)
			geneset.update_microInfo(prb_map=prb_results, ode_map=ode_results)

	def handle_symbols(self):
		"""Handles symbol condition.
        """
		print 'handling symbol assignment...'
		# for each geneset
		for gs_abbrev, geneset in self.genesets.iteritems():
			results = {}

			# look up ode_gene_ids for each ref_id
			query_id = self.uploader.get_ode_genes(geneset.species, geneset.geneset_values.keys())

			all_gene_ids = []
			all_results = {}
			for (all_ref, all_pref, all_gdb), all_ids in query_id.iteritems():
				all_gene_ids += all_ids
				all_results[all_ref] = all_ids
			all_gene_ids = list(set(all_gene_ids))
			all_refs = all_results.keys()

			# look up preferred ode_ref_ids for each gene_id
			query_refs = self.uploader.get_prefRef(self.species, self.gs_gene_id_type,
			                                       all_gene_ids)

			# go through query_ids and see if single values 'pass'
			poss_keys = query_id.keys()
			x_results = {}
			for (all_ref, all_pref, all_gdb), all_ids in query_id.iteritems():
				if all_ref not in results.keys():
					if all_pref and all_gdb == self.gs_gene_id_type:
						poss_keys.remove((all_ref, all_pref, all_gdb))
						all_refs.remove(all_ref)
						x_results[all_ref] = all_ids

			# go through the remaining possibilities
			next_poss = {}  # {ref_id: [poss_refs,],}
			for poss_ref in all_refs:
				poss_ids = all_results[poss_ref]
				for poss_id in poss_ids:
					if poss_id not in results.values():
						# look up in query_refs
						next_poss[poss_ref] = query_refs[poss_id]
						print '\nEDIT: remaining possibilities in handle_symbols (ask Tim)\n'
						exit()

			# go through the x_results (those found first time)
			for xref, xids in x_results.iteritems():
				for xid in xids:
					if xid not in results.values():
						results[xref] = xid
						break

			# check to make sure all values were found
			if len(results) != len(geneset.geneset_values):
				# EDIT: here is where you'd add a new gene
				err = "Error: missing ode_gene_id for input value(s), " \
				      "%s" % (set(all_results.keys()) - set(results.keys()))
				self.errors.set_errors(critical=err)

			print results

			print 'made it to the end'
			exit()
			# next, update genesets
			relevant_headers = results.keys()
			# must preserve original header list for update_geneset_values to work
			# if diff for any reason, will need to call 'set_geneset_values' instead
			geneset.update_geneset_values(relevant_headers)
		# geneset.update_symbolInfo(ode_map=)
		# need header -> ode

	def populate_dictionaries(self):
		""" Queries GeneWeaver, populating globally stored dictionaries with
            information we only need to query once, including:
            - Gene Types
            - MicroArray Types
            - Species Types
        """
		# Gene Types
		self.gene_types = self.uploader.get_geneTypes()
		# MicroArray Types
		self.micro_types = self.uploader.get_microArrayTypes()
		# Species Types
		self.species_types = self.uploader.get_speciesTypes()

	def read_file(self, fp):
		""" Reads in from a source text file, using the location stored in global
            var, 'input_file', + generates objs for data handling.
        """
		with open(fp, 'r') as file_path:
			lines = file_path.readlines()
			self.file_toString = ''.join(lines)

			# first, detect how many GeneSets we need to create here
			numGS, gs_locs = self.calc_numGeneSets(self.file_toString)

			# second, find + assign required header values to global vars
			currPos = 0
			for line in lines:
				currPos += len(line)
				if currPos < gs_locs[0]:  # only search the metadata headers
					stripped = line.strip()
					if stripped[:1] == '#' or stripped[:2] == '\n' or not stripped:
						continue
					elif stripped[:1] == '!':  # score type indicator
						score = stripped[1:].strip()
						self.assign_threshVals(score)
					elif stripped[:1] == '@':  # species type indicator
						sp = stripped[1:].strip()
						self.assign_species(sp)
					elif stripped[:1] == '%':  # geneset gene id type
						gid = stripped[1:].strip()
						self.assign_geneType(gid)
					elif stripped[:2] == 'A ':  # group type
						grp = stripped[1:].strip()
						self.assign_groupType(grp)
					elif stripped[:2] == 'P ':  # pubmed id
						pub = stripped[1:].strip()
						self.uploader.search_pubmed(pub)
				else:
					break

			# third, isolate GeneSet info + create GeneSet objs
			currGS = 1
			for x in range(numGS):
				if currGS != numGS:
					gs = self.file_toString[gs_locs[x]: gs_locs[x + 1]]
					self.create_geneset(gs.strip())
				else:
					gs = self.file_toString[gs_locs[x]:]
					self.create_geneset(gs.strip())
				currGS += 1

		print "handling file parsing + global assignments..."

	def calc_numGeneSets(self, gs_file):
		print 'calculating number of GeneSets in file...'
		# if any of these fail, we know that the file is missing key info
		try:
			bang = gs_file.split('!')
			at = gs_file.split('@')
			perc = gs_file.split('%')
			equiv = gs_file.split('=')
			colon = gs_file.split(':')
		except ValueError:
			err = 'Error: Critical GeneSet information is missing. ' \
			      'Please refer to the documentation to make sure that ' \
			      'everything is labelled correctly.'
			self.errors.set_errors(critical=err)

		# should only contain one of the following
		if len(bang) != 2 or len(at) != 2 or len(perc) != 2:
			err = 'Error: Critical GeneSet information is missing. ' \
			      'Please refer to the documentation to make sure that ' \
			      'everything is labelled correctly.'
			self.errors.set_errors(critical=err)

		# should be of equal number
		if len(colon) != len(equiv):
			err = 'Error: Incorrect GeneSet labelling. Please refer to ' \
			      'the documentation.'
			self.errors.set_errors(critical=err)

		# see which GeneSet header label comes first
		len_colon = 0
		len_equiv = 0
		order = {}  # TESTING
		first_loc = []
		for x in range(len(colon) - 1):  # last items should be equal, so skip
			len_colon += len(colon[x])
			len_equiv += len(equiv[x])
			# print len_colon, len_equiv
			if len_colon < len_equiv:
				order[x] = ':'  # TESTING
				first_loc.append(len_colon)
			else:
				order[x] = '='  # TESTING
				first_loc.append(len_equiv)
		# print order #  TESTING

		numGS = len(colon) - 1
		print 'estimated number of GeneSets in this file: %s' % numGS
		return numGS, first_loc

	def assign_threshVals(self, score):
		print 'checking + assigning score type...'
		score = score.replace(' ', '').lower()

		if 'binary' in score:
			self.score_type = '3'
		elif 'p-value' in score:
			self.score_type = '1'
			try:
				values = score.split('<')
				if len(values) == 1:  # then no value was actually given
					raise ValueError
				self.threshold = values[1]
			except ValueError:
				self.threshold = '0.05'
				err = 'Warning: P-Value threshold not specified. ' \
				      'Using "P-Value < 0.05".'
				self.errors.set_errors(noncritical=err)
		elif 'q-value' in score:
			self.score_type = '2'
			try:
				values = score.split('<')
				if len(values) == 1:  # then no value was actually given
					raise ValueError
				self.threshold = values[1]
			except ValueError:
				self.threshold = '0.05'
				err = 'Warning: Q-Value threshold not specified. ' \
				      'Using "Q-Value < 0.05".'
				self.errors.set_errors(noncritical=err)
		elif 'correlation' in score:
			self.score_type = '4'
			try:
				values = score.split('<')
				if len(values) != 3:  # then something is missing: assume default
					raise ValueError
				self.threshold = values[0] + ',' + values[2]
			except ValueError:
				self.threshold = '-0.75,0.75'
				err = 'Warning: Correlation thresholds not specified properly. ' \
				      'Using "-0.75 < Correlation < 0.75".'
				self.errors.set_errors(noncritical=err)
		elif 'effect' in score:
			self.score_type = '5'
			try:
				values = score.split('<')
				if len(values) != 3:  # then something is missing: assume default
					raise ValueError
				self.threshold = values[0] + ',' + values[2]
			except ValueError:
				self.threshold = '0,1'
				err = 'Warning: Effect size thresholds not specified properly. ' \
				      'Using "0 < Effect < 1".'
				self.errors.set_errors(noncritical=err)

	def assign_species(self, sp):
		print 'checking + assigning species type...'
		sp = sp.lower()

		if sp in self.species_types.keys():
			self.species = self.species_types[sp]
		else:
			err = 'Error: Unable to identify the input species type, %s. ' \
			      'Please refer to the documentation for a list of species types, ' \
			      'written out by their scientific name.' % sp
			self.errors.set_errors(critical=err)

	def assign_geneType(self, gid):
		print 'checking + assigning gene ID type...'
		gid = gid.lower().strip()

		if gid in self.gene_types.keys():
			self.gs_gene_id_type = self.gene_types[gid]
		# check to see if it is a microarray
		elif gid[11:] in self.micro_types.keys():
			self.gs_gene_id_type = self.micro_types[gid[11:]]
			self.microarray = gid[11:]
		else:
			err = 'Error: Unable to determine the gene type provided. ' \
			      'Please consult the documentation for a list of types.'
			self.errors.set_errors(critical=err)

	def assign_groupType(self, grp='private'):
		print 'checking + assigning group type...'
		grp = grp.lower()

		if grp == 'public':
			self.privacy = '0'
		else:
			self.privacy = '-1'

	def create_geneset(self, raw_info):
		print 'creating GeneSet obj...'
		# create GeneSet obj
		gs = GeneSet(self)

		gs_info = raw_info.split('\n')
		desc = []  # store as list, as can span multiple lines
		content_loc = 0
		for info in gs_info:
			info = info.strip()
			if info[:1] == ':':
				gs.set_abbrev(info[1:].strip())
			elif info[:1] == '=':
				gs.set_name(info[1:].strip())
			elif info[:1] == '+':
				desc.append(info[1:].strip())
			elif not info:
				# keep track of the location of the last blank line
				content_loc = gs_info.index(info)

			# add concatenated description to UploadGeneSet obj
		gs.set_description(' '.join(desc))

		# add content to UploadGeneSet obj
		gs_vals = {}
		vals = []  # in case score type is Binary, + we need to derive the max val
		for data in gs_info[content_loc + 1:]:
			try:
				gene, val = data.split('\t')
				vals.append(float(val))
				gs_vals[gene.strip()] = val.strip()
			# add the threshold val if binary
			except ValueError:
				err = "Error: Data points should be in the format 'gene " \
				      "id <tab> data value', with each data point on a " \
				      "separate line. Please check the file and make sure that you did " \
				      "not include an empty geneset with no genes."
				self.errors.set_errors(critical=err)

		# pass GeneSet values along to UploadGeneSet obj
		gs.set_genesetValues(gs_vals)

		# if the score type is Binary, still need to assign a threshold value
		if self.score_type == '3':
			self.threshold = str(max(vals))
			gs.set_threshold(self.threshold)

		# add UploadGeneSet obj to global dict
		self.genesets[gs.abbrev_name] = gs


class GeneSet:
	def __init__(self, batch):
		print "initializing GeneSet object..."

		self.batch = batch
		self.gs_gene_id_type = batch.gs_gene_id_type
		self.pubmed = batch.pubmed  # PubMed ID
		self.group = batch.privacy  # group (public or private)
		self.score_type = batch.score_type  # gs_threshold_type
		self.threshold = batch.threshold  # gs_threshold
		self.species = batch.species  # sp_id
		self.uploader = batch.uploader

		# GeneSet fields
		self.geneset_values = {}  # {gene id: gene value,} (for gsv_value_list)
		self.abbrev_name = ''  # gs_abbreviation
		self.name = ''  # gs_name
		self.description = ''  # gs_description
		self.file_id = None

		self.count = 0
		self.gs_id = None

		# platform fields
		self.prb_info = None
		self.ode_info = None

		# symbol fields
		self.header2ode = None  # {gene id (original ref): ode_gene_id, }

	def upload(self):
		print "initiating upload sequence..."
		self.file_id = self.uploader.insert_file(count=self.count, name=self.name,
		                                         gs_values=self.geneset_values)

		self.gs_id = self.uploader.insert_geneset(file_id=self.file_id, usr_id=self.batch.user_id,
		                                          cur_id=self.batch.cur_id, sp_id=self.species,
		                                          score_type=self.score_type, thresh=self.threshold,
		                                          count=self.count, gs_gene_id_type=self.gs_gene_id_type,
		                                          name=self.name, abbrev_name=self.abbrev_name,
		                                          description=self.description, group=self.group,
		                                          pub_id=self.batch.publication['pub_id'])

		self.uploader.insert_geneset_values(gs_values=self.geneset_values, thresh=self.threshold,
		                                    gs_id=self.gs_id, count=self.count, header2ode=self.header2ode)

		self.uploader.modify_gsv_lists(gsv_source_list=self.geneset_values.keys(),
		                               gsv_value_list=self.geneset_values.values(),
		                               gs_id=self.gs_id)

	# -----------------------MUTATORS--------------------------------------------#
	def set_genesetValues(self, gsv_values):
		print 'setting GeneSet value list...'
		if type(gsv_values) == dict:
			self.geneset_values = gsv_values
		else:
			err = 'Error: Expected to recieve a dictionary of GeneSet values in ' \
			      'UploadGeneset.set_genesetValues() where "{gene id: gene value, }".'
			self.batch.set_errors(critical=err)

	def set_abbrev(self, abbrev):
		print 'setting abbreviated GeneSet name...'
		self.abbrev_name = abbrev

	def set_name(self, gs_name):
		print 'setting GeneSet name...'
		self.name = gs_name

	def set_description(self, desc):
		print 'setting GeneSet description...'
		self.description = desc

	def set_threshold(self, thresh):
		print 'setting GeneSet threshold value...'
		self.threshold = str(thresh)

	def update_geneset_values(self, headers):
		print 'updating geneset values...'
		res = {}
		for header in headers:
			res[header] = self.geneset_values[header]
		self.geneset_values = res

		# update global count to reflect changes
		self.update_count()

	def update_microInfo(self, prb_map, ode_map):
		print 'updating platform info...'
		# prb_map {prb_ref_id: prb_id}
		# ode_map {prb_ref_id: ode_gene_id}

		self.prb_info = prb_map
		self.ode_info = ode_map

	def update_symbolInfo(self, ode_map):
		# ode_map expects {ref_id: ode_gene_id, }
		print 'updating gsv lists...'
		self.header2ode = ode_map

	def update_count(self):
		self.count = len(self.geneset_values)

	def geneweaver_setup(self):
		print "will identify the preliminary features of the GeneWeaver query, + populate globals..."

	def create_genes(self):
		print "will generate new UploadGene objs..."
		# if handling platforms
		if self.batch.microarray:
			print self.ode_info
			print self.prb_info
			print self.geneset_values

		# if handling symbols

		# if self.geneset_values:
		# 	for gene_id, value in self.geneset_values.iteritems():
		# 		# create UploadGene obj, adding these raw data
		# 		g = UploadGene(self)
		# 		g.set_rawID(gene_id)
		# 		g.set_rawVal(value)
		# 		g.setup()
		#
		# 		# store UploadGene obj in global dict
		# 		self.genes[gene_id] = g
		# else:
		# 	err = "Error: Unable to create UploadGene objs in UploadGeneSet, as there " \
		# 	      "are no values in 'self.geneset_values'."
		# 	self.batch.set_errors(critical=err)


def test_dictionaries():
	b = Batch()
	b.populate_dictionaries()


def test_fileParsing(number):
	test = '/Users/Asti/geneweaver/website-py/src/static/text/'
	append = ['affy-batch.txt',  # 0
	          'affy-dup.txt',  # 1
	          'agilent-batch.txt',  # 2
	          'batch-geneset-a.txt',  # 3
	          'batch-geneset-b.txt',  # 4
	          'batch-geneset-c.txt',  # 5
	          'batch-geneset-d.txt',  # 6
	          'empty-geneset.txt',  # 7
	          'symbol-batch.txt']  # 8

	test_file = test + append[number]
	b = Batch(input_filepath=test_file)


if __name__ == '__main__':
	# TESTING
	print sys.argv

	if len(sys.argv) < 2:
		print "Usage: python %s <int_range(9)>" % sys.argv[0]
		print "       where <int_range(9)> specifies an integer" \
		      "       between 0-8 [incl.]"
		exit()
	test_fileParsing(int(sys.argv[1]))

# WORKING
# test_dictionaries()
