
__author__ = 'baker'
__author__ = 'reynolds'

# !/usr/bin/python

#### file: batch.py
#### desc: Rewrite of the PHP batch geneset upload function.
#### vers: 0.2.1
#### auth: TR
##
#### TODO:  1. The regex taken from the PHP code for effect and correlation
####        scores doesn't work on all input cases. It breaks for cases such
####        as "0.75 < Correlation." For almost all cases now though, it works.
##
####        2. Genesets still need to be associated with a usr_id. This isn't
####        done now because there's no point in getting usr_ids offline.
####        However, one of the cmd line args allows you to specify a usr_id.
##
####        3. Actually determine gsv_in_threshold insead of just setting it
####        to be true lol.
##
####        4. Better messages for duplicate/missing genes and pubmed errors
####        (i.e. provide the gs_name these failures are associated with).
##

## multisets because regular sets remove duplicates, requires python 2.7
from collections import Counter as mset
from collections import defaultdict as dd
import datetime
import json
import psycopg2
import random
import re
import urllib2 as url2
import config
import geneweaverdb

#### TheDB
##
#### Class for interfacing with the DB. Attempts to create a connection during
#### object initialization. Only one of these objects should be instantiated.
##
class TheDB():
    def __init__(self, db='geneweaver', user='odeadmin', password='odeadmin'):
        #cs = ("host='crick' dbname='%s' user='%s' password='%s'"
        #      % (db, user, password))

        db = config.get('db', 'database')
        user = config.get('db', 'user')
        password = config.get('db', 'password')
        host = config.get('db', 'host')
        port = config.getInt('db', 'port')

        cs = "host='%s' dbname='%s' user='%s' password='%s' port='%s'" % (host, db, user, password, port)

        try:
            self.conn = psycopg2.connect(cs)
        except:  
            print '[!] Oh noes, failed to connect to the db.'
            print ''
            exit()

        self.cur = self.conn.cursor()

    #### getGeneTypes
    ##
    #### Queries the DB for a list of gene types and returns the result
    #### as a dict. The keys are gdb_names and values gdb_ids. All gdb_names
    #### are converted to lowercase.
    ##
    def getGeneTypes(self):
        query = 'SELECT gdb_id, gdb_name FROM odestatic.genedb;'

        self.cur.execute(query, [])

        ## Returns a list of tuples [(gdb_id, gdb_name)]
        res = self.cur.fetchall()
        d = {}

        ## We return a dict of gdb_names --> gdb_ids
        for tup in res:
            d[tup[1].lower()] = tup[0]

        return d

    #### getOdeGeneIdsNonPref
    ##
    #### Attempts to retrieve find ode_gene_ids for ode_ref_ids by mapping
    #### non-preferred ode_ref_ids to the preferred ones (ode_pref == true).
    #### This can be done in a single query, but since we want to map
    #### nonpref_ref --> ode_gene_id --> pref_ref, it's done as two separate
    #### queries. Plus it allows us to return a list of ode_ref_ids that can
    #### be added to gsv_source_list.
    ##
    #### update, nevermind fuck all that. I'm just gonna map non-preferred
    #### ode_ref_ids to ode_gene_ids and make things easy. Choosing the quick
    #### way over the not-even-sure-if-correct way for now. If gsv_value_list
    #### is really important I can just write a separate script to update
    #### those values or code that functionality here later on.
    ##
    def getOdeGeneIdsNonPref(self, sp, syms):
        if type(syms) == list:
            syms = tuple(syms)

        # query = ('SELECT ode_ref_id, ode_gene_id FROM extsrc.gene WHERE '
        #        'sp_id = %s AND ode_ref_id IN %s;')
        # query2 = ('SELECT ode_ref_id, ode_gene_id FROM extsrc.gene WHERE '
        #        'sp_id = %s AND ode_pref = true AND ode_gene_id IN %s;')
        query = ('SELECT ode_ref_id, ode_gene_id FROM extsrc.gene WHERE '
                 'sp_id = %s AND ode_ref_id IN %s;')

        self.cur.execute(query, [sp, syms])

        ## Returns a list of tuples [(ode_ref_id, ode_gene_id)]
        res = self.cur.fetchall()
        d = {}

        found = map(lambda x: x[0], res)

        ## Map symbols that weren't found to None
        for nf in (set(syms) - set(found)):
            res.append((nf, None))

        return res

    ## This can be uncommented later if I want/need to fix this
    ## functionality and attempt to do what I was going to do before--map
    ## non-pref ode_ref_ids --> ode_gene_ids --> pref ode_ref_ids and add
    ## both refs to gsv_source_list.
    #
    ## First dict of ode_ref_id --> ode_gene_ids
    ## First dict of ode_gene_id --> ode_ref_id
    # for tup in res:
    #   #d0[tup[0].lower()] = tup[1]
    #   d[tup[1]] = tup[0]

    ### Now the second query, to map ode_gene_ids to the preferred ode_refs
    ##self.cur.execute(query2, [sp, d0.values()])
    # self.cur.execute(query2, [sp, d.keys()])

    # res = self.cur.fetchall()
    # fin = []

    ### Appends triplets (user given symbol, ode_gene_id, pref. ode_ref_id)
    # for tup in res:
    #   fin.append((d[tup[1]], tup[1], tup[0]))

    ### Any user provided ode_ref_ids we didn't find are mapped to None
    # for nf in (set(syms) - set(map(lambda x: x[0], fin))):
    #   fin.append(nf, None)

    # return fin
    # if not res:
    #   return (sym, None)

    # else: # Should only be a single element in the list, if not oh well!
    #   return (res[0][0], res[0][1])

    #### getOdeGeneIds
    ##
    #### Given a list of gene symbols or whatever the hell the user is using
    #### in the batch file, this function returns symbol mapping,
    #### (ode_ref_id) --> ode_gene_ids. If the symbol doesn't exist in the DB
    #### or can't be found, it is mapped to None.
    #### All ode_ref_ids are converted to lowercase.
    ##
    def getOdeGeneIds(self, sp, syms):
        if type(syms) == list:
            syms = tuple(syms)

        query = '''SELECT DISTINCT ode_ref_id, ode_gene_id 
                   FROM extsrc.gene
                   WHERE sp_id = %s AND 
                         ode_pref = true AND 
                         lower(ode_ref_id) IN %s;'''

        self.cur.execute(query, [sp, syms])

        ## Returns a list of tuples [(ode_ref_id, ode_gene_id)]
        res = self.cur.fetchall()
        d = {}

        ## Ignore this wall of bullshit for now, unless you want to read
        ## about my failures.
        #
        ## The first query (above) finds all ode_ref_ids that are preferred
        ## (ode_pref == true). Not all the genes provided by a user will be
        ## preferred though (e.g. 147189_at). For these cases, we find the
        ## ode_gene_id they are mapped to, then query the DB for the preferred
        ## ode_gene_id for the species given. This way we add the pref. symbol
        ## and the user provided one to the gsv_source_list. If we still can't
        ## find it, then all hope is lost.
        found = map(lambda x: x[0].lower(), res)
        notfound = list(set(syms) - set(found))

        if notfound:
            res.extend(db.getOdeGeneIdsNonPref(sp, notfound))

        ## We return a dict of ode_ref_id --> ode_gene_ids
        for tup in res:
            #d[tup[0].lower()] = tup[1]
            d[tup[0]] = tup[1]

        return d

    #### getMicroarrayTypes
    ##
    #### Queries the DB for a list of microarray platforms and returns the
    #### result as a dict. The keys are pf_names and values are pf_ids.
    #### All pf_names are converted to lowercase.
    ##
    def getMicroarrayTypes(self):
        query = 'SELECT pf_id, pf_name FROM odestatic.platform;'

        self.cur.execute(query, [])

        ## Returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = {}

        ## We return a dict of pf_names --> pf_ids
        for tup in res:
            d[tup[1].lower()] = tup[0]

        return d

    def getPlatformProbes(self, pfid, refs):
        """
        Returns a mapping of prb_ref_ids -> prb_ids for the given platform
        and probe references.

        :arg int: platform ID (pf_id)
        :arg list: list of platform probes (prb_ref_id)
        :ret dict: reference to ID mapping
        """

        if type(refs) == list:
            refs = tuple(refs)

        qu = '''SELECT prb_ref_id, prb_id
                FROM odestatic.probe
                WHERE pf_id = %s AND
                      prb_ref_id IN %s;'''

        self.cur.execute(qu, [pfid, refs])

        ## Returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = dd(long)

        ## We return a dict of pf_names --> pf_ids
        for tup in res:
            d[tup[0]] = tup[1]

        return d

    def getProbe2Gene(self, prbids):
        """
        Returns a mapping of prb_ids -> ode_gene_ids for the given set
        of prb_ids.


        :arg int: platform ID (pf_id)
        :arg list: list of platform probes (prb_ref_id)
        :return:
        """

        if type(prbids) == list:
            prbids = tuple(prbids)

        qu = '''SELECT prb_id, ode_gene_id
                FROM extsrc.probe2gene
                WHERE prb_id IN %s;'''

        self.cur.execute(qu, [prbids])

        ## Returns a list of tuples [(pf_id, pf_name)]
        res = self.cur.fetchall()
        d = dd(list)

        ## We return a dict of prb_ids -> ode_gene_ids. This is a list since
        ## there may be 1:many associations.
        for tup in res:
            d[tup[0]].append(tup[1])

        return d


    #### getSpecies
    ##
    #### Queries the DB for a list of species and returns the result as a
    #### dict. The keys are sp_names and values are sp_ids. All sp_names are
    #### converted to lowercase.
    ##
    def getSpecies(self):
        query = 'SELECT sp_id, sp_name FROM odestatic.species;'

        self.cur.execute(query)

        ## Returns a list of tuples [(sp_id, sp_name)]
        res = self.cur.fetchall()
        d = {}

        ## We return a dict of sp_names --> sp_ids
        for tup in res:
            d[tup[1].lower()] = tup[0]

        return d

    #### insertFile
    ##
    #### Inserts a new row into the file table. Most of the columns for the file
    #### table are required as arguments.
    ##
    def insertFile(self, size, uri, contents, comments):
        query = ('INSERT INTO production.file (file_size, file_uri, '
                 'file_contents, file_comments, file_created, file_changes) '
                 'VALUES (%s, %s, %s, %s, NOW(), \'\') RETURNING file_id;')
        vals = [size, uri, contents, comments]

        self.cur.execute('set search_path = extsrc,production,odestatic;')
        self.cur.execute(query, vals)

        ## Returns a list of tuples [(file_id)]
        res = self.cur.fetchall()

        return res[0][0]

    #### insertPublication
    ##
    #### Given a dict whose keys are refer to columns of the publication table,
    #### this function inserts a new publication into the db.
    #### Don't forget to commit changes after calling this function.
    ##
    def insertPublication(self, pd):
        query = ('INSERT INTO production.publication (pub_authors, pub_title, '
                 'pub_abstract, pub_journal, pub_volume, pub_pages, '
                 'pub_pubmed) VALUES (%s, %s, %s, %s, %s, %s, %s) RETURNING '
                 'pub_id;')

        vals = [pd['pub_authors'], pd['pub_title'], pd['pub_abstract'],
                pd['pub_journal'], pd['pub_volume'], pd['pub_pages'],
                pd['pub_pubmed']]

        self.cur.execute(query, vals)

        ## Returns a list of tuples [(pub_id)]
        res = self.cur.fetchall()

        return res[0][0]

    #### insertGenesetValue
    ##
    def insertGenesetValue(self, gs_id, gene_id, value, name, thresh):
        query = ('INSERT INTO extsrc.geneset_value (gs_id, ode_gene_id, '
                 'gsv_value, gsv_hits, gsv_source_list, gsv_value_list, '
                 'gsv_in_threshold, gsv_date) VALUES (%s, %s, %s, 0, %s, %s, '
                 '%s, NOW());')

        thresh = 't' if value <= thresh else 'f'
        vals = [gs_id, gene_id, value, [name], [float(value)], thresh]

        self.cur.execute(query, vals)

    #### insertGeneset
    ##
    #### Given a dict whose keys are refer to columns of the geneset table,
    #### this function inserts a new geneset into the db.
    #### Don't forget to commit changes after calling this function.
    ##
    def insertGeneset(self, gd):
        query = ('INSERT INTO geneset (file_id, usr_id, cur_id, sp_id, '
                 'gs_threshold_type, gs_threshold, gs_created, '
                 'gs_updated, gs_status, gs_count, gs_uri, gs_gene_id_type, '
                 'gs_name, gs_abbreviation, gs_description, gs_attribution, '
                 'gs_groups, pub_id) '
                 'VALUES (%s, %s, %s, %s, %s, %s, NOW(), NOW(), \'normal\', '
                 '%s, \'\', %s, %s, %s, %s, 0, %s, %s) RETURNING gs_id;')

        vals = [gd['file_id'], gd['usr_id'], gd['cur_id'], gd['sp_id'],
                gd['gs_threshold_type'], gd['gs_threshold'], gd['gs_count'],
                gd['gs_gene_id_type'], gd['gs_name'], gd['gs_abbreviation'],
                gd['gs_description'], gd['gs_groups'], gd['pub_id']]

        self.cur.execute('set search_path = extsrc,production,odestatic;')
        self.cur.execute(query, vals)

        ## Returns a list of tuples [(gs_id)]
        res = self.cur.fetchall()

        return res[0][0]

    #### updateGenesetCount
    ##
    #### Updates gs_count for a given gs_id. Required since genesets are first
    #### made, then geneset_values are validated and added.
    ##
    def updateGenesetCount(self, gsid, count):
        query = 'UPDATE geneset SET gs_count = %s WHERE gs_id = %s'
        self.cur.execute(query, [count, gsid])

    #### commit
    ##
    #### Commits changes made to the DB. Only required if we've inserted new
    #### genesets, geneset_values, or publications.
    ##
    def commit(self):
        self.conn.commit()


## DB global, should only be one instance of this class
db = TheDB()

def eatWhiteSpace(s):
    """
    Removes leading + trailing whitespace from a given string.

    :arg string:
    :ret string:
    """

    return s.strip()

def readBatchFile(fp):
    """
    Reads the file at the given filepath and returns all the lines that
    comprise the file.

    :arg string: filepath to read
    :ret list: a list of strings--each line in the file
    """

    with open(fp, 'r') as fl:
        return fl.readlines()

def makeDigrams(s):
    """
    Recursively creates an exhaustive list of digrams from the given string.

    :arg string:
    :ret list: list of strings, each string is a digram
    """

    if len(s) <= 2:
        return [s]

    b = makeDigrams(s[1:])
    b.insert(0, s[:2])

    return b

def calcStringSimilarity(s1, s2):
    """
    Calculates the percent similarity between two strings. Meant to be a
    replacement for PHP's similar_text function, which old GeneWeaver uses
    to determine the right microarray platform to use.
    Couldn't find how similar_text was implemented (just that it used some
    algorithm in the book 'Programming Classics' by Oliver) so this function
    is fairly different but achieves the same result. This algorithm uses
    digrams and their intersections to determine percent similarity. It is
    calculated as:

    sim(s1, s2) = (2 * intersection(digrams(s1), digrams(s2)) /
                   |digrams(s1) + digrams(s2)|

    :param string:
    :param string:
    :ret float: percent similarity
    """

    sd1 = makeDigrams(s1)
    sd2 = makeDigrams(s2)
    intersect = list((mset(sd1) & mset(sd2)).elements())

    return (2 * len(intersect)) / float(len(sd1) + len(sd2))

def parseScoreType(s):
    """
    Attempts to parse out the score type and any threshold value
    from a given string.
    Acceptable score types and threshold values include:
        Binary
        P-Value < 0.05
        Q-Value < 0.05
        0.40 < Correlation < 0.05
        6.0 < Effect < 22.50
    The numbers can vary and if they can't be parsed, default values
    (e.g. 0.05) are used.
    There is an issue with the regexs in this function. See the TODO list
    at the top of the file for a description.

    :param string: string containing score type and possibly threshold value
    :return tuple: (gs_threshold_type, gs_threshold, errors)
    """

    stype = ''
    thresh = '0.05'
    thresh2 = '0.05'
    error = ''

    ## Binary threshold is left at the default of 0.05
    if s.lower() == 'binary':
        stype = '3'
        thresh = '1'

    elif s.lower().find('p-value') != -1:
        ## Try to find the threshold, this regex is from the PHP func.
        ## my regex: ([0-9]?\.[0-9]+)
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
        ## This disgusting regex is from the PHP function
        ## And it sucks. It breaks on some input, might have to change this
        ## later.
        m = re.search(r"([0-9.-]{2,})[^0-9.-]*([0-9.-]{2,})", s.lower())
        stype = '4'

        if m:
            thresh = m.group(1) + ',' + m.group(2)  # parenthesized group
        else:
            thresh = '-0.75,0.75'
            error = ('No thresholds specified for Correlation data.'
                     ' Using -0.75 < value < 0.75.')

    elif s.lower().find('effect') != -1:
        ## Again, PHP regex
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

    return (stype, thresh, error)


#### makeGeneset
##
##
def makeGeneset(name, abbr, desc, spec, pub, grp, ttype, thresh, gtype, vals,
                usr=0, cur_id=5, annotations=None):
    """
    Given a shitload of arguments, this function returns a dictionary
    representation of a single geneset. Each key is a different column found
    in the geneset table. Not all columns are (or need to be) represented.

    TODO:   Need to retrieve the user's id and attach it, right now it just
            uses a placeholder.

    :arg string: geneset name
    :arg string: geneset abbreviation
    :arg string: geneset description
    :arg int: species ID, converted to an int if a string
    :arg int: publication ID
    :arg string: group ID, should be a string not an int
    :arg int: threshold type
    :arg string: geneset threshold, see parseScoreType for a description
    :arg int: gene ID type
    :arg list: geneset_values, a list of tuples (gene, value)
    :arg int: user ID
    :arg int: curation ID, unless specified it defaults to private (5)
    :ret dict: geneset
    """

    gs = {}

    gs['gs_name'] = name
    gs['gs_abbreviation'] = abbr
    gs['gs_description'] = desc
    gs['sp_id'] = int(spec)
    gs['gs_groups'] = grp
    gs['pub_id'] = pub  # The pubmed article still needs to retrieved
    gs['gs_threshold_type'] = int(ttype)
    gs['gs_threshold'] = thresh
    gs['gs_gene_id_type'] = int(gtype)
    gs['usr_id'] = int(usr)
    gs['values'] = vals  # Not a column in the geneset table; processed later
    gs['annotations'] = annotations # Not a column in the geneset table, etc.

    ## Other fields we can fill out
    gs['gs_count'] = len(vals)
    gs['cur_id'] = cur_id  # auto private tier?

    return gs


#### getPubmedInfo
##
#### Retrieves Pubmed article info from the NCBI servers using the NCBI eutils.
#### The result is a dictionary whose keys are the same as the publication
#### table. The actualy return value for this function though is a tuple. The
#### first member is the dict, the second is any error message.
##
def getPubmedInfo(pmid):
    ## URL for pubmed article summary info
    url = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?'
           'retmode=json&db=pubmed&id=%s') % pmid
    ## NCBI eFetch URL that only retrieves the abstract
    url_abs = ('http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'
               '?rettype=abstract&retmode=text&db=pubmed&id=%s') % pmid

    ## Sometimes the NCBI servers shit the bed and return errors that kill
    ## the python script, we catch these and just return blank pubmed info
    try:
        res = url2.urlopen(url).read()
        res2 = url2.urlopen(url_abs).read()

    except url2.HTTPError:
        er = ('Error! There was a problem accessing the NCBI servers. No '
              'PubMed info for the PMID you provided could be retrieved.')
        return ({}, er)

    pinfo = {}
    res = json.loads(res)

    ## In case of KeyErrors...
    try:
        pub = res['result']
        pub = pub[pmid]

        pinfo['pub_title'] = pub['title']
        pinfo['pub_abstract'] = res2
        pinfo['pub_journal'] = pub['fulljournalname']
        pinfo['pub_volume'] = pub['volume']
        pinfo['pub_pages'] = pub['pages']
        pinfo['pub_pubmed'] = pmid
        pinfo['pub_authors'] = ''

        ## Author struct {name, authtype, clustid}
        for auth in pub['authors']:
            pinfo['pub_authors'] += auth['name'] + ', '

        ## Delete the last comma + space
        pinfo['pub_authors'] = pinfo['pub_authors'][:-2]

    except:
        er = ('Error! The PubMed info retrieved from NCBI was incomplete. No '
              'PubMed data will be attributed to this geneset.')
        return ({}, er)

    return (pinfo, '')


#### parseBatchFile
##
##
def parseBatchFile(lns, usr=0, cur=5):
    """
    Parses the batch file according to the format listed on
    http://geneweaver.org/index.php?action=manage&cmd=batchgeneset

    :param list: list of strings, one per line of the batch file
    :param int: user ID to associate with the parsed genesets
    :param int: curation ID
    :ret tuple: triplet (list of gensets, list of warnings, list of errors)
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
    onts = []   # ontology annotations
    cerr = ''  # critical errors discovered during parsing
    ncerr = []  # non-critical errors discovered during parsing
    errors = [] # critical errors discovered during parsing
    warns = [] # non-critical errors discovered during parsing

    #for ln in lns:
    for i in range(len(lns)):
        #ln = eatWhiteSpace(ln)
        lns[i] = lns[i].strip()

        ## :, =, + are required for all datasets
        #
        ## Lines beginning with ':' are geneset abbreviations (REQUIRED)
        #if ln[:1] == ':':
        if lns[i][:1] == ':':
            ## This checks to see if we've already read in some geneset_values
            ## If we have, that means we can save the geneset, clear out any
            ## REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                ## Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            #abbr = eatWhiteSpace(ln[1:])
            abbr = eatWhiteSpace(lns[i][1:])

        ## Lines beginning with '=' are geneset names (REQUIRED)
        #elif ln[:1] == '=':
        elif lns[i][:1] == '=':
            ## This checks to see if we've already read in some geneset_values
            ## If we have, that means we can save the geneset, clear out any
            ## REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                ## Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            #name = eatWhiteSpace(ln[1:])
            name = eatWhiteSpace(lns[i][1:])

        ## Lines beginning with '+' are geneset descriptions (REQUIRED)
        #elif ln[:1] == '+':
        elif lns[i][:1] == '+':
            ## This checks to see if we've already read in some geneset_values
            ## If we have, that means we can save the geneset, clear out any
            ## REQUIRED fields before we do more parsing, and start over
            if gsvals:
                gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                                 thresh, gene, gsvals, usr, cur)
                ## Start a new dataset
                abbr = ''
                desc = ''
                name = ''
                gsvals = []
                genesets.append(gs)

            #desc += eatWhiteSpace(ln[1:])
            desc += eatWhiteSpace(lns[i][1:])
            desc += ' '

        ## !, @, %, are required but can be omitted from later sections if
        ## they don't differ from the first.
        #
        ## Lines beginning with '!' are score types (REQUIRED)
        #elif ln[:1] == '!':
        elif lns[i][:1] == '!':
            #score = eatWhiteSpace(ln[1:])
            score = eatWhiteSpace(lns[i][1:])
            score = parseScoreType(score)

            ## Indicates a critical error has occured (no score type w/ an
            ## error message)
            if not score[0] and score[2]:
                #cerr = score[2]
                #break
                errors.append(score[2])

            else:
                stype = score[0]
                thresh = score[1]

            ## Any warnings
            if score[0] and score[2]:
                #ncerr.append(score[2])
                warns.append(score[2])

        ## Lines beginning with '@' are species types (REQUIRED)
        #elif ln[:1] == '@':
        elif lns[i][:1] == '@':
            #spec = eatWhiteSpace(ln[1:])
            spec = eatWhiteSpace(lns[i][1:])
            specs = db.getSpecies()

            if spec.lower() not in specs.keys():
                #cerr = ('Critical error! There is no data for the species (%s) '
                #        'you specified. ' % spec)
                #break
                err = 'LINE %s: %s is an invalid species' % (i + 1, spec)
                errors.append(err)

            else:
                ## spec is now an integer (sp_id)
                spec = specs[spec.lower()]

        ## Lines beginning with '%' are gene ID types (REQUIRED)
        #elif ln[:1] == '%':
        elif lns[i][:1] == '%':
            #gene = eatWhiteSpace(ln[1:])
            gene = eatWhiteSpace(lns[i][1:])

            ## In the PHP source, it looks like the gene type is checked
            ## to see if it's a microarray first, if it is then the pf_id is
            ## used, otherwise gdb_id is used. Doesn't make much sense because
            ## some pf_ids overlap with gdb_ids. On second glance the PHP code
            ## for gene id types makes no fucking sense but whatever.
            if gene.lower().find('microarray') != -1:
                plats = db.getMicroarrayTypes()
                origplat = gene
                gene = gene[len('microarray '):]  # delete 'microarray ' text

                ## Determine the closest microarry platform match. The PHP
                ## function calculated % string similarity between the user
                ## supplied platform and the list of plats in the db, choosing
                ## the one with the best match
                best = 0.70
                for plat, pid in plats.items():
                    sim = calcStringSimilarity(plat.lower(), origplat.lower())

                    if sim > best:
                        best = sim
                        gene = plat

                ## Convert to the ID, gene will now be an integer
                gene = plats.get(gene, 'unknown')

                if type(gene) != int:
                    err = 'LINE %s: %s is an invalid platform' % \
                          (i + 1, origplat)
                    errors.append(err)
                    #cerr = ('Critical error! We aren\'t sure what microarray '
                    #        'platform (%s) you specified. Check the list of '
                    #        'supported platforms.' % origplat)
                    #break

            ## Otherwise the user specified one of the gene types, not a
            ## microarray platform
            ## :IMPORTANT: Expression platforms have positive (+)
            ## gs_gene_id_types while all other types (e.g. symbols) should
            ## have negative (-) integer ID types.
            else:
                types = db.getGeneTypes()

                if gene.lower() not in types.keys():
                    #cerr = ('Critical error! There is no data for the gene type '
                    #        '(%s) you specified.' % gene)
                    #break
                    err = 'LINE %s: %s is an invalid gene type' % (i + 1, gene)
                    errors.append(err)

                else:
                    ## gene is now an integer (gdb_id)
                    gene = types[gene.lower()]
                    ## Negate, see comment tagged important above
                    gene = -gene


        ## Lines beginning with 'P ' are PubMed IDs (OPTIONAL)
        #elif (ln[:2].lower() == 'p ') and (len(ln.split('\t')) == 1):
        elif (lns[i][:2].lower() == 'p ') and (len(lns[i].split('\t')) == 1):
            #pub = eatWhiteSpace(ln[1:])
            pub = eatWhiteSpace(lns[i][1:])

        ## Lines beginning with '~ ' are ontology annotations (OPTIONAL)
        elif (lns[i][:2] == '~ ') and (len(lns[i].split('\t')) == 1):
            onts.append(eatWhiteSpace(lns[i][1:]))

        ## Lines beginning with 'A' are groups, default is private (OPTIONAL)
        #elif ln[:2].lower() == 'a ' and (len(ln.split('\t')) == 1):
        elif lns[i][:2].lower() == 'a ' and (len(lns[i].split('\t')) == 1):
            #group = eatWhiteSpace(ln[1:])
            group = eatWhiteSpace(lns[i][1:])

            ## If the user gives something other than private/public,
            ## automatically make it private
            if group.lower() != 'private' and group.lower() != 'public':
                group = '-1'
                cur = 5

            ## Public data sets are initially thrown into the provisional
            ## Tier IV. Tier should never be null.
            elif group.lower() == 'public':
                group = '0'
                cur = 4

            else:  # private
                group = '-1'
                cur = 5

        ## If the lines are tab separated, we assume it's the gene data that
        ## will become apart of the geneset_values
        #elif len(ln.split('\t')) == 2:
        elif len(lns[i].split('\t')) == 2:

            ## First we check to see if all the required data was specified
            if ((not abbr) or (not name) or (not desc) or (not stype) or
                    (not spec) or (not gene)):
                #cerr = ('Critical error! Looks like one of the required '
                #        'fields is missing.')
                #break
                err = 'One or more of the required fields are missing.'
                ## Otherwise this string will get appended a bajillion times
                if err not in errors:
                    errors.append(err)
                #pass


            #ln = ln.split()
            else:
                lns[i] = lns[i].split()

                ## I don't think this code can ever be reached...
                if len(lns[i]) < 2:
                    err = 'LINE %s: Skipping invalid gene, value formatting' \
                          % (i + 1)
                    warns.append(err)

                else:
                    gsvals.append((lns[i][0], lns[i][1]))

            #if len(ln) < 2:
            #    cerr = ("Critical error! Looks like there isn't a value "
            #            "associated with the gene %s. Or maybe you forgot to "
            #            "use tabs." % ln[0])
            #    break

            #gsvals.append((ln[0], ln[1]))

        ## Lines beginning with '#' are comments
        #elif ln[:1] == '#':
        elif lns[i][:1] == '#':
            continue

        ## Skip blank lines
        #elif ln[:1] == '':
        elif lns[i][:1] == '':
            continue

        ## Who knows what the fuck this line is, just skip it
        else:
            #ncerr.append('BAD LINE: ' + ln)
            err = 'LINE %s: Skipping unknown identifiers' % (i + 1)
            warns.append(err)

    ## awwww shit, we're finally finished! Check for critical errors and
    ## if there were none, make the final geneset and return
    #if cerr:
    #    return ([], ncerr, cerr)
    if errors:
        return ([], warns, errors)

    else:
        gs = makeGeneset(name, abbr, desc, spec, pub, group, stype,
                         thresh, gene, gsvals, usr, cur)
        genesets.append(gs)

        #return (genesets, ncerr, [])
        return (genesets, warns, errors)


#### makeRandomFilename
##
#### Generates a random filename for the file_uri column in the file table. The
#### PHP version of this function (getRandomFilename) combines the user's
#### email, the string '_ODE_', the current date, and a random number. Since
#### this script is offline right now, I'm just using 'GW_' + date + '_' + a
#### random six letter alphanumeric string. Looking at the file_uri contents
#### currently in the db though, there seems to be a ton of variation in the
#### naming schemes.
##
def makeRandomFilename():
    lets = 'abcdefghijklmnopqrstuvwxyz1234567890'
    rstr = ''
    now = datetime.datetime.now()

    for i in range(6):
        rstr += random.choice('abcdefghijklmnopqrstuvwxyz1234567890')

    return ('GW_' + str(now.year) + '-' + str(now.month) + '-' +
            str(now.day) + '_' + rstr)


#### buFile
##
#### Parses geneset content into the proper format and inserts it into the file
#### table. The proper format is gene\tvalue\n .
##
def buFile(genes):
    conts = ''
    ## Geneset values should be a list of tuples (symbol, pval)
    for tup in genes:
        conts += (tup[0] + '\t' + tup[1] + '\n')

    return db.insertFile(len(conts), makeRandomFilename(), conts, '')


#### buGenesetValues
##
#### Batch upload geneset values.
##
def buGenesetValues(gs):
    ## Geneset values should be a list of tuples (symbol, pval)
    ## First we attempt to map them to the internal ode_gene_ids
    symbols = filter(lambda x: not not x, gs['values'])
    symbols = map(lambda x: x[0], symbols)

    ## Negative numbers indicate normal genetypes (found in genedb) while
    ## positive numbers indicate expression platforms and more work :(
    if gs['gs_gene_id_type'] < 0:
        sym2ode = db.getOdeGeneIds(gs['sp_id'], symbols)

        ## Save gene symbol with proper capitalization
        for sym in sym2ode.keys():
            sym2ode[sym.lower()] = (sym, sym2ode[sym])

    else:
        sym2probe = db.getPlatformProbes(gs['gs_gene_id_type'], symbols)
        prbids = []

        for sym in symbols:
            prbids.append(sym2probe[sym])

        prbids = list(set(prbids))
        prb2odes = db.getProbe2Gene(prbids)


    # non-critical errors we will inform the user about
    noncrit = []
    # duplicate detection
    dups = dd(str)
    total = 0

    for tup in gs['values']:

        ## Platform handling
        if gs['gs_gene_id_type'] > 0:
            sym = tup[0]
            value = tup[1]
            prbid = sym2probe[sym]
            odes = prb2odes[prbid]

            if not prbid or not odes:
                err = ("Error! There doesn't seem to be any gene/locus data for "
                       "%s in the database." % sym)
                noncrit.append(err)
                continue

            for ode in odes:
                ## Check for duplicate ode_gene_ids, otherwise postgres bitches
                if not dups[ode]:
                    dups[ode] = tup[0]

                else:
                    err = ('Error! Seems that %s is a duplicate of %s. %s was not '
                           'added to the geneset.' %
                           (sym, dups[ode], sym))
                    noncrit.append(err)
                    continue

                db.insertGenesetValue(gs['gs_id'], ode, value, sym,
                                      'true')
                                      #gs['gs_threshold'])

                total += 1

            continue

        ## Not platform stuff
        if not sym2ode[tup[0].lower()][1]:
            err = ("Error! There doesn't seem to be any gene/locus data for "
                   "%s in the database." % tup[0])
            noncrit.append(err)
            continue

        ## Check for duplicate ode_gene_ids, otherwise postgres bitches
        if not dups[sym2ode[tup[0].lower()][1]]:
            dups[sym2ode[tup[0].lower()][1]] = tup[0]

        else:
            err = ('Error! Seems that %s is a duplicate of %s. %s was not '
                   'added to the geneset.' %
                   (tup[0], dups[sym2ode[tup[0].lower()]], tup[0]))
            noncrit.append(err)
            continue

        #print sym2ode[tup[0].lower()][1]
        #print dups
        ## Remember to lower that shit, forgot earlier :(
        db.insertGenesetValue(gs['gs_id'], sym2ode[tup[0].lower()][1], tup[1],
                              sym2ode[tup[0].lower()][0], gs['gs_threshold'])

        total += 1

    return (total, noncrit)


#### buGenesets
##
#### Batch upload genesets. Requires the filepath to the batch upload file.
#### Takes two additional (optional) parameters, a usr_id and cur_id, which
#### are provided as command line arguments. This allows the person running
#### the script to change usr_ids and cur_ids, which are currently set to 0
#### and 5 (private) respectively, for this "offline" version of the script.
##
def buGenesets(fp, usr_id=0, cur_id=5):
    noncrits = []  # non-critical errors we will inform the user about
    added = []  # list of gs_ids successfully added to the db

    ## returns (genesets, non-critical errors, critical errors)
    b = parseBatchFile(readBatchFile(fp), usr_id, cur_id)

    ## A critical error has occurred
    if b[2]:
        print b[2]
        print ''
        exit()

    else:
        genesets = b[0]
        noncrits = b[1]

    for gs in genesets:
        ## If a PMID was provided, we get the info from NCBI
        if gs['pub_id']:
            pub = getPubmedInfo(gs['pub_id'])
            gs['pub_id'] = pub[0]

            ## Non-crit pubmed retrieval errors
            if pub[1]:
                noncrits.append(pub[1])

            ## New row in the publication table
            if gs['pub_id']:
                gs['pub_id'] = db.insertPublication(gs['pub_id'])
            else:
                gs['pub_id'] = None  # empty pub

        else:
            gs['pub_id'] = None  # empty pub

        ## Insert the data into the file table
        gs['file_id'] = buFile(gs['values'])
        ## Insert new genesets and geneset_values
        gs['gs_id'] = db.insertGeneset(gs)
        gsverr = buGenesetValues(gs)

        # Update gs_count if some geneset_values were found to be invalid
        if gsverr[0] != len(gs['values']):
            db.updateGenesetCount(gs['gs_id'], gsverr[0])

        added.append(gs['gs_id'])

        # Non-critical errors discovered during geneset_value creation
        if gsverr[1]:
            noncrits.extend(gsverr[1])

        ## Add ontology annotations provided they exist
        if gs['annotations']:
            ont_ids = geneweaverdb.get_ontologies_by_refs(gs['annotations'])

            for ont_id in ont_ids:
                geneweaverdb.add_ont_to_geneset(
                    gs['gs_id'], ont_id, 'Manual Association'
                )

    #db.commit()

    return (added, noncrits)


if __name__ == '__main__':
    from optparse import OptionParser
    from sys import argv

    # cmd line shit
    usage = 'usage: %s [options] <batch_file>' % argv[0]
    parse = OptionParser(usage=usage)

    parse.add_option('-u', action='store', type='string', dest='usr_id',
                     help='Specify a usr_id for newly added genesets')
    parse.add_option('-c', action='store', type='string', dest='cur_id',
                     help='Specify a cur_id for newly added genesets')

    (opts, args) = parse.parse_args(argv)

    if len(args) < 2:
        print '[!] You need to provide a batch geneset file.'
        parse.print_help()
        print ''
        exit()

    if not opts.usr_id:
        opts.usr_id = 0
    if not opts.cur_id:
        opts.cur_id = 5

    ## Where all the magic happens
    stuff = buGenesets(args[1], opts.usr_id, opts.cur_id)

    print '[+] The following genesets were added:'
    print ', '.join(map(str, stuff[0]))
    print ''

    if stuff[1]:
        print '[!] There were some non-critical errors with the batch file:'
        for er in stuff[1]:
            print er
        print ''

