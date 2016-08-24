#!/usr/bin/env python

#### file:  ncbo.py
#### desc:  A rewrite of Jeremy Jay's NCBO annotator code. The original
####	    code was no longer working due to NCBO API modifications 
####        and an obsolete API key. This refactoring fixes those bugs
####        cleans up the code a bit, and adds comments where necessary.
#### vers:  0.1.0
#### auth:  TR
##

import json
import urllib as url
import urllib2 as url2

NCBO_BASE = 'http://data.bioontology.org'
NCBO_ANNOTATOR = NCBO_BASE + '/annotator?'
## My NCBO API key (Jeremy's no longer worked). If this ever needs to be
## replaced, head over to http://bioportal.bioontology.org/accounts/new
## and register a new account.
API_KEY = '2709bdd2-c311-4089-b000-56fa3d33307c'
## I _think_ ontology IDs are just the abbreviations.
## Not explicitly in the NCBO docs, but this seems to work and the virtual
## ontology IDs in Jeremy's original code no longer work. 
NCBO_IDS = ['MESH', 'GO', 'MP', 'MA']

def fetch_ncbo_annotations(text, ncboids):
    """
    Given a chunk of text and a set of NCBO ontology IDs, this function will
    send the text to NCBO and return a list of annotations for the given
    ontologies.

    :arg str: the text to annotate
    :arg list: list of ontology IDs
    :ret list: list of annotation objects (dicts) retured by NCBO
    """

    ncboids = list(set(ncboids))
    ncboids = map(str, ncboids)
    ncboids = ','.join(ncboids)

    params = {'apikey': API_KEY, 
              'format': 'json', 
              'ontologies': ncboids,
              'text': text}
    params = url.urlencode(params)

    ## Attempt connecting to NCBO and pulling annotation data. Quits if an 
    ## exception is handled three times.
    for attempt in range(3):
        try:
            req = url2.Request(NCBO_ANNOTATOR, params)
            res = url2.urlopen(req)
            res = res.read()

        except url2.HTTPError as e:
            print 'Failed to retrieve annotation data from NCBO:'
            print e
            continue

        ## Success
        break

    ## for-else construct: if the loop doesn't break (in our case this
    ## indicates success) then this statement is executed
    else:
        print 'Failed to retrieve annotation data after three attempts'
        exit()

    return json.loads(res)

def get_ncbo_link(link):
    """
    NCBO uses (awful) LD flavored JSON. So almost every member of an object
    returned by the NCBO API is in the form of a link which then 
    requires further API calls to retrieve the data.
    This function calls any API returned link and (hopefully) returns the
    actual data after JSON parsing.

    :arg str: link to follow and retrieve data from
    :ret dict: some object representing data at the link
    """

    opener = url2.build_opener()
    opener.addheaders = [('Authorization', 'apikey token=' + API_KEY)]

    for attempt in range(3):
        try:
            res = opener.open(link)
            res = res.read()

        except url2.HTTPError as e:
            print 'Failed to retrieve annotation data from an NCBO link:'
            print e
            continue

        ## Success
        break

    else:
        print 'Failed to retrieve data from an NCBO URL'
        return None

    return json.loads(res)

def parse_ncbo_annotations(annots):
    """
    Given a list of annotation objects retrieved from NCBO, this function 
    parses out and returns IDs. The object list can be retrieved by calling
    fetch_ncbo_terms().

    :arg list: list of annotation objects from NCBO
    :ret list: list of terms
    """

    ontids = []

    for anno in annots:
        link = anno['annotatedClass']['links']['self']
        details = get_ncbo_link(link)

        if not details:
            continue

        ## Everything is in unicode
        ontid = details[u'@id']
        ontname = details[u'prefLabel']
        ## The stupid ID is a URL, so we remove everything except the end
        index = ontid.rfind(u'/')
        ## Plus one to skip the slash
        ontid = ontid[(index + 1):]
        ## Some ontologies use ':' (e.g. GO:001, MP:001) as part of their IDs
        ## but NCBO converts these to '_'.
        ontid = ontid.replace(u'_', u':')

        ontids.append(ontid)

    ontids = map(lambda s: s.encode('ascii', 'ignore'), ontids)
    ontids = list(set(ontids))

    return ontids

if __name__ == '__main__':

    text = '''Highly addictive drugs like nicotine and amphetamine not only
    change an individual's behaviour in the short and long-term, they also
    induce persistent changes in neuronal excitability and morphology. Although
    research has started to examine the epigenetic changes that occur
    immediately after drug exposure, there has been little investigation into
    the persistent modifications to the epigenome that likely moderate the
    stable maintenance of the neurological changes. Male Long-Evans rats were
    administered amphetamine, nicotine, or saline for 14 consecutive days,
    given a 14 day withdrawal period, and then sacrificed. DNA from the mPFC,
    OFC, and nucleus accumbens (NAc) was used for global DNA methylation
    analysis and RNA from the same brain regions was used for gene expression
    analysis. Following the two-week withdrawal period, exposure to amphetamine
    or nicotine was associated with a decrease in global DNA methylation in
    each brain region examined.'''

    ## Sample usage
    an = fetch_ncbo_annotations(text, NCBO_IDS)
    print parse_ncbo_annotations(an)

