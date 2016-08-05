
import uploader

class BatchFile:

	def __init__(self, file_path=None, file_list=None):

		# input handling
		self.file_path = file_path  # 0 [input_id]
		self.file_list = file_list  # 1 [input_id[

		# error handling
		self.errors = ErrorHandler()

		# data handling
		self.uploader = uploader.Uploader()
		self.file_toString = ''
		self.lines = []

		# interpret input types
		self.assess_inputs()

		# generate batches of genesets
		self.generate_batch()


	def assess_inputs(self):
		""" Checks what form of data we are dealing with,
			and decides what to do next.
		"""
		# interpret the input data
		if self.file_list:
			self.read_file(1)
		elif self.file_path:
			self.read_file(0)

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

	def generate_batch(self):
		""" Interprets the input data and generates Batch objs. """

		# estimate batch
		numBatch, batch_locs = self.calc_batch()
		numGS, gs_locs = self.calc_geneset()

		# if there are fewer GeneSets than Batch objs, report error
		if len(gs_locs) < len(batch_locs):
			err = 'Error: One of the batches of GeneSets does not ' \
			      'contain any GeneSets. Please edit your input file ' \
			      'and try again.'
			self.errors.set_errors(critical=err)

		start_batch = [0]  # remember that there's a zero here
		for x in range(numBatch):
			bvals = batch_locs.values()
			bmin = min([bvals[0][x], bvals[1][x], bvals[2][x]])
			start_batch.append(bmin)

		# use the start_batch list to cut up the self.file_toString
		#   into a field containing the prospective list of strings
		#   or, even more ideally, into a list of lists sampling from
		#   self.lines.

		# iterate through this list, like in Batch read_file

		# identify list region that could contain genesets
		# do a similar method to above on the two geneset items
		#   per each batch chunk

		# isolate genesets in a list of lists / dict

		# create batch objs with all of the above information
		# edit batch obj (simplify)





		# use the batch_locs to iterate through the
		#   list of lines (see batch.py)





		# find and assign metadata headers

		# isolate GeneSet info + create GeneSet obj

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


class ErrorHandler:
	def __init__(self):
		# error handling fields
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

		# USER FEEDBACK [uncomment selection]
		if crit_count:
			print "Critical error messages added [%i]\n" % crit_count
			for c in self.crit:
				print c
			exit()  # NOTE: might not be the way you want to leave this
		if noncrit_count:
			print "Noncritical error messages added [%i]\n" % noncrit_count
