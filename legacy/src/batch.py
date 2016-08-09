import sys
from uploader import Uploader
from error_tracker import ErrorTracker


class Batch:
	def __init__(self, usr_id=0, cur_id='1', file_path=None, file_list=None):

		# input handling
		self.file_path = file_path  # 0 [input_id]
		self.file_list = file_list  # 1 [input_id]
		self.user_id = usr_id
		self.cur_id = cur_id

		# error handling
		self.errors = ErrorTracker()

		# uploader handling
		self.uploader = Uploader(errors=self.errors, user_id=0)

		# data handling
		self.file_toString = ''
		self.file_len = None
		self.lines = []
		self.numBatch = None
		self.numGS = None
		self.gs_locs = {}
		self.batch_locs = {}
		self.delimit_file = []
		self.batches = {}
		self.genesets = {}

		# prepping req headers for GeneSet creation
		self.meta_info = ['gs_gene_id_type', 'microarray?', 'privacy',
		                  'score_type', 'thresh', 'species']

		# database connection fields
		self.gene_types = {}  # {gdb_name: gdb_id,}
		self.micro_types = {}  # {pf_name: pf_id,}
		self.platform_types = {}  # {prb_ref_id: prb_id,}
		self.species_types = {}  # {sp_name: sp_id,}

		# retrieve key refs from database
		self.populate_dictionaries()

		# interpret input types
		self.assess_inputs()

		# identify batches of genesets
		self.create_batches()  # populates self.genesets

		# initiate geneset upload process
		self.upload_genesets()

	def upload_genesets(self):

		for idx, sets in self.genesets.iteritems():
			# determine whether handling platforms or symbols
			if self.batches[idx]['microarray?']:
				self.genesets[idx] = self.handle_platform(sets)
				print '\n*************** %i GeneSet(s) created ****************\n' % len(sets)  # TESTING
			else:
				self.genesets[idx] = self.handle_symbol(sets)
				print '\n*************** %i GeneSet(s) created ****************\n' % len(sets)  # TESTING

			if 'publication' in self.batches[idx].keys():
				pub = self.batches[idx]['publication']
				pub_id = self.uploader.insert_publication(pub_authors=pub['pub_authors'],
				                                          pub_title=pub['pub_title'],
				                                          pub_abstract=pub['pub_abstract'],
				                                          pub_journal=pub['pub_journal'],
				                                          pub_volume=pub['pub_volume'],
				                                          pub_pages=pub['pub_pages'],
				                                          pub_pubmed=pub['pub_pubmed'])
				self.batches[idx]['publication']['pub_id'] = pub_id

			for gs_name, gs_list in sets.iteritems():
				for geneset in gs_list:
					geneset.upload()

			# call for a merge of errors (maybe use one of
			#   of the loops above?)

	def handle_platform(self, gs_dict):
		""" Handles microarray condition.
		"""
		# print 'handling platform assignment...'

		# for each list of geneset objs
		for gs_abbrev, gs_list in gs_dict.iteritems():
			for geneset in gs_list:
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

				# next, update geneset
				adjusted_headers = list(set(adjusted_headers) - set(ode_headers))
				geneset.update_geneset_values(adjusted_headers)
				geneset.update_ode_map(ode_map=ode_results)

		return gs_dict

	def handle_symbol(self, gs_dict):
		"""Handles symbol condition.
		"""
		# print 'handling symbol assignment...'
		# for each geneset
		for gs_abbrev, gs_list in gs_dict.iteritems():
			for geneset in gs_list:
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
				query_refs = self.uploader.get_prefRef(geneset.species,
				                                       geneset.gs_gene_id_type,
				                                       all_gene_ids)

				# go through query_ids and see if single values 'pass'
				poss_keys = query_id.keys()
				x_results = {}
				for (all_ref, all_pref, all_gdb), all_ids in query_id.iteritems():
					if all_ref not in results.keys():
						if all_pref and all_gdb == geneset.gs_gene_id_type:
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
							break

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

				# next, update genesets
				relevant_headers = results.keys()
				geneset.update_geneset_values(relevant_headers)
				geneset.update_ode_map(ode_map=results)

		return gs_dict

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

	def assess_inputs(self):
		""" Checks what form of data we are dealing with,
			and decides what to do next.
		"""
		# interpret the input data
		if self.file_list:
			self.read_file(1)
		elif self.file_path:
			self.read_file(0)

		# determine the layout of the file
		self.numBatch, self.batch_locs = self.calc_batch()
		self.numGS, self.gs_locs = self.calc_geneset()

	def read_file(self, input_id):

		if input_id == 1:  # file_list input
			if type(self.file_list) == list:
				self.file_toString = ''.join(self.file_list)
				self.lines = self.file_list
			else:
				err = 'Error: BatchFile expected to receive a file ' \
				      'as a list of lines.'
				self.errors.set_errors(critical=err)

		elif input_id == 0:  # file_path input
			if type(self.file_path) == str:
				with open(self.file_path, 'r') as file_path:
					self.lines = file_path.readlines()
					self.file_toString = ''.join(self.lines)
			else:
				err = 'Error: BatchFile expected to receive a file ' \
				      'path.'
				self.errors.set_errors(critical=err)

	def create_batches(self):
		""" Interprets the input data and generates Batch objs. """

		# if there are fewer GeneSets than Batch objs, report error
		if self.numGS < self.numBatch:
			err = 'Error: One of the batches of GeneSets does not ' \
			      'contain any GeneSets. Please edit your input file ' \
			      'and try again.'
			self.errors.set_errors(critical=err)

		# separate batches
		coords_batch = []
		for x in range(self.numBatch):
			bvals = self.batch_locs.values()
			bmin = min([bvals[0][x], bvals[1][x], bvals[2][x]])
			coords_batch.append(bmin)
		end = len(self.file_toString)
		coords_batch.append(end)

		# separate genesets
		coords_gs = []
		gs_vals = self.gs_locs.values()
		for z in range(self.numGS):
			gs_mins = min([gs_vals[0][z], gs_vals[1][z]])
			coords_gs.append(gs_mins)
		coords_gs.append(end)

		# make batches using the chunks provided by the bmins
		prevB = coords_batch[0]  # previous batch coord
		raw_batches = []
		for y in range(len(coords_batch)):
			o = self.file_toString[prevB:coords_batch[y]].split('\n')
			if len(o) > 5:
				raw_batches.append(o)
			prevB = coords_batch[y]

		if not raw_batches:
			err = "Error: Unable to distinguish the layout of the input file. " \
			      "Please refer to documentation for more insight on how to " \
			      "set up your file."
			self.errors.set_errors(critical=err)

		# identify option sets
		self.delimit_file = raw_batches

		# process files key variables
		self.get_meta()

		# merge the two coords (batch and gs)
		coords_all = coords_batch + coords_gs
		coords_all = sorted(coords_all)[:-1]  # (remove extra endpoint)
		prev_idx = coords_all[0]  # previous index
		currB = 0  # current batch

		for z in range(len(coords_all)):
			curr_idx = coords_all[z]
			if curr_idx != coords_all[0]:
				p = self.file_toString[prev_idx:curr_idx].split('\n')
				if len(p) > 3:
					if prev_idx not in coords_batch:
						# update the self.batches, ignoring the first iter
						self.batches[currB]['genesets'].append(p)
					if curr_idx in coords_batch:
						# update the batch index
						currB += 1
				prev_idx = curr_idx

		# using these sections, generate GeneSet objs
		self.create_genesets()

	def create_genesets(self):
		desc = []
		vals = []
		for idx, batch in self.batches.iteritems():
			self.genesets[idx] = {}
			for geneset in batch['genesets']:
				abbrev = None
				name = None
				gs_vals = {}
				for entry in geneset:
					line = entry.strip()
					if line[:1] == ':':
						abbrev = line[1:].strip()
					elif line[:1] == '=':
						name = line[1:].strip()
					elif line[:1] == '+':
						desc.append(line[1:].strip())
					elif '#' in line or len(line) == 0:  # ignore comments
						pass
					elif '\t' in line:
						raw = line.split('\t')
						if len(raw) > 2:
							tmp = []
							for res in raw:
								if res:
									tmp.append(res)
							raw = tmp

						gene = raw[0]
						val = raw[1]
						try:
							vals.append(float(val))
							gs_vals[gene.strip()] = val.strip()
						except ValueError:
							err = "Error: Data points should be in the format 'gene " \
							      "id <tab> data value', with each data point on a " \
							      "separate line. Please check the file and make sure that you did " \
							      "not include an empty geneset with no genes."
							self.errors.set_errors(critical=err)

				# format values for database
				content = dict((header, self.batches[0][header])
				               for header in self.meta_info)

				# create GeneSet + update headers
				gs = GeneSet(gs_dict=content, errors=self.errors,
				             uploader=self.uploader)
				gs.set_abbrev(abbrev)
				gs.set_name(name)
				gs.set_user(self.user_id)
				gs.set_cur(self.cur_id)

				# add concatenated description to GeneSet obj
				gs.set_description(' '.join(desc))

				# add geneset values
				gs.set_genesetValues(gs_vals)

				if gs.score_type == '3':
					gs.threshold = str(max(vals))

				# add GeneSet obj to global dict

				if gs.abbrev_name not in self.genesets[idx]:
					self.genesets[idx][gs.abbrev_name] = [gs]
				else:
					self.genesets[idx][gs.abbrev_name].append(gs)

	def get_meta(self):
		# retrieves meta data header options

		self.batches = {}
		option_idx = 0
		# isolate important batch option info
		for delimit in self.delimit_file:
			self.batches[option_idx] = {'genesets': []}
			self.batches[option_idx]['privacy'] = '-1'  # set default
			for line in delimit:
				line = line.strip()
				# if it contains a comment marker, skip it
				if '#' in line:
					continue
				# if it contains meta data headers, store
				elif line[:1] in self.batch_locs.keys():
					if line[:1] == '!':
						score = line[1:].strip()
						score_type, thresh = self.get_threshVals(score)
						self.batches[option_idx]['score_type'] = score_type
						self.batches[option_idx]['thresh'] = thresh
					elif line[:1] == '@':  # species type indicator
						sp = line[1:].strip()
						species = self.get_species(sp)
						self.batches[option_idx]['species'] = species
					elif line[:1] == '%':  # geneset gene id type
						gid = line[1:].strip()
						gs_gene_id_type, microarray = self.get_geneType(gid)
						self.batches[option_idx]['gs_gene_id_type'] = gs_gene_id_type
						self.batches[option_idx]['microarray?'] = microarray
					elif line[:2] == 'A ':  # group type
						grp = line[1:].strip()
						privacy = self.get_groupType(grp)
						self.batches[option_idx]['privacy'] = privacy
					elif line[:2] == 'P ':  # pubmed id
						pub = line[1:].strip()
						publication = self.uploader.search_pubmed(pub)
						self.batches[option_idx]['publication'] = publication
			option_idx += 1

	def calc_batch(self):
		# check meta data headers
		metaSyms = {'!': [], '@': [], '%': []}
		uni = []
		probs = []
		for m in metaSyms.iterkeys():
			locs = self.list_duplicates_of(self.file_toString, m)
			uni.append(len(locs))
			uni = list(set(uni))
			metaSyms[m] = locs

			if len(uni) == 1:
				continue
			else:
				probs.append(m)

		if len(probs):
			err = "Error: Unable to find all required Metadata " \
			      "headers. Please refer to the documentation for " \
			      "more information on how to use %s." % ', '.join(probs)
			self.errors.set_errors(critical=err)
		else:
			numBatch = uni[0]
			return numBatch, metaSyms

	def calc_geneset(self):
		# check geneset headers
		gSyms = {'=': [], ':': []}
		guni = []
		gprobs = []
		for g in gSyms.iterkeys():
			glocs = self.list_duplicates_of(self.file_toString, g)
			guni.append(len(glocs))
			guni = list(set(guni))
			gSyms[g] = glocs

			if len(guni) != 1:
				gprobs.append(g)

		if len(gprobs):
			gerr = "Error: Unable to find all required GeneSet " \
			       "headers. Please refer to the documentation for " \
			       "more information on how to use %s." % ', '.join(gprobs)
			self.errors.set_errors(critical=gerr)
		else:
			numGS = guni[0]
			return numGS, gSyms

	def list_duplicates_of(self, seq, item):
		start_at = -1
		locs = []
		while True:
			try:
				loc = seq.index(item, start_at + 1)
			except ValueError:
				break
			else:
				locs.append(loc)
				start_at = loc
		return locs

	def get_threshVals(self, score):
		# print 'checking + assigning score type...'

		score_type = None
		threshold = None
		score = score.replace(' ', '').lower()
		if 'binary' in score:
			score_type = '3'
		elif 'p-value' in score:
			score_type = '1'
			try:
				values = score.split('<')
				if len(values) == 1:  # then no value was actually given
					raise ValueError
				threshold = values[1]
			except ValueError:
				threshold = '0.05'
				err = 'Warning: P-Value threshold not specified. ' \
				      'Using "P-Value < 0.05".'
				self.errors.set_errors(noncritical=err)
		elif 'q-value' in score:
			score_type = '2'
			try:
				values = score.split('<')
				if len(values) == 1:  # then no value was actually given
					raise ValueError
				threshold = values[1]
			except ValueError:
				threshold = '0.05'
				err = 'Warning: Q-Value threshold not specified. ' \
				      'Using "Q-Value < 0.05".'
				self.errors.set_errors(noncritical=err)
		elif 'correlation' in score:
			score_type = '4'
			try:
				values = score.split('<')
				if len(values) != 3:  # then something is missing: assume default
					raise ValueError
				threshold = values[0] + ',' + values[2]
			except ValueError:
				threshold = '-0.75,0.75'
				err = 'Warning: Correlation thresholds not specified properly. ' \
				      'Using "-0.75 < Correlation < 0.75".'
				self.errors.set_errors(noncritical=err)
		elif 'effect' in score:
			score_type = '5'
			try:
				values = score.split('<')
				if len(values) != 3:  # then something is missing: assume default
					raise ValueError
				threshold = values[0] + ',' + values[2]
			except ValueError:
				threshold = '0,1'
				err = 'Warning: Effect size thresholds not specified properly. ' \
				      'Using "0 < Effect < 1".'
				self.errors.set_errors(noncritical=err)

		return score_type, threshold

	def get_species(self, sp):
		# print 'checking + assigning species type...'
		sp = sp.lower()

		if sp in self.species_types.keys():
			species = self.species_types[sp]
		else:
			err = 'Error: Unable to identify the input species type, %s. ' \
			      'Please refer to the documentation for a list of species types, ' \
			      'written out by their scientific name.' % sp
			self.errors.set_errors(critical=err)

		return species

	def get_geneType(self, gid):
		# print 'checking + assigning gene ID type...'
		gs_gene_id_type = None
		microarray = None
		gid = gid.lower().strip()

		if gid in self.gene_types.keys():
			gs_gene_id_type = self.gene_types[gid]
			microarray = False
		# check to see if it is a microarray
		elif gid[11:] in self.micro_types.keys():
			gs_gene_id_type = self.micro_types[gid[11:]]
			microarray = True
		else:
			err = 'Error: Unable to determine the gene type provided. ' \
			      'Please consult the documentation for a list of types.'
			self.errors.set_errors(critical=err)

		return gs_gene_id_type, microarray

	def get_groupType(self, grp='private'):
		# print 'checking + assigning group type...'
		privacy = None
		grp = grp.lower()

		if grp == 'public':
			privacy = '0'
		else:
			privacy = '-1'

		return privacy

	def report_errors(self):
		# all objs errors were added to global 'errors'
		crit, noncrit = self.errors.get_errors(critical=True, noncritical=True)

		# merge errors into strings
		crit = '\n'.join(crit)
		noncrit = '\n'.join(noncrit)

		return crit, noncrit

	def report_gs_names(self):
		gs_names = []
		for idx, genesets in self.genesets.iteritems():
			gs_names += genesets.keys()

		return gs_names


class GeneSet:
	def __init__(self, gs_dict, errors=None, uploader=None):
		# print "initializing GeneSet object..."
		# handle input
		self.input_dict = gs_dict

		# Batch fields
		self.gs_gene_id_type = ''
		self.publication = {}  # PubMed ID
		self.pubmed = ''
		self.group = ''  # group (public or private)
		self.score_type = ''  # gs_threshold_type
		self.threshold = ''  # gs_threshold
		self.species = ''  # sp_id

		self.user_id = ''
		self.cur_id = ''
		self.microarray = None

		if not errors:
			self.errors = ErrorTracker()
		else:
			self.errors = errors

		if not uploader:
			self.uploader = Uploader(errors=self.errors)
		else:
			self.uploader = uploader

		# GeneSet fields
		self.geneset_values = {}  # {gene id: gene value,} (for gsv_value_list)
		self.abbrev_name = ''  # gs_abbreviation
		self.name = ''  # gs_name
		self.description = ''  # gs_description
		self.file_id = None

		self.count = 0
		self.gs_id = None

		# mapping fields
		self.prb_info = None
		self.ode_info = None

		# populate batch header info
		self.handle_input()

	def upload(self):
		# print "initiating upload sequence..."

		self.file_id = self.uploader.insert_file(count=self.count,
		                                         gs_name=self.name,
		                                         gs_vals=self.geneset_values)

		self.gs_id = self.uploader.insert_geneset(file_id=self.file_id,
		                                          usr_id=self.user_id,
		                                          cur_id=self.cur_id,
		                                          species=self.species,
		                                          score_type=self.score_type,
		                                          threshold=self.threshold,
		                                          count=self.count,
		                                          gs_gene_id_type=self.gs_gene_id_type,
		                                          name=self.name,
		                                          abbrev_name=self.abbrev_name,
		                                          description=self.description,
		                                          group=self.group,
		                                          pub_id=self.publication['pub_id'])

		# iterate through geneset_values
		for gene_id, value in self.geneset_values.iteritems():
			# find the right ode_gene_id associated w/ gene
			ode_gene = self.ode_info[gene_id]

			# check to see if value is within the threshold
			if float(value) <= float(self.threshold):
				gsv_in_thresh = True
			else:
				gsv_in_thresh = False

			self.uploader.insert_geneset_values(ode_gene_id=ode_gene,
			                                    value=value,
			                                    gs_id=self.gs_id,
			                                    count=self.count,
			                                    gsv_in_thresh=gsv_in_thresh,
			                                    gsv_source_list=self.geneset_values.keys(),
			                                    gsv_value_list=self.geneset_values.values())

	def handle_input(self):
		# we know that these should always work, as checked in Batch
		try:
			self.gs_gene_id_type = self.input_dict['gs_gene_id_type']
			self.group = self.input_dict['privacy']
			self.score_type = self.input_dict['score_type']
			self.threshold = self.input_dict['thresh']
			self.species = self.input_dict['species']
			self.microarray = self.input_dict['microarray?']
		except ValueError:
			print "\nREALLY SHOULDN'T HAVE BROKEN HERE!! [GeneSet] \n"
			exit()

		if 'publication' in self.input_dict.keys():
			self.publication = self.input_dict['publication']
			self.pubmed = self.publication['pub_pubmed']

		else:
			self.publication['pub_id'] = None

	# -----------------------MUTATORS--------------------------------------------#
	def set_genesetValues(self, gsv_values):
		# print 'setting GeneSet value list...'
		if type(gsv_values) == dict:
			self.geneset_values = gsv_values
		else:
			err = 'Error: Expected to receive a dictionary of GeneSet values in ' \
			      'UploadGeneset.set_genesetValues() where "{gene id: gene value, }".'
			self.batch.set_errors(critical=err)

	def set_abbrev(self, abbrev):
		# print 'setting abbreviated GeneSet name...'
		self.abbrev_name = abbrev

	def set_name(self, gs_name):
		# print 'setting GeneSet name...'
		self.name = gs_name

	def set_description(self, desc):
		# print 'setting GeneSet description...'
		self.description = desc

	def set_threshold(self, thresh):
		# print 'setting GeneSet threshold value...'
		self.threshold = str(thresh)

	def update_geneset_values(self, headers):
		# print 'updating geneset values...'
		res = {}
		for header in headers:
			res[header] = float(self.geneset_values[header])
		self.geneset_values = res

		# update global count to reflect changes
		self.update_count()

	def update_ode_map(self, ode_map):
		# print 'updating ode mapping...'
		self.ode_info = ode_map

	def update_count(self):
		self.count = len(self.geneset_values)

	def set_user(self, usr_id):
		self.user_id = usr_id

	def set_cur(self, cur):
		self.cur_id = cur


def test_fileParsing(number):
	# test directories
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

	# add uploader + error handling separately
	test_file = test + append[number]
	b = Batch(file_path=test_file)
	b.report_gs_names()

# batches = []
# for output in bf.delimit_file:
# 	batch = B.Batch(output)
# 	batches.append(batch)

if __name__ == '__main__':
	# TESTING
	print sys.argv

	if len(sys.argv) < 2:
		print "Usage: python %s <int_range(9)>" % sys.argv[0]
		print "       where <int_range(9)> specifies an integer\n" \
		      "       between 0-8 [incl.]"
		exit()

	test_fileParsing(int(sys.argv[1]))
