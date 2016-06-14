# file: batch.py
# date: 6/10/16
# version: 1.0

class Batch:

	def __init__(self, input_file = None):
		# figure out optimum input type

		# DESIGN DECISION - for now, pretend that input file is req
		self.raw_file = input_file

		# error handling
		self.crit = []
		self.noncrit = []

		# database connection fields
		self.connection = None
		self.cur = None
		# launch connection to GeneWeaver database
		self.launch_connection()

	def launch_connection(self):
		""" 
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

    def read_file(self, fp):
    	""" Reads in from a source text file and outputs organized data	 # EDIT

		# separate each column into lists (make sure the same length before proceeding)

		Parameters
		----------
		fp: filepath to read (string)
		"""
		print "will handle file parsing someday..."

	def groom_raw_data(self):
		print "will assign raw data to objects someday..."

	def database_setup(self):
		print "will upload to GeneWeaver someday..."

class UploadGeneSet:

	def __init__(self, batch, prelim_info):
		print "will initialize GeneSet object someday, using preliminary info from the input file..."

	def geneweaver_setup(self):
		print "will identify the preliminary features of the GeneWeaver query, + populate globals..."

	def upload(self):
		print "will initiate data query..."

	def add_gene(self):
		print "will generate new UploadGene obj..."

	def create_file(self):
		print "will create user's UploadGeneSet..."

	def create_publicaton(self):
		print "will generate new publication, if not already in GeneWeaver... "
		# EDIT: may have absolutely no functionality at all - refer to input file layout

	def commit(self):
		print "will determine whether or not to actually make changes, or to just" \
			  " leave it in a 'test mode' state..."

class UploadGene:

	def __init__(self, geneset):
		print "will initialize Gene obj someday, using information inherited from GeneSet..."

	#-----------------mutators go here-----------------------#

	def insert_gene(self):
		print 'will insert user-specified gene into GeneSet someday...'

	def insert_gene_info(self):
		print 'will insert gene info, if gene is not already in GeneWeaver...'

	def insert_value(self):
		print 'will insert Gene value into GeneWeaver, if all information is provided...'

	def search_geneweaver(self):
		print "queries GeneWeaver for a series of possible cases, depending on what's available..."

	# -----------------series of cross-checking functions go here-----------------#

# class UploadSNP - only if relevant, if tables are up to speed
class UploadGene