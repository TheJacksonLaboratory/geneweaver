## This file contains API wrappers and related functions for annotating user
## uploaded genesets. For now, two separate annotation services (NCBO and the
## Monarch Initiative) are used since the latter is missing MA annotations.
## Separate stand-alone versions of these wrappers can be found, for now,
## at git clone git@fin0c.net:gwp-curation-server

import json
import urllib as url
import urllib2 as url2

NCBO_URL = 'http://data.bioontology.org'
NCBO_ANNOTATOR = NCBO_URL + '/annotator?'
## My NCBO API key (Jeremy's no longer worked). If this ever needs to be
## replaced, head over to http://bioportal.bioontology.org/accounts/new
## and register a new account.
API_KEY = '2709bdd2-c311-4089-b000-56fa3d33307c'
## NCBO docs are kinda shitty but I _think_ ontology IDs it uses are just the
## abbreviations. This seems to work, and nothing else is specified in the
## docs about ontology IDs so...
ONT_IDS = ['MESH', 'GO', 'MP', 'MA']
MONARCH_URL = 'https://scigraph-ontology.monarchinitiative.org/scigraph'
## Couldn't find this endpoint anywhere in the documentation, but it's buried
## in Monarch's source code. If it changes, you might have to look there.
MONARCH_ANNOTATOR = MONARCH_URL + '/annotations/entities.json'

def fetch_ncbo_annotations(text, ncboids):
    """
    Given a chunk of text and a set of NCBO ontology IDs, this function will
    send the text to NCBO and return a list of annotations for the given
    ontologies.

    :arg str: the text to annotate
    :arg list: list of ontology IDs (abbreviations) to use when annotating
    :ret list: list of annotation IDs
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
    Since NCBO enjoys testing the sanity of it's users, (almost) every member
    of an object returned by the NCBO API is in the form of a link which then
    requires further API calls to retrieve the data.
    This function calls any API returned link and (hopefully) returns the
    actual data after JSON parsing.

    :arg str: JSON-LD link
    :ret dict: json object representing whatever data we retrieved
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

    :arg list: list of JSON annotation objects returned by NCBO
    :ret list: list of annotation IDs
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
        ## Some ontologies use ':' (e.g. GO:001, MP:001) but NCBO converts ':'
        ## to '_', so we convert back
        if ontid.find(u':'):
            ontid = ontid.replace(u'_', u':')

        ontids.append(ontid)

    ontids = map(lambda s: s.encode('ascii', 'ignore'), ontids)
    ontids = list(set(ontids))

    return ontids


def fetch_monarch_annotations(text):
    """
    Sends a chunk of text to Monarch's annotation service and returns a list
    of annotations for several ontologies.

    :arg str: the text to annotate
    :ret list: list of annotation IDs
    """

    ## If longestOnly == true, the annotator will always use the longest match
    params = {'content': text, 'longestOnly': 'false'}
    params = url.urlencode(params)

    ## Attempt connecting pulling annotation data. Quits if an exception
    ## is handled three times.
    for attempt in range(3):
        try:
            req = url2.Request(MONARCH_ANNOTATOR, params)
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

    :arg list: list of JSON annotation objects returned by MI
    :ret list: list of annotation IDs
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

    :arg list: annotation IDs
    :arg list: list of ontologies whose annotations we want to keep
    :ret list: annotation IDs
    """

    onts = map(lambda s: s.lower(), onts)
    ## MI ontology IDs are returned as ONT:1234
    pure = filter(lambda a: a.split(':')[0].lower() in onts, annots)

    return pure

def annotate_text(text, onts):
    """
    Annotates a chunk of text to various ontologies using the NCBO and MI
    annotation services.

    :arg str: the text to annotate
    :arg list: ontologies to use during the annotation
    :ret list: annotation IDs
    """

    ncbo_onts = fetch_ncbo_annotations(text, onts)
    ncbo_onts = parse_ncbo_annotations(ncbo_onts)
    mi_onts = fetch_monarch_annotations(text)
    mi_onts = parse_monarch_annotations(mi_onts)
    mi_onts = filter_monarch_annotations(mi_onts, onts)

    ## Monarch initiative returns MESH annotations as MESH:D1234, while
    ## NCBO and the GW DB just use the unique ID (D1234).
    for i in range(len(mi_onts)):
        if mi_onts[i].find('MESH') != -1:
            mi_onts[i] = mi_onts[i].split(':')[1].strip()

    ## Prevent annotation duplicates
    ncbo_onts = list(set(ncbo_onts) - set(mi_onts))

    return (mi_onts, ncbo_onts)

def insert_annotations(dbcur, gsid, desc, abstract):
    """

    :arg obj:
    :arg int:
    :arg str:
    :arg str:
    :ret:
    """

    ## We annotate descriptions and publications separately to mark them as
    ## such.
    for refsrc in ['Description', 'Publication']:
        if refsrc == 'Description':
            text = desc

        elif abstract and refsrc == 'Publication':
            text = abstract

        else:
            continue

        ## ONT_IDS should eventually be changed to a DB call that retrieves a
        ## list of available ontologies instead of hardcoded values
        (mi_annos, ncbo_annos) = annotate_text(text, ONT_IDS)

        ## SQL taken from the curation_server to insert new annotations
        ## Should eventually be moved into geneweaverdb
        mi_sql = '''INSERT INTO
                        extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
                    SELECT %s, ont_id, %s||', MI Annotator'
                    FROM extsrc.ontology
                    WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));'''
        ncbo_sql = '''INSERT INTO
                          extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
                      SELECT %s, ont_id, %s||', NCBO Annotator'
                      FROM extsrc.ontology
                      WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));'''
        black_sql = '''SELECT ont_id
                       FROM extsrc.geneset_ontology
                       WHERE gs_id=%s AND gso_ref_type='Blacklist';'''

        dbcur.execute(black_sql, (gsid,))
        blacklisted = [str(x[0]) for x in dbcur]

        mi_data = (gsid, refsrc, '{'+','.join(mi_annos)+'}', '{'+','.join(blacklisted)+'}')
        ncbo_data = (gsid, refsrc, '{'+','.join(ncbo_annos)+'}', '{'+','.join(blacklisted)+'}')

        dbcur.execute(mi_sql, mi_data)
        dbcur.execute(ncbo_sql, ncbo_data)
        dbcur.connection.commit()

    ## SQL taken from the curation_server
    #mi_sql = '''INSERT INTO
    #              extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
    #            SELECT %s, ont_id, %s||', MI Annotator'
    #            FROM extsrc.ontology
    #            WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));'''

    #ncbo_sql = '''INSERT INTO
    #                extsrc.geneset_ontology (gs_id, ont_id, gso_ref_type)
    #              SELECT %s, ont_id, %s||', NCBO Annotator'
    #              FROM extsrc.ontology
    #              WHERE ont_ref_id=ANY(%s) AND NOT (ont_id=ANY(%s));'''

    #sql_data = (gs_id, refsrc, '{'+','.join(mi_onts)+'}', '{'+','.join(blacklisted)+'}')
    #db_cur.execute(ins_sql_mi,
    #               (gs_id, refsrc, '{'+','.join(mi_onts)+'}', '{'+','.join(blacklisted)+'}'))


