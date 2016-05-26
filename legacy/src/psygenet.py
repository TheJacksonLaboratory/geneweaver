

class PsyT:

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

		# traverse lists in parallel
		for x in range(len(symbols)):  # for each row of raw data
			# if PsyGeneSet obj doesn't yet exist for that disorder
			if disease_ids[x] not in self.disorder_genesets.keys() and source_ids[x] not in ['ALL', 'CURATED']:
				print '#1', source_ids[x]
				geneset = PsyGeneSet(self, disease_ids[x])  # make a new PsyGeneSet obj
				# populate new geneset with this row of data
				geneset.add_gene(symbol=symbols[x], desc=descs[x], score=scores[x],
					source_id=source_ids[x], psy_id=psy_ids[x])
				# add new PsyGeneSet obj to self.disorder_genesets
				self.disorder_genesets[disease_ids[x]] = geneset

			elif source_ids[x] not in ['ALL', 'CURATED']: # otherwise, PsyGeneSet obj already exists
				print '#2', source_ids[x]
				# update PsyGeneSet obj with new info
				self.disorder_genesets[disease_ids[x]].add_gene(symbol=symbols[x], 
					desc=descs[x], score=scores[x], source_id=source_ids[x], psy_id=psy_ids[x])

class PsyGeneSet:

	def __init__(self, batch, disease_id):
		# inherited fields
		self.batch = batch
		self.cur = batch.cur
		self.connection = batch.connection

		# identifiers
		self.disease_id = disease_id
		self.disease_name = batch.disease_map[disease_id][0]
		self.psych_disorder = batch.disease_map[disease_id][1]

		# data processing fields
		self.genes = {}	 # {(gene_symbol, source): Gene obj,}

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

class Gene:

	def __init__(self, geneset):
		self.geneset = geneset
		self.batch = geneset.batch

		self.psy_id = None
		self.gene_symbol = None
		self.description = None
		self.score = None
		self.source_id = None
		self.species = None	 # list

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

def test_readFile():
	psy = PsyT()
	psy.read_file(psy.ROOT_DIR)

def test_groomRaw():
	psy = PsyT()
	psy.groom_raw_data()

if __name__ == '__main__':
	# ACTIVELY WRITING / DEBUGGING METHODS
	test_groomRaw()

	# FUNCTIONING METHODS
	# test_readFile()