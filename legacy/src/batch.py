# file: batch.py
# desc: Rewrite of the PHP batch geneset upload function.
# version: 0.2.1
# author(s): Erich Baker, Tim Reynolds, Astrid Moore

# TODO:
# 1. The regex taken from the PHP code for effect and correlation
#   scores doesn't work on all input cases. It breaks for cases such
#   as "0.75 < Correlation." For almost all cases now though, it works.

# 2. Genesets still need to be associated with a usr_id. This isn't
# 	done now because there's no point in getting usr_ids offline.
#   However, one of the cmd line args allows you to specify a usr_id.

# 3. Actually determine gsv_in_threshold insead of just setting it
#   to be true lol.

# 4. Better messages for duplicate/missing genes and pubmed errors
#   (i.e. provide the gs_name these failures are associated with).


# multisets because regular sets remove duplicates, requires python 2.7
from collections import Counter as mset
from collections import defaultdict as dd
import datetime
import json
import psycopg2
import random
import re
import urllib2 as url2
import config


# import geneweaverdb

class TheDB:
    """ Class for interfacing with the DB. Attempts to create a connection
        during object init. Only one of these objects should be instantiated,
        so assigned to a global variable (self.conn).  """

    def __init__(self):

        # Global variables
        self.conn = None  # psycopg2 connection obj
        self.cur = None  # psycopg2 cursor obj

        data = config.get('db', 'database')
        user = config.get('db', 'user')
        password = config.get('db', 'password')
        host = config.get('db', 'host')

        # set up connection information
        cs = 'host=\'%s\' dbname=\'%s\' user=\'%s\' password=\'%s\'' % (host, data, user, password)

        try:
            self.conn = psycopg2.connect(cs)  # connect to geneweaver database
            self.cur = self.conn.cursor()
        except SyntaxError:  # cs probably wouldn't be a useable string if wasn't able to connect
            print "Error: Unable to connect to database."
            exit()

    def getGeneTypes(self):
        """ Queries the DB for a list of gene types and returns the result as a dict.
            Gene type name is mapped against gene type id. All gene type names
            are converted to lowercase.

        Returns
        -------
        d: dict of gdb_name -> gdb_id

        """
        d = {}  # empty dict for return val

        # QUERY: get a list of gene types by id + name
        query = 'SELECT gdb_id, gdb_name ' \
                'FROM odestatic.genedb;'

        self.cur.execute(query, [])  # execute query
        res = self.cur.fetchall()  # gather result of query

        for tup in res:
            d[tup[1].lower()] = tup[0]  # USEAGE: {gdb_name: gbd_id,} - dict ref for gene types

        return d  # RETURNS: list of tuples [(gdb_name, gdb_id)]

    # groom / pull out any more functions that could be used for other cases [reduction]
    def getOdeGeneIdsNonPref(self, sp, syms, gtype, gs):
        """ Attempts to retrieve ode_gene_ids for ode_ref_ids by mapping
            non-preferred ode_ref_ids to the preferred ode_gene_ids (ode_pref == true).
            This can be done in a single query, but since we want to map
            nonpref_ref --> ode_gene_id --> pref_ref, it's done as two separate
            queries. Plus it allows us to return a list of ode_ref_ids that can
            be added to gsv_source_list.

        Parameters
        ----------
        sp: Species ID (int)
        syms: Reference IDs (list)
        gtype: Gene Type (int)
        gs: GeneSet information (dict)

        Returns
        -------
        output: dictionary of Reference IDs -> Gene IDs such that {ode_ref_id: ode_gene_id,}
        noncrit: list of non-criticl errors to inform the user about
        final_values: list of ode_ref_ids representative of the keys in output
        id_to_value: output dict that maps ode_gene_id(s) to associated gsv_value(s)
        output_gs: GeneSet that reflects any changes made during queries

        """
        gene_type = abs(gtype)  # gene type stripped of sign ('-' = symbol)
        gene_ids = []  # list of genes that were ode_pref=False following QUERY 1, for QUERY 2
        revDict = {}  # USAGE: {ode_gene_id: [ode_ref_id,],}  -  reverse dictionary to d, from QUERY 1
        posDict = {}  # USAGE: {ode_ref_id: [ode_gene_id,],} - results from QUERY 1
        output = {}  # USAGE: {ode_ref_id: ode_gene_id, } - final dictionary
        noncrit = []  # list of errors and warnings
        value_dict = {x[0]: x[1] for x in gs["values"]}  # USAGE: {ode_ref_id: gsv_value,} - dict of gs["values"]
        id_to_value = {}  # USAGE: {ode_gene_id: gsv_value,}  -  track the gsv_value associated with each ode_gene_id

        print "syms: %s\n" % syms

        try:
            syms = tuple(syms)
        except TypeError:
            noncrit.append("Error: Input list of ode_ref_ids was not entered as a list.\n")
            self.print_noncrit(noncrit)
            exit()

        # QUERY 1: set up db query to retrieve ode_ref_id + ode_gene_id for all genes
        #   of a specified species (sp_id), regardless of user preference (ode_pref)
        #   + are in the list of ode reference IDs of interest to the user
        try:
            query1 = 'SELECT ode_ref_id, ode_gene_id, ode_pref, gdb_id ' \
                     'FROM extsrc.gene ' \
                     'WHERE sp_id = %s ' \
                     'AND ode_ref_id IN %s;'

            self.cur.execute(query1, [sp, syms])  # execute QUERY 1
            res1 = self.cur.fetchall()  # USAGE: [(ode_ref_id, ode_gene_id),]  -  gather result of QUERY 1

            if not len(res1):
                noncrit.append("Error: Unable to upload batch file as no genes found.\n"
                               "Check text file input before attempting batch upload again.\n")
                self.print_noncrit(noncrit)
                exit()

            found1 = map(lambda m: m[0], res1)  # USAGE: [ode_ref_id,] - isolate the ref ids pulled in QUERY 1
            revList = map(lambda t: t[1], res1)  # USAGE: [ode_gene_ids,] - list of all ode_gene_ids found in QUERY 1
            revDict = {p: [] for p in revList}  # USAGE: {ode_gene_id: [ode_ref_id,],} - reverse dict lookup for QUERY 1
            posDict = {d: [] for d in found1}  # USAGE: {ode_gene_id: [ode_ref_id,],} - dict lookup for QUERY 1

            for nf in (set(syms) - set(found1)):  # map symbols that weren't found to None
                noncrit.append("Warning: Symbol '%s\' was not found.\n"
                               "Check that the text file parameters [Species ID = %i, Gene Type = %i] "
                               "match gene info for '%s\'. \n"
                               % (nf, int(sp), int(gene_type), nf))
                output[nf] = None

            for ref, gID, pref, gdb in res1:
                revDict[gID].append(ref)  # ode_ref_id added for each ode_gene_id
                posDict[ref].append(gID)  # ode_gene_id added for each ode_ref_id
                if str(pref) == 'True' and int(gdb) == gene_type:
                    output[ref] = gID  # if any ode_pref == 'True', remap ode_gene_id
                    # map gID to relative gsv_value (works bc Q1 searches based on primary ode_ref_id list)
                    id_to_value[gID] = value_dict[ref]
                elif str(pref) == 'False' or int(gdb) != gene_type:  # need to run QUERY 2 for that ode_gene_id
                    gene_ids.append(gID)  # add genes with non-pref properties to gene id list, for QUERY 2

            for key, value in revDict.iteritems():
                if len(value) > 1:
                    noncrit.append("Warning: It appears that there are multiple genes referenced %s that "
                                   "share the same gene ID [%s]." % (value, key))

            gene_ids = set(gene_ids)  # removes any duplicates... wouldn't keep both regardless
            gene_ids = tuple(gene_ids)

        except psycopg2.ProgrammingError:
            noncrit.append("Error: Unable to upload batch file as no genes found.\n"
                           "Check text file input before attempting batch upload again.\n")
            self.print_noncrit(noncrit)
            exit()

        # QUERY 2: set up db query to retrieve ode_ref_id + ode_gene_id for all genes
        #   of a specified species (sp_id), that are user preferred (ode_pref)
        #   + are in the list of ode reference IDs of interest to the user
        if gene_ids:
            query2 = 'SELECT ode_ref_id, ode_gene_id ' \
                     'FROM extsrc.gene ' \
                     'WHERE sp_id = %s ' \
                     'AND gdb_id = %s ' \
                     'AND ode_pref = TRUE ' \
                     'AND ode_gene_id IN %s;'

            self.cur.execute(query2, [sp, gene_type, gene_ids])  # execute QUERY 2
            res2 = self.cur.fetchall()  # gather result of QUERY 2

            temp = {x[1]: x[0] for x in res2}  # USEAGE: {ode_gene_id: ode_ref_id,}
            found2 = map(lambda l: l[1], res2)  # USAGE: [ode_gene_id,] - isolate gene ids that are legit (pref=True)
            notFound = set(gene_ids) - set(found2)  # items not found in QUERY 2
            success = set(found2) - notFound  # items successfully found in QUERY 2

            for item in success:  # if any found2 ode_gene_ids in gene_ids, then add to output (often a short list)
                output[temp[item]] = item
                for o in revDict[item]:
                    id_to_value[item] = value_dict[o]
                t = [temp[item]]  # put ode_gene_id of interest in a list for quick set based comparison
                newref = set(t) - (set(syms) - set(t))  # get any new references following QUERY 1

                if newref:  # if this is a new gene references that did not exist to start with
                    for key, values in posDict.iteritems():
                        if item in values and len(values) > 1:
                            noncrit.append("Warning: Gene(s) %s not found. An associated Gene '%s' "
                                           "with a shared Gene ID [%s] was found for the same parameters, "
                                           "and will be added to the GeneSet instead of %s."
                                           % (revDict[item], temp[item], item, revDict[item]))
                            break
                        break
                    break

            for n in notFound:  # if a valid ode_ref_id is still not found (also often a short list - complexity sake)
                for rev in revDict[n]:
                    if rev in syms:  # if it was one of the original ode_ref_ids
                        output[rev] = None
                        noncrit.append("Warning: Gene %s not found, even after checked associated Gene IDs."
                                       "As a result, %s has subsequently been mapped to zero," % (rev, rev))

        final_values = list(output.keys())
        not_found = set(syms) - set(final_values)
        new_values = list(set(final_values) - set(not_found))
        keys_values = map(lambda x: (x, id_to_value[output[x]]), new_values)
        updated_gs = updateGeneset(gs, vals=keys_values, gcount=len(keys_values))
        output = self.lower_headers(output)

        return output, noncrit, final_values, id_to_value, updated_gs

    @staticmethod
    def lower_headers(ref):
        """ Takes in a dictionary and sets all the keys to lowercase. Returns the result.

        Parameters
        ----------
        ref: dict

        Returns
        -------
        output: dict with lowercase keys

        """
        output = {}
        if ref:
            key_map = {x: x.lower() for x in ref.iterkeys()}  # map old keys -> lowercase keys
            output = {key_map[key]: value for key, value in ref.iteritems()}
        else:
            print "Error: No dictionary was input to lower_headers().\n "

        return output

    @staticmethod
    def print_noncrit(noncrit):
        """ Prints noncritical messages to the user regarding problems in their
            batch uploading.
        """
        print "The following message(s) were raised during user batch uploading: "
        for non in noncrit:
            print non


# FIX: make below a shorter version of above, call above when we don't find what we originally thought we wanted
# or just separate into two difference query methods [QUERY ref_id, QUERY gene_id] and call both in symbol handler
    # def getOdeGeneIds(self, sp, syms):
    #     """ [Tim] Given a list of gene symbols from the users' batch file, if the symbol doesn't
    #         exist in the DB or can't be found, it is mapped to None.  The first query
    #         finds all ode_ref_ids that are preferred (ode_pref == true). All ode_ref_ids are
    #         converted to lowercase. Not all the genes provided by a user will be preferred
    #         though (e.g. 147189_at). For these cases, we find the ode_gene_id they are mapped
    #         to, then query the DB for the preferred ode_gene_id for the species given. This
    #         way we add the preferred symbol, and the one provided by the user, to the
    #         gsv_source_list. If we still can't find it, then all hope is lost. (clarify)
    #
    #     Parameters
    #     ----------
    #     sp: Species ID (int)
    #     syms: ode reference IDs (list)
    #
    #     Returns
    #     -------
    #     d: dict of ode reference IDs -> ode gene IDs
    #
    #     """
    #     # type check syms to make sure it's a list
    #     if type(syms) == list:
    #         # if it is, then cast to a tuple
    #         syms = tuple(syms)
    #
    #     # set up query to gather ode_ref_id + ode_gene_id for genes
    #     #   of a specified species (sp_id), that are user preferred (ode_pref)
    #     #   + are in the list of ode reference IDs of interest to the user
    #     query = 'SELECT DISTINCT ode_ref_id, ode_gene_id, gdb_id ' \
    #             'FROM extsrc.gene ' \
    #             'WHERE sp_id = %s ' \
    #             'AND ode_pref = TRUE ' \
    #             'AND ode_ref_id IN %s;'
    #
    #     # execute query, using params
    #     self.cur.execute(query, [sp, syms])
    #
    #     # returns a list of tuples [(ode_ref_id, ode_gene_id)]
    #     res = self.cur.fetchall()
    #     d = {}
    #
    #     ## Ignore this wall of bullshit for now, unless you want to read
    #     ## about my failures.
    #     #
    #
    #     found = map(lambda x: x[0], res)
    #     notfound = list(set(syms) - set(found))
    #
    #     if notfound:
    #         res.extend(db.getOdeGeneIdsNonPref(sp, notfound))
    #
    #     ## We return a dict of ode_ref_id --> ode_gene_ids
    #     for tup in res:
    #         d[tup[0].lower()] = tup[1]
    #
    #     print d
    #     return d

    def getMicroarrayTypes(self):
        """ Queries the DB for a list of microarray platforms and returns the
            result as a dict. The keys are pf_names and values are pf_ids. All pf_names
            are converted to lowercase.

        Returns
        -------
        d: dict of pf_names -> pf_ids

        """
        query = 'SELECT pf_id, pf_name ' \
                'FROM odestatic.platform;'

        self.cur.execute(query, [])

        # returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = {}

        # we return a dict of pf_names --> pf_ids
        for tup in res:
            d[tup[1].lower()] = tup[0]

        return d

    def getPlatformProbes(self, pfid, refs):
        """ Returns a mapping of prb_ref_ids -> prb_ids for the given platform
            and probe references.

        Parameters
        ----------
        pfid: platform ID (int)
        refs: list of platform probes

        Returns
        -------
        d: dict of prb_ref_id(s) -> prb_id(s)

        """

        if type(refs) == list:
            refs = tuple(refs)

        query = 'SELECT prb_ref_id, prb_id ' \
                'FROM odestatic.probe ' \
                'WHERE pf_id = %s ' \
                'AND prb_ref_id IN %s;'

        self.cur.execute(query, [pfid, refs])

        # returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = dd(long)

        for tup in res:
            d[tup[0]] = tup[1]  # dict of prb_ref_id --> prb_id

        return d

    def getProbe2Gene(self, prbids):
        """ Returns a mapping of platform IDs against ode gene IDs, for the given set
            of platform probes.

        Parameters
        ----------
        prbids: list of platform probes

        Returns
        -------
        d: dict of prb_ids -> ode_gene_ids

        """

        if type(prbids) == list:
            prbids = tuple(prbids)

        # prb_id: platform prob ID
        query = 'SELECT prb_id, ode_gene_id ' \
                'FROM extsrc.probe2gene ' \
                'WHERE prb_id IN %s;'

        self.cur.execute(query, [prbids])

        # returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = dd(list)

        # we return a dict of prb_ids -> ode_gene_ids. This is a list since
        # there may be 1:many associations.
        for tup in res:
            d[tup[0]].append(tup[1])

        return d

    def getSpecies(self):
        """ Queries the DB for a list of species and returns the result as a
            dict. The keys are sp_names and values are sp_ids. All sp_names are
            converted to lowercase.

        Returns
        -------
        d: dict of sp_names -> sp_ids

        """
        d = {}  # empty dict to hold return val
        query = 'SELECT sp_id, sp_name ' \
                'FROM odestatic.species;'

        self.cur.execute(query, [])
        res = self.cur.fetchall()  # returns a list of tuples [(sp_id, sp_name)]

        for tup in res:
            d[tup[1].lower()] = tup[0]

        return d  # we return a dict of sp_names --> sp_ids

    def insertFile(self, size, uri, contents, comments):
        """ Inserts a new row into the file table. Most of the columns for the file
            table are required as arguments.

        Parameters
        ----------
        size: file size
        uri: file uri
        contents: file contents
        comments: file comments

        Returns
        -------
        r: (clarify - why is this returning anything?)

        """
        # check to see if 'RETURNING' is a legit call in SQL
        query = 'INSERT INTO production.file ' \
                '(file_size, file_uri, file_contents, file_comments, ' \
                'file_created, file_changes) ' \
                'VALUES (%s, %s, %s, %s, NOW(), \'\') RETURNING file_id;'

        vals = [size, uri, contents, comments]

        self.cur.execute('set search_path = extsrc,production,odestatic;')
        self.cur.execute(query, vals)

        # returns a list of tuples [(file_id)]
        res = self.cur.fetchall()
        #
        r = res[0][0]

        return r

    def insertPublication(self, pd):
        """ Given a dict whose keys refer to columns of the publication table,
            this function inserts a new publication into the db.
            Don't forget to commit changes after calling this function.

        Parameters
        ----------
        pd: (clarify)

        Returns
        -------
        r: (clarify - why is this returning anything?)

        """

        query = 'INSERT INTO production.publication ' \
                '(pub_authors, pub_title, pub_abstract, pub_journal, ' \
                'pub_volume, pub_pages, pub_pubmed) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING pub_id;'

        vals = [pd['pub_authors'], pd['pub_title'], pd['pub_abstract'],
                pd['pub_journal'], pd['pub_volume'], pd['pub_pages'],
                pd['pub_pubmed']]

        self.cur.execute(query, vals)

        # returns a list of tuples [(pub_id)]
        res = self.cur.fetchall()
        #
        r = res[0][0]

        return r

    def insertGenesetValue(self, gs_id, gene_id, value, name, thresh):
        """ Given GeneSet ID, Gene ID, GeneSet value... (clarify - params)
            this function inserts a new GeneSet value into the db.
            Don't forget to commit changes after calling this function.

        Parameters
        ----------
        gs_id: GeneSet ID (gs_id)
        gene_id: Gene ID (ode_gene_id)
        value: GeneSet Value (gsv_value)
        name: GeneSet Value Source List (ode_ref_id)
        thresh: GeneSet Value in Threshold (gsv_in_threshold)
        """

        query = 'INSERT INTO extsrc.geneset_value ' \
                '(gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list, ' \
                'gsv_value_list, gsv_in_threshold, gsv_date) ' \
                'VALUES (%s, %s, %s, 0, %s, %s, %s, NOW());'

        vals = [gs_id, gene_id, value, [name], [float(value)], thresh]

        self.cur.execute(query, vals)

    def insertGeneset(self, gd):
        """ Given a dict whose keys are refer to columns of the geneset table,
            this function inserts a new geneset into the db.
            Don't forget to commit changes after calling this function.

        Parameters
        ----------
        gd: (clarify)

        Returns
        -------
        r: (clarify)

        """
        query = 'INSERT INTO geneset ' \
                '(file_id, usr_id, cur_id, sp_id, gs_threshold_type, ' \
                'gs_threshold, gs_created, gs_updated, gs_status, ' \
                'gs_count, gs_uri, gs_gene_id_type, gs_name, ' \
                'gs_abbreviation, gs_description, gs_attribution, ' \
                'gs_groups, pub_id) ' \
                'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), \'normal\', ' \
                '%s, \'\', %s, %s, %s, %s, 0, %s, %s) RETURNING gs_id;'

        vals = [gd['file_id'], gd['usr_id'], gd['cur_id'], gd['sp_id'],
                gd['gs_threshold_type'], gd['gs_threshold'], gd['gs_count'],
                gd['gs_gene_id_type'], gd['gs_name'], gd['gs_abbreviation'],
                gd['gs_description'], gd['gs_groups'], gd['pub_id']]

        self.cur.execute('set search_path = extsrc,production,odestatic;')
        self.cur.execute(query, vals)

        # Returns a list of tuples [(gs_id)]
        res = self.cur.fetchall()
        r = res[0][0]

        print "insertGeneset: ", vals, "\n"

        return r

    def updateGenesetCount(self, gsid, count):
        """ Updates gs_count for a given gs_id. Required since genesets are first
            made, then geneset_values are validated and added.

        Parameters
        ----------
        gsid: GeneSet ID
        count: GeneSet count

        """
        query = 'UPDATE geneset ' \
                'SET gs_count = %s ' \
                'WHERE gs_id = %s'

        self.cur.execute(query, [count, gsid])

    def commit(self):
        """ Commits changes made to the DB. Only required if we've inserted new
            genesets, geneset_values, or publications. """
        self.conn.commit()


# DB global, should only be one instance of this class # put this in Main later, once class Batch established
db = TheDB()

# ADD LATER -----------------------------]
# class Batch:
#     """ Extracts raw text from a user-input file and, following identification
#         of gene identifiers, queries sql database using psycopg2.
#
#     """
#
#     def __init__(self, db_obj):
#
#         self.database = db_obj


def eatWhiteSpace(input_string):
    """ Removes leading + trailing whitespace from a given string.

    Parameters
    ----------
    input_string: string for whitespace removal

    Returns
    -------
    output_string: string with whitespace removed

    """
    output_string = input_string.strip()
    return output_string


def readBatchFile(fp):
    """ Reads the file at the given filepath and returns all the lines that
        comprise the file.

    Parameters
    ----------
    fp: filepath to read (string)

    Returns
    -------
    lines: list of strings containing each line of the file

    """
    with open(fp, 'r') as file_path:
        lines = file_path.readlines()

    return lines


def makeDigrams(s):
    """ Recursively creates an exhaustive list of digrams from the given string.

    Parameters
    ----------
    s: (clarify)

    Returns
    -------
    b: list of strings where each string is a digram

    """
    if len(s) <= 2:
        return [s]

    b = makeDigrams(s[1:])
    b.insert(0, s[:2])

    return b


def calcStringSimilarity(s1, s2):
    """ Calculates the percent similarity between two strings.

        Meant to be a replacement for PHP's similar_text function, which old
        GeneWeaver uses to determine the right microarray platform to use.

        [Tim] Couldn't find how similar_text was implemented (just that it used some
        algorithm in the book 'Programming Classics' by Oliver) so this function
        is fairly different but achieves the same result. This algorithm uses
        digrams and their intersections to determine percent similarity. It is
        calculated as:

        sim(s1, s2) = (2 * intersection(digrams(s1), digrams(s2)) /
                   |digrams(s1) + digrams(s2)|

    Parameters
    ----------
    s1: first input string for comparison
    s2: second input string for comparison

    Returns
    -------
    perc_sim: calculated result of the percent similarty between two strings

    """
    sd1 = makeDigrams(s1)
    sd2 = makeDigrams(s2)
    intersect = list((mset(sd1) & mset(sd2)).elements())

    perc_sim = (2 * len(intersect)) / float(len(sd1) + len(sd2))

    return perc_sim


def parseScoreType(s):
    """ Attempts to parse out the score type and any threshold value
        from a given string.

        Acceptable score types and threshold values include:
            Binary
            P-Value < 0.05
            Q-Value < 0.05
            0.40 < Correlation < 0.05
            6.0 < Effect < 22.50

        The numbers can vary and if they can't be parsed, default values
        (e.g. 0.05) are used.

        [Tim] There is an issue with the regexs in this function.
        See the TODO list at the top of the file for a description.

    Parameters
    ----------
    s: string containing score type + possibly threshold value (clarify)

    Returns
    -------
    groomed: tuple containing (gs_threshold_type, gs_threshold, errors)

    """
    stype = ''
    thresh = '0.05'
    thresh2 = '0.05'
    error = ''

    # Binary threshold is left at the default of 0.05
    if s.lower() == 'binary':
        stype = '3'
        thresh = '1'

    elif s.lower().find('p-value') != -1:
        # Try to find the threshold, this regex is from the PHP func.
        # my regex: ([0-9]?\.[0-9]+)
        m = re.search(r"([0-9.-]{2,})", s.lower())
        stype = '1'

        if m:
            thresh = m.group(1)  # parenthesized group
        else:
            error = 'No threshold specified for P-Value data. Using p < 0.05.'

    elif s.lower().find('q-value') != -1:
        m = re.search(r"([0-9.-]{2,})", s.lower())
        stype = '2'

        if m:
            thresh = m.group(1)  # parenthesized group
        else:
            error = 'No threshold specified for Q-Value data. Using q < 0.05.'

    elif s.lower().find('correlation') != -1:
        # This disgusting regex is from the PHP function
        # And it sucks. It breaks on some input, might have to change this
        # later.
        m = re.search(r"([0-9.-]{2,})[^0-9.-]*([0-9.-]{2,})", s.lower())
        stype = '4'

        if m:
            thresh = m.group(1) + ',' + m.group(2)  # parenthesized group
        else:
            thresh = '-0.75,0.75'
            error = ('No thresholds specified for Correlation data.'
                     ' Using -0.75 < value < 0.75.')

    elif s.lower().find('effect') != -1:
        # Again, PHP regex
        m = re.search(r"([0-9.-]{2,})[^0-9.-]*([0-9.-]{2,})", s.lower())
        stype = '5'

        if m:
            thresh = m.group(1) + ',' + m.group(2)  # parenthesized group
        else:
            thresh = '0,1'
            error = ('No thresholds specified for Effect data.'
                     ' Using 0 < value < 1.')

    else:
        error = 'An unknown score type (%s) was provided.' % s

    groomed = (stype, thresh, error)

    return groomed


def makeGeneset(name, abbr, desc, spec, pub, grp, ttype, thresh, gtype, vals,
                usr=0, cur_id=5):
    """ Given a bunch of arguments, this function returns a dictionary
        representation of a single geneset. Each key is a different column found
        in the geneset table. Not all columns are (or need to be) represented.

        [Tim] TODO:	Need to retrieve the user's id and attach it, right now
        it just uses a placeholder.

    Parameters
    ----------
    name: GeneSet name
    abbr: GeneSet abbreviation
    desc: GeneSet description
    spec: Species ID (later converted to an int if a string)
    pub: Publication ID
    grp: Group ID (later converted to a string if an int)
    ttype: threshold type
    thresh: GeneSet threshold (see parseScoreType for a description)
    gtype: Gene ID type
    vals: GeneSet values, tuple containing (gene, value)
    usr: User ID (defaults to user (0))
    cur_id: Curation ID (unless specified it defaults to private (5))

    Returns
    -------
    gs: dict representative of GeneSet

    """
    gs = {'gs_name': name, 'gs_abbreviation': abbr, 'gs_description': desc,
          'sp_id': int(spec), 'gs_groups': grp, 'pub_id': pub,
          'gs_threshold_type': int(ttype), 'gs_threshold': thresh,
          'gs_gene_id_type': int(gtype), 'usr_id': int(usr), 'values': vals,
          'gs_count': len(vals), 'cur_id': cur_id}

    return gs


def updateGeneset(input_gs, name=None, abbr=None, desc=None, spec=None, pub=None,
                  grp=None, ttype=None, thresh=None, gtype=None, vals=None,
                  gcount=None, usr=None, cur_id=None):
    """ Takes in an input GeneSet, along with any number of parameters, and outputs
        a GeneSet with the correct specifications.

    Parameters
    ----------
    input_gs: input GeneSet for manipulation
    name: GeneSet name (defaults to None)
    abbr: GeneSet abbreviation (defaults to None)
    desc: GeneSet description (defaults to None)
    spec: Species ID (later converted to an int if string; defaults to None)
    pub: Publication ID (defaults to None)
    grp: Group ID (later converted to a string if int; defaults to None)
    ttype: threshold type (defaults to None)
    thresh: GeneSet threshold
    gtype: Gene ID type (defaults to None)
    vals: GeneSet values, tuple containing (gene, value) (defaults to None)
    gcount: number of Genes in GeneSet (int)
    usr: User ID (defaults to user (0))
    cur_id: Curation ID (defaults to private (5))

    Returns
    -------
    output_gs: output GeneSet containing any changes

    """
    output_gs = {}  # output geneset
    keys = ['gs_name', 'gs_abbreviation', 'gs_description',
            'sp_id', 'gs_groups', 'pub_id', 'gs_threshold_type',
            'gs_threshold', 'gs_gene_id_type', 'usr_id', 'values',
            'gs_count', 'cur_id']
    changes = [name, abbr, desc, spec, grp, pub, ttype, thresh, gtype, usr, vals, gcount, cur_id]

    for x in range(len(keys)):
        if changes[x]:  # if input param is something other than 'default' None
            output_gs[keys[x]] = changes[x]  # add change to output geneset
        else:  # if there is no change
            output_gs[keys[x]] = input_gs[keys[x]]  # transfer from input geneset to output

    return output_gs


def getPubmedInfo(pmid):
    """ Retrieves Pubmed article info from the NCBI servers using the NCBI eutils.
        The result is a dictionary whose keys are the same as the publication
        table. The actual return value for this function though is a tuple. The
        first member is the dict, the second is any error message.

    Parameters
    ----------
    pmid: PubMed ID

    Returns
    -------
    (clarify)

    """
    # URL for pubmed article summary info
    url = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?'
           'retmode=json&db=pubmed&id=%s') % pmid
    # NCBI eFetch URL that only retrieves the abstract
    url_abs = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
               '?rettype=abstract&retmode=text&db=pubmed&id=%s') % pmid

    # Sometimes the NCBI servers shit the bed and return errors that kill
    # the python script, we catch these and just return blank pubmed info
    try:
        res = url2.urlopen(url).read()
        res2 = url2.urlopen(url_abs).read()

    except url2.HTTPError:
        er = ('Error! There was a problem accessing the NCBI servers. No '
              'PubMed info for the PMID you provided could be retrieved.')
        return ({}, er)

    res = json.loads(res)

    # In case of KeyErrors...
    try:
        pub = res['result']
        pub = pub[pmid]

        pinfo = {'pub_title': pub['title'], 'pub_abstract': res2,
                 'pub_journal': pub['fulljournalname'],
                 'pub_volume': pub['volume'], 'pub_pages': pub['pages'],
                 'pub_pubmed': pmid, 'pub_authors': ''}

        # Author struct {name, authtype, clustid}
        for auth in pub['authors']:
            pinfo['pub_authors'] += auth['name'] + ', '

        # Delete the last comma + space
        pinfo['pub_authors'] = pinfo['pub_authors'][:-2]

    except:
        er = ('Error! The PubMed info retrieved from NCBI was incomplete. No '
              'PubMed data will be attributed to this GeneSet.')
        return ({}, er)

    return (pinfo, '')


# groom
def parseBatchFile(lns, usr=0, cur=5):
    """ Parses the batch file according to the format listed on:
        http://geneweaver.org/index.php?action=manage&cmd=batchgeneset

    Parameters
    ----------
    lns: list of strings, one per line of the batch file
    usr: User ID, to associate with the parsed GeneSets
    cur: Curation ID

    Returns
    -------
    triplet: tuple containing (list of GeneSets, list of warnings, list of errors)

    """
    genesets = []
    gsvals = []  # geneset_values, here as a list of tuples (sym, pval)
    abbr = ''  # geneset abbreviation
    name = ''  # geneset name
    desc = ''  # geneset description
    gene = ''  # gene type (gs_gene_id_type)
    pub = None  # pubmed ID
    group = 'private'  # group (public or private)
    stype = ''  # score type (gs_threshold_type)
    thresh = '0.05'  # threshold value for scores
    spec = ''  # species name
    cerr = ''  # critical errors discovered during parsing
    ncerr = []  # non-critical errors discovered during parsing
    errors = []  # critical errors discovered during parsing
    warns = []  # non-critical errors discovered during parsing

    # for ln in lns:
    for i in range(len(lns)):
        lns[i] = lns[i].strip()

        # :, =, + are required for all datasets
        #
        # Lines beginning with ':' are geneset abbreviations (REQUIRED)
        if lns[i][:1] == ':':
            # This checks to see if we've already read in some geneset_values
            # If we have, that means we can save the geneset, clear out any
            # REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                # Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            abbr = eatWhiteSpace(lns[i][1:])

        # Lines beginning with '=' are geneset names (REQUIRED)
        elif lns[i][:1] == '=':
            # This checks to see if we've already read in some geneset_values
            # If we have, that means we can save the geneset, clear out any
            # REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                # Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            name = eatWhiteSpace(lns[i][1:])

        # Lines beginning with '+' are geneset descriptions (REQUIRED)
        elif lns[i][:1] == '+':
            # This checks to see if we've already read in some geneset_values
            # If we have, that means we can save the geneset, clear out any
            # REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                # Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            desc += eatWhiteSpace(lns[i][1:])
            desc += ' '

        # !, @, %, are required but can be omitted from later sections if
        # they don't differ from the first.
        #
        # Lines beginning with '!' are score types (REQUIRED)
        elif lns[i][:1] == '!':
            score = eatWhiteSpace(lns[i][1:])
            score = parseScoreType(score)

            # Indicates a critical error has occured (no score type w/ an
            # error message)
            if not score[0] and score[2]:
                errors.append(score[2])

            else:
                stype = score[0]
                thresh = score[1]

            # Any warnings
            if score[0] and score[2]:
                warns.append(score[2])

        # Lines beginning with '@' are species types (REQUIRED)
        elif lns[i][:1] == '@':
            spec = eatWhiteSpace(lns[i][1:])
            specs = db.getSpecies()

            if spec.lower() not in specs.keys():
                err = 'LINE %s: %s is an invalid species' % (i + 1, spec)
                errors.append(err)

            else:
                # spec is now an integer (sp_id)
                spec = specs[spec.lower()]

        # Lines beginning with '%' are gene ID types (REQUIRED)
        elif lns[i][:1] == '%':
            gene = eatWhiteSpace(lns[i][1:])

            # In the PHP source, it looks like the gene type is checked
            # to see if it's a microarray first, if it is then the pf_id is
            # used, otherwise gdb_id is used. Doesn't make much sense because
            # some pf_ids overlap with gdb_ids. On second glance the PHP code
            # for gene id types makes no fucking sense but whatever.
            if gene.lower().find('microarray') != -1:
                plats = db.getMicroarrayTypes()
                origplat = gene
                gene = gene[len('microarray '):]  # delete 'microarray ' text

                # Determine the closest microarry platform match. The PHP
                # function calculated % string similarity between the user
                # supplied platform and the list of plats in the db, choosing
                # the one with the best match
                best = 0.70
                for plat, pid in plats.items():
                    sim = calcStringSimilarity(plat.lower(), origplat.lower())

                    if sim > best:
                        best = sim
                        gene = plat

                # Convert to the ID, gene will now be an integer
                gene = plats.get(gene, 'unknown')

                if type(gene) != int:
                    err = 'LINE %s: %s is an invalid platform' % \
                          (i + 1, origplat)
                    errors.append(err)

            # Otherwise the user specified one of the gene types, not a
            # microarray platform
            # :IMPORTANT: Expression platforms have positive (+)
            # gs_gene_id_types while all other types (e.g. symbols) should
            # have negative (-) integer ID types.
            else:
                types = db.getGeneTypes()

                if gene.lower() not in types.keys():
                    err = 'LINE %s: %s is an invalid gene type' % (i + 1, gene)
                    errors.append(err)

                else:
                    # gene is now an integer (gdb_id)
                    gene = types[gene.lower()]
                    # Negate, see comment tagged important above
                    gene = -gene

        # Lines beginning with 'P ' are PubMed IDs (OPTIONAL)
        elif (lns[i][:2].lower() == 'p ') and (len(lns[i].split('\t')) == 1):
            pub = eatWhiteSpace(lns[i][1:])

        # Lines beginning with 'A' are groups, default is private (OPTIONAL)
        elif lns[i][:2].lower() == 'a ' and (len(lns[i].split('\t')) == 1):
            group = eatWhiteSpace(lns[i][1:])
            # If the user gives something other than private/public,
            # automatically make it private
            if group.lower() != 'private' and group.lower() != 'public':
                group = '-1'

            elif group.lower() == 'public':
                group = '0'

            else:  # private
                group = '-1'

        # If the lines are tab separated, we assume it's the gene data that
        # will become apart of the geneset_values
        elif len(lns[i].split('\t')) == 2:
            print lns[i].split('\t'), "\n"

            # First we check to see if all the required data was specified
            if ((not abbr) or (not name) or (not desc) or (not stype) or
                    (not spec) or (not gene)):
                err = 'One or more of the required fields are missing.'
                # Otherwise this string will get appended a bajillion times
                if err not in errors:
                    errors.append(err)

            else:
                lns[i] = lns[i].split()

                # I don't think this code can ever be reached...
                if len(lns[i]) < 2:
                    err = 'LINE %s: Skipping invalid gene, value formatting' \
                          % (i + 1)
                    warns.append(err)

                else:
                    gsvals.append((lns[i][0], lns[i][1]))

        # Lines beginning with '#' are comments
        elif lns[i][:1] == '#':
            continue

        # Skip blank lines
        elif lns[i][:1] == '':
            continue

        # Who knows what the fuck this line is, just skip it
        else:
            err = 'LINE %s: Skipping unknown identifiers' % (i + 1)
            warns.append(err)

    # awwww shit, we're finally finished! Check for critical errors and
    # if there were none, make the final geneset and return
    if errors:
        triplet = ([], warns, errors)
        return triplet

    else:
        gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                         thresh, gene, gsvals, usr, cur)
        genesets.append(gs)

        triplet = (genesets, warns, errors)
        return triplet


def makeRandomFilename():
    """ Generates a random filename for the file_uri column in the file table. The
        PHP version of this function (getRandomFilename) combines the user's
        email, the string '_ODE_', the current date, and a random number. Since
        this script is offline right now, I'm just using 'GW_' + date + '_' + a
        random six letter alphanumeric string. Looking at the file_uri contents
        currently in the db though, there seems to be a ton of variation in the
        naming schemes.

    Returns
    -------
    (clarify)

    """
    rstr = ''
    now = datetime.datetime.now()

    for i in range(6):
        rstr += random.choice('abcdefghijklmnopqrstuvwxyz1234567890')

    return ('GW_' + str(now.year) + '-' + str(now.month) + '-' +
            str(now.day) + '_' + rstr)


def handle_symbols(gs, symbols):
    """ Handles the condition during batch uploading where the data type of
        gene information input was a symbol (not platform). Uploads geneset values.
        Returns the total number of GeneSets with recently inserted gsv_values,
        a list of any errors raised, and updated GeneSet.

    Parameters
    ----------
    gs: dict representing GeneSet info
    symbols: gs['values'] - input ode_gene_ids from text file

    Returns
    -------
    total: number Geneset gsv_values inserted (int)
    noncrit: list of errors (strings) raised when calling getOdeGeneIdsNonPref
    output_gs: GeneSet info updated with any changes

    """
    total = 0  # number of values added to database
    sym2ode, noncrit, final_refs, id_to_value, output_gs = db.getOdeGeneIdsNonPref(gs['sp_id'], symbols,
                                                                                   gs['gs_gene_id_type'], gs)
    if not noncrit:
        noncrit = []

    if output_gs['pub_id']:  # if a PMID was provided, we get the info from NCBI
        pub = getPubmedInfo(output_gs['pub_id'])
        output_gs['pub_id'] = pub[0]

        if pub[1]:  # non-crit pubmed retrieval errors
            noncrit.append(pub[1])

        if output_gs['pub_id']:  # new row in the publication table
            output_gs['pub_id'] = db.insertPublication(output_gs['pub_id'])
        else:
            output_gs['pub_id'] = None  # empty pub
    else:
        output_gs['pub_id'] = None  # empty pub

    output_gs['file_id'] = buFile(output_gs['values'])  # insert the data into the file table
    output_gs['gs_id'] = db.insertGeneset(output_gs)  # insert new genesets

    for ref, val in output_gs['values']:
        db.insertGenesetValue(output_gs['gs_id'], sym2ode[ref.lower()], val, ref, 'true')
        total += 1

    return total, noncrit, output_gs


# still need to work on handle_platform and getPlatformProbes [like you did with symbols]
def handle_platform(gs, symbols):
    """ Handles the condition during batch uploading where the data type of
        gene information input was a not a symbol (platform). Uploads geneset values.
        Returns the total number of GeneSets with recently inserted gsv_values
        and a list of any errors raised.

    Parameters
    ----------
    gs: dict representing GeneSet info
    symbols: gs['values'] - input ode_gene_ids from text file

    Returns
    -------
    total: number GeneSet gsv_values inserted (int)
    noncrit: list of errors (strings) raised
    gs: updated GeneSet info

    """
    total = 0  # number of values added to database
    noncrit = []
    sym2probe = db.getPlatformProbes(gs['gs_gene_id_type'], symbols)  # USEAGE: {prb_ref_id: prb_id,}
    prbids = map(lambda l: sym2probe[l], symbols)  # generate a list of prb_ids
    prbids = list(set(prbids))  # get rid of any duplicates
    prb2odes = db.getProbe2Gene(prbids)  # USAGE: {prb_ids: ode_gene_ids,}
    dups = dd(str)  # duplicate detection

    # add below to getPlatformProbes
    if gs['pub_id']:  # if a PMID was provided, we get the info from NCBI
        pub = getPubmedInfo(gs['pub_id'])
        gs['pub_id'] = pub[0]

        if pub[1]:  # non-crit pubmed retrieval errors
            noncrit.append(pub[1])

        if gs['pub_id']:  # new row in the publication table
            gs['pub_id'] = db.insertPublication(gs['pub_id'])
        else:
            gs['pub_id'] = None  # empty pub
    else:
        gs['pub_id'] = None  # empty pub

    gs['file_id'] = buFile(gs['values'])  # insert the data into the file table
    gs['gs_id'] = db.insertGeneset(gs)  # insert new genesets

    for tup in gs['values']:
        sym = tup[0]
        print "sym (buGenesetValues): %s \n" % sym
        value = tup[1]
        print "value (buGenesetValues): %s \n" % value
        prbid = sym2probe[sym]
        odes = prb2odes[prbid]

        if not prbid or not odes:
            err = ("Error! There doesn't seem to be any gene/locus data for "
                   "%s in the database." % sym)
            noncrit.append(err)
            continue

        for ode in odes:
            if not dups[ode]:  # check for duplicate ode_gene_ids
                dups[ode] = tup[0]
            else:  # otherwise query
                err = ('Error! Seems that %s is a duplicate of %s. %s was not '
                       'added to the geneset.' %
                       (sym, dups[ode], sym))
                noncrit.append(err)
                continue

            db.insertGenesetValue(gs['gs_id'], ode, value, sym,
                                  'true')
            total += 1
        continue

    return total, noncrit, gs


def buFile(genes):
    """ Parses geneset content into the proper format and inserts it into the file
        table. The proper format is gene\tvalue\n .

    Parameters
    ----------
    genes: (clarify)

    Returns
    -------
    (clarify)

    """
    conts = ''
    # Geneset values should be a list of tuples (symbol, pval)
    for tup in genes:
        conts += (tup[0] + '\t' + tup[1] + '\n')

    return db.insertFile(len(conts), makeRandomFilename(), conts, '')


def buGenesetValues(gs):
    """ Batch upload geneset values.

    Parameters
    ----------
    gs: dict representing GeneSet info

    Returns
    -------
    total: number Geneset gsv_values inserted (int)
    noncrit: list of errors (strings) raised when adding GeneSet
    gs: if expression platform (gs); if symbols (updated_gs)

    """
    values = gs['values']  # USEAGE: [(symbol, gsv_value),] - should be a list of tuples
    symbols = map(lambda x: x[0], values)  # USAGE: [symbol,] - isolate a list of reference values for querying

    if gs['gs_gene_id_type'] < 0:  # negative numbers indicate normal gene types (symbols)
        print "SYMBOL HANDLING\n"
        total, noncrit, updated_gs = handle_symbols(gs, symbols)
    else:  # positive numbers indicate expression platforms
        print "PLATFORM HANDLING\n"
        total, noncrit, updated_gs = handle_platform(gs, symbols)

    return total, noncrit, updated_gs


def buGenesets(fp, usr_id=0, cur_id=5):
    """ Batch uploads genesets. Requires the filepath to the batch upload file.
        Takes two additional (optional) parameters, a usr_id and cur_id, which
        are provided as command line arguments. This allows the person running
        the script to change usr_ids and cur_ids, which are currently set to 0
        and 5 (private) respectively, for this "offline" version of the script.

    Parameters
    ----------
    fp: (clarify)
    usr_id: (clarify)
    cur_id: (clarify)

    Returns
    -------
    (clarify)

    """
    noncrits = []  # non-critical errors we will inform the user about
    added = []  # list of gs_ids successfully added to the db
    genesets = []

    # returns (genesets, non-critical errors, critical errors)
    b = parseBatchFile(readBatchFile(fp), usr_id, cur_id)

    if b[2]:  # if a critical error has occurred
        print b[2]
        print ''
        exit()
    else:
        genesets = b[0]
        noncrits = b[1]

    for gs in genesets:
        total, gsverr, output_gs = buGenesetValues(gs)

        if gsverr:  # update gs_count if some geneset_values were found to be invalid
            db.updateGenesetCount(output_gs['gs_id'], total)

        added.append(output_gs['gs_id'])

    db.commit()

    return added, noncrits

# ----------------------------TESTING FUNCTIONS---------------------------- #


def batch_file_test():
    """ Tests the capabilities of batch.py to parse a user-input batch
    GeneSet file, add GeneSets, and batch upload. Prints errors
    identified as 'non-critical' to the command line.

    [previously found under __main__; isolated for ease of testing]
    """
    from optparse import OptionParser
    from sys import argv

    # cmd line prompt for batch test
    usage = 'usage: %s [options] <batch_file>' % argv[0]
    parse = OptionParser(usage=usage)

    parse.add_option('-u', action='store', type='string', dest='usr_id',
                     help='Specify a usr_id for newly added GeneSets')
    parse.add_option('-c', action='store', type='string', dest='cur_id',
                     help='Specify a cur_id for newly added GeneSets')

    (opts, args) = parse.parse_args(argv)

    if len(args) < 2:
        print '[!] You need to provide a batch GeneSet file.'
        parse.print_help()
        print ''
        exit()

    if not opts.usr_id:
        opts.usr_id = 0
    if not opts.cur_id:
        opts.cur_id = 5

    # where all the magic happens
    stuff = buGenesets(args[1], opts.usr_id, opts.cur_id)

    print '[+] The following GeneSets were added:'
    print ', '.join(map(str, stuff[0]))
    print ''

    if stuff[1]:
        print '[!] There were some non-critical errors with the batch file:'
        for er in stuff[1]:
            print er
        print ''


def getOdeGeneIdsNonPrefTest():
    """ Tests the capabilities of function: getOdeGeneIdsNonPrefTest()"""
    # database already randomly defined above
    # getOdeGeneIdsNonPref(species id, list of ode ref ids)

    from optparse import OptionParser
    from sys import argv

    # cmd line prompt for batch test
    usage = 'usage: %s [options] <batch_file>' % argv[0]
    parse = OptionParser(usage=usage)

    parse.add_option('-u', action='store', type='string', dest='usr_id',
                     help='Specify a usr_id for newly added GeneSets')
    parse.add_option('-c', action='store', type='string', dest='cur_id',
                     help='Specify a cur_id for newly added GeneSets')

    (opts, args) = parse.parse_args(argv)

    genesets = {}  # genesets we are working with

    # returns (genesets, non-critical errors, critical errors)
    b = parseBatchFile(readBatchFile(args[1]), 0, 0)

    # A critical error has occurred
    if b[2]:
        print b[2]
        print ''
        exit()
    else:
        genesets = b[0]

    for geneset in genesets:
        symbols = map(lambda x: x[0], geneset['values'])
        db.getOdeGeneIdsNonPref(geneset["sp_id"], symbols, geneset["gs_gene_id_type"], geneset)
        break

if __name__ == '__main__':
    print '\n TEST: batch file upload test \n'
    batch_file_test()

    # print '\n TEST: getOdeGeneIdsNonPref() \n'
    # getOdeGeneIdsNonPrefTest()
