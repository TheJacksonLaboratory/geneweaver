#!/usr/bin/env python

#### file:  monarch.py
#### desc:  Wrapper for the Monarch Initiative's text annotator.
#### vers:  0.1.0
#### auth:  TR
##

import json
import urllib as url
import urllib2 as url2

BASE_URL = 'https://scigraph-ontology.monarchinitiative.org/scigraph'
## Couldn't find this endpoint anywhere in the documentation, but it's buried
## in Monarch's source code. If it changes, you might have to look there.
ANNOTATE_URL = BASE_URL + '/annotations/entities.json'
## The ontologies we care about
ONT_IDS = ['MESH', 'GO', 'MP', 'MA']

def fetch_monarch_annotations(text):
    """
    Sends a chunk of text to Monarch's annotation service and returns a list
    of annotations for several ontologies.

    :arg str: the text to annotate
    :ret list: list of annotation objects (dicts) retured by MI
    """

    ## If longestOnly == true, only the longest text matches are returned
    params = {'content': text, 'longestOnly': 'false'}
    params = url.urlencode(params)

    ## Attempt connecting pulling annotation data. Quits if an exception
    ## is handled three times.
    for attempt in range(3):
        try:
            req = url2.Request(ANNOTATE_URL, params)
            res = url2.urlopen(req)
            res = res.read()

        except url2.HTTPError as e:
            print 'Failed to retrieve annotation data:'
            print e
            continue

        ## Success
        break

    ## for-else construct: if the loop doesn't break (in our case this
    ## indicates success) then this statement is executed
    else:
        print 'Failed to retrieve annotation data after three attempts'
        return []

    return json.loads(res)

def parse_monarch_annotations(annots):
    """
    Given a list of annotation objects retrieved from MI, this function 
    parses out and returns ontology IDs.

    :arg list: list of annotation objects from MI
    :ret list: list of terms
    """

    ontids = []
    ## Remove a nested level
    annots = map(lambda d: d['token'], annots)

    for anno in annots:
        ontid = anno['id']

        ontids.append(ontid)

    ontids = map(lambda s: s.encode('ascii', 'ignore'), ontids)
    ontids = list(set(ontids))

    return ontids

def filter_monarch_annotations(annots, onts):
    """
    Filters out any annotations that don't belong in the specified ontologies.
    If the annotations were retrieved from an API, they should be converted to
    ASCII prior to this function (or just make sure both the annotations and
    ontology strings are unicode).

    :arg list: annotations
    :arg list: ontologies
    :ret list: annotations that are members of the given ontologies
    """

    pure = []
    onts = map(lambda s: s.lower(), onts)
    ## MI ontology IDs are returned as ONT:1234
    pure = filter(lambda a: a.split(':')[0].lower() in onts, annots)

    return pure

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
    an = fetch_monarch_annotations(text)
    an = parse_monarch_annotations(an)

    print an
    print filter_monarch_annotations(an, ONT_IDS)

