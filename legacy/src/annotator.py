"""
This file contains API wrappers and related functions for annotating user
uploaded genesets. For now, two separate annotation services (NCBO and the
Monarch Initiative) are used since the latter is missing MA annotations.
Separate stand-alone versions of these wrappers can be found, for now,
at bitbucket.org/geneweaver/curation
"""
import json
import os
import traceback
import urllib
from urllib.parse import urlencode
# Upload Fix: Use requests package instead of urrlib
import requests
# END Upload Fix

import geneweaverdb
from time import sleep


# Endpoints and the NCBO API key are read from the environment (with working
# fallbacks) so infra isn't hardcoded and the key can be rotated without a code
# change. Never log API_KEY.
NCBO_URL = os.environ.get('GW_NCBO_URL', 'https://data.bioontology.org')
# No trailing '?': the annotator call passes params=..., which requests encodes
# into the query string.
NCBO_ANNOTATOR = NCBO_URL + '/annotator'

## NCBO API key. If this ever needs to be replaced, register a new account at
## http://bioportal.bioontology.org/accounts/new and set GW_NCBO_API_KEY.
API_KEY = os.environ.get('GW_NCBO_API_KEY', '2709bdd2-c311-4089-b000-56fa3d33307c')

## NCBO docs are kinda shitty but I _think_ ontology IDs it uses are just the
## abbreviations. This seems to work, and nothing else is specified in the
## docs about ontology IDs so...
ONT_IDS = ['MESH', 'GO', 'MP', 'MA']
MONARCH_URL = os.environ.get('GW_MONARCH_URL', 'http://scigraph-ontology.monarchinitiative.org/scigraph')

## Couldn't find this endpoint anywhere in the documentation, but it's buried
## in Monarch's source code. If it changes, you might have to look there.
MONARCH_ANNOTATOR = MONARCH_URL + '/annotations/entities.json'

ANNOTATORS = ['monarch', 'ncbo', 'both', 'none']
# Monarch's SciGraph annotator (scigraph-ontology.monarchinitiative.org) was
# decommissioned (the host no longer resolves), so 'ncbo' is the working
# default. See GWC-8.
DEFAULT_ANNOTATOR = os.environ.get('GW_DEFAULT_ANNOTATOR', 'ncbo')

# NCBO rejects the whole /annotator request (HTTP 404) if the `ontologies`
# parameter contains any acronym it doesn't recognize. GeneWeaver's ontology
# list includes prefixes NCBO lacks (e.g. JAX, ORPHA), so we filter the
# requested set against NCBO's supported acronyms. Cached at module scope to
# avoid re-fetching on every annotation. See GWC-8.
_ncbo_acronyms = None


def describe_request_error(exc, endpoint):
    """Describe a requests failure without leaking the API key.

    ``str(exc)`` on a requests exception embeds the fully prepared URL --
    including ``?apikey=...`` and the annotated text -- so logging the exception
    directly would write the NCBO key (and user content) to pod stdout and
    Cloud Logging. Report only the exception type, the HTTP status when there is
    one, and the bare endpoint, which carries no query string.

    :param exc: the caught exception
    :param endpoint: the endpoint URL *without* a query string
    :returns: a log-safe one-line description
    """
    status = getattr(getattr(exc, 'response', None), 'status_code', None)
    if status is not None:
        return '%s: HTTP %s from %s' % (type(exc).__name__, status, endpoint)
    return '%s from %s' % (type(exc).__name__, endpoint)


def get_ncbo_supported_acronyms():
    """Return the set of ontology acronyms NCBO supports (cached).

    Returns None if the list can't be fetched, in which case callers should
    send the requested set unfiltered rather than block annotation.
    """
    global _ncbo_acronyms
    if _ncbo_acronyms is None:
        try:
            resp = requests.get(NCBO_URL + '/ontologies',
                                params={'apikey': API_KEY}, timeout=30)
            resp.raise_for_status()
            _ncbo_acronyms = {o['acronym'] for o in resp.json() if 'acronym' in o}
        except Exception as e:
            print('Could not fetch NCBO ontology list (%s); '
                  'sending requested ontologies unfiltered'
                  % describe_request_error(e, NCBO_URL + '/ontologies'))
            return None
    return _ncbo_acronyms


def get_geneweaver_ontologies():
    """
    Returns a list of the ontologies currently supported by GeneWeaver.

    :ret list: a list of ontology prefixes supported by GW
    """

    return [d.prefix.upper() for d in geneweaverdb.get_all_ontologydb()]


def fetch_ncbo_annotations(text, ncboids):
    """
    Given a chunk of text and a set of NCBO ontology IDs, this function will
    send the text to NCBO and return a list of annotations for the given
    ontologies.

    :arg str: the text to annotate
    :arg list: list of ontology IDs (abbreviations) to use when annotating
    :ret list: list of annotation IDs
    """

    ## Only ascii!
    text = text.encode('ascii', 'ignore')

    ncboids = list(set(ncboids))
    ncboids = map(str, ncboids)
    # Upload Fix Everest
    # Convert back into a list instead of a map function for enumerate compatibility
    ncboids = list(ncboids)
    # END upload fix

    ## Normalize GeneWeaver ontology prefixes to NCBO acronyms (GW uses 'DO',
    ## NCBO uses 'DOID') and drop any acronym NCBO doesn't recognize -- NCBO
    ## 404s the ENTIRE /annotator request if the ontologies list contains even
    ## one unknown acronym (e.g. GW's JAX, ORPHA). See GWC-8.
    ncboids = ['DOID' if item == 'DO' else item for item in ncboids]
    supported = get_ncbo_supported_acronyms()
    if supported is not None:
        dropped = sorted(item for item in ncboids if item not in supported)
        if dropped:
            print('Dropping NCBO-unsupported ontologies: %s' % dropped)
        ncboids = [item for item in ncboids if item in supported]

    # END UPLOAD FIX

    ncboids = ','.join(ncboids)
    params = {'apikey': API_KEY,
              'format': 'json',
              'ontologies': ncboids,
              'text': text}

    # Added .encode('utf-8')
    # Import re above don't forget to delete if not used
    # params = urlencode(params).encode('utf-8')
    # The ontologies (ncboids) aren't being properly handled when encoded and decoded. Maybe need to use requests package instead of urllib.
    # print(params)
    # End Upload fix

    ## Attempt connecting to NCBO and pulling annotation data. Quits if an
    ## exception is handled three times.
    for _ in range(3):
        try:
            # Must be params= (not data=): for a GET, requests puts `data` in
            # the request body, so NCBO would receive no text/apikey/ontologies
            # and return nothing -> silent annotation failure (GWC-8).
            # timeout so a hung NCBO can't block the upload request indefinitely.
            req = requests.get(NCBO_ANNOTATOR, params=params, timeout=30)
            # requests does NOT raise on non-2xx by itself; without this a 4xx/5xx
            # error body would fall through to json.loads and be mishandled.
            req.raise_for_status()
            res = req.text

        except requests.exceptions.RequestException as e:
            # Covers HTTP errors (via raise_for_status), timeouts and connection
            # errors. requests never raises urllib.error.HTTPError.
            print('Failed to retrieve annotation data from NCBO: %s'
                  % describe_request_error(e, NCBO_ANNOTATOR))
            sleep(1)
            continue

        ## Success
        break

    ## for-else construct: if the loop doesn't break (in our case this
    ## indicates success) then this statement is executed
    else:
        print('Failed to retrieve NCBO annotation data after three attempts')
        return []

    return json.loads(res)


def get_ncbo_link(link):
    """
    Since NCBO enjoys testing the sanity of its users, (almost) every member
    of an object returned by the NCBO API is in the form of a link which then
    requires further API calls to retrieve the data.
    This function calls any API returned link and (hopefully) returns the
    actual data after JSON parsing.

    :arg str: JSON-LD link
    :ret dict: json object representing whatever data we retrieved
    """
    headers = {
        'Authorization': f'apikey token={API_KEY}'
    }

    response = None
    for attempt in range(3):
        try:
            response = requests.get(link, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.HTTPError as e:
            print(f'HTTPError on attempt {attempt + 1}: {e}')
            if response is not None:
                print(f'Response content: {response.content}')  # Log the response content
            sleep(1)
            continue
        except Exception as e:
            print(f'Unknown error on attempt {attempt + 1}: {e}')
            print(traceback.format_exc())  # Print the full traceback for debugging
            sleep(1)
            continue
    else:
        print('Failed to retrieve data from an NCBO URL')
        return None


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
        try:
            link = anno['annotatedClass']['links']['self']
        except TypeError:
            print('NCBO returned an invalid annotation object')
            continue

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

        ## We have to add the 'EDAM_' prefix to all EDAM terms
        if ontid.find('data:') >= 0 or ontid.find('format:') >= 0 or\
           ontid.find('operation:') >= 0 or ontid.find('topic:') >= 0:
            ontid = 'EDAM_' + ontid

        ontids.append(ontid)

    ontids = list(set([s.encode('ascii', 'ignore') for s in ontids]))

    return ontids


def fetch_monarch_annotations(text):
    """
    Sends a chunk of text to Monarch's annotation service and returns a list
    of annotations for several ontologies.

    :arg str: the text to annotate
    :ret list: list of annotation IDs
    """

    ## Only ascii!
    text = text.encode('ascii', 'ignore')

    ## If longestOnly == true, the annotator will always use the longest match
    params = {'content': text, 'longestOnly': 'false'}
    params = urlencode(params)

    ## Attempt connecting pulling annotation data. Quits if an exception
    ## is handled three times.
    for _ in range(3):
        try:
            req = urllib.request.Request(MONARCH_ANNOTATOR + '?' + params)
            res = urllib.request.urlopen(req)
            res = res.read()

        except urllib.error.HTTPError as err:
            print('Failed to retrieve annotation data:')
            print(err)
            continue

        except Exception as err:
            print('Unkown error fetching annotations:')
            print(err)
            continue

        ## Success
        break

    ## for-else construct: if the loop doesn't break (in our case this
    ## indicates success) then this statement is executed
    else:
        print('Failed to retrieve Monarch annotation data after three attempts')
        return []

    return json.loads(res)


def parse_monarch_annotations(annots):
    """
    Given a list of annotation objects retrieved from MI, this function
    parses out and returns ontology IDs.

    :arg list: list of JSON annotation objects returned by MI
    :ret list: list of annotation IDs
    """

    ## Remove a nested level
    annots = [d['token'] for d in annots]

    ontids = [anno['id'] for anno in annots]
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
    pure = list(filter(lambda a: a.split(':')[0].lower() in onts, annots))

    return pure


def annotate_text(text, onts, ncbo=False, monarch=True):
    """
    Annotates a chunk of text to various ontologies using the NCBO and MI
    annotation services.

    :arg str: the text to annotate
    :arg list: ontologies to use during the annotation
    :ret list: annotation IDs
    """

    if ncbo:
        ncbo_onts = fetch_ncbo_annotations(text, onts)
        ncbo_onts = parse_ncbo_annotations(ncbo_onts)
    else:
        ncbo_onts = []

    if monarch:
        mi_onts = fetch_monarch_annotations(text)
        mi_onts = parse_monarch_annotations(mi_onts)
        mi_onts = filter_monarch_annotations(mi_onts, onts)
    else:
        mi_onts = []

    ## Monarch initiative returns MESH annotations as MESH:D1234, while
    ## NCBO and the GW DB just use the unique ID (D1234).
    for i in range(len(mi_onts)):
        if mi_onts[i].find('MESH') != -1:
            mi_onts[i] = mi_onts[i].split(':')[1].strip()

    ## Prevent annotation duplicates
    ncbo_onts = list(set(ncbo_onts) - set(mi_onts))

    return [mi_onts, ncbo_onts]


def insert_annotations(dbcur, gsid, desc, abstract, ncbo=False, monarch=True):
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

        gw_ontologies = get_geneweaver_ontologies()

        ## ONT_IDS should eventually be changed to a DB call that retrieves a
        ## list of available ontologies instead of hardcoded values
        (mi_annos, ncbo_annos) = annotate_text(
            text, gw_ontologies, ncbo=ncbo, monarch=monarch
        )

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

        if monarch:
            mi_data = (gsid, refsrc, '{'+','.join(mi_annos)+'}', '{'+','.join(blacklisted)+'}')
            dbcur.execute(mi_sql, mi_data)
        if ncbo:
            # UPLOAD FIX: The ncbo annotations need to be decoded otherwise they are kept as bytes
            # Not doing so will cause the rest of the script to fail (bytes feed into a .join() method
            ncbo_annos = [ncbo.decode('utf-8') for ncbo in ncbo_annos]
            # UPLOAD FIX END
            ncbo_data = (gsid, refsrc, '{'+','.join(ncbo_annos)+'}', '{'+','.join(blacklisted)+'}')
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


def rerun_annotator(gs_id, publication, description, user_prefs={}):

    annotator_pref = user_prefs.get('annotator', DEFAULT_ANNOTATOR)

    if annotator_pref == 'both':
        ncbo = True
        monarch = True
    elif annotator_pref == 'ncbo':
        ncbo = True
        monarch = False
    elif annotator_pref == 'monarch':
        monarch = True
        ncbo = False
    elif annotator_pref == 'none':
        monarch = False
        ncbo = False

    gw_ontologies = get_geneweaver_ontologies()

    pub_annos = annotate_text(
        publication, gw_ontologies, ncbo=ncbo, monarch=monarch
    )
    desc_annos = annotate_text(
        description, gw_ontologies, ncbo=ncbo, monarch=monarch
    )

    # These are the only annotations we preserve
    assoc_annos =\
        geneweaverdb.get_all_ontologies_by_geneset(gs_id, 'Manual Association')

    # Convert to ont_ids
    for i in range(len(pub_annos)):
        if pub_annos[i]:
            pub_annos[i] = geneweaverdb.get_ontologies_by_refs(pub_annos[i])

    for i in range(len(desc_annos)):
        if desc_annos[i]:
            desc_annos[i] = geneweaverdb.get_ontologies_by_refs(desc_annos[i])

    assoc_annos = map(lambda a: a.ontology_id, assoc_annos)

    geneweaverdb.clear_geneset_ontology(gs_id)

    # There's probably a cleaner way to do this but idk
    for ont_id in assoc_annos:
        geneweaverdb.add_ont_to_geneset(gs_id, ont_id, 'Manual Association')

    for ont_id in pub_annos[0]:
        if ont_id not in assoc_annos:
            geneweaverdb.add_ont_to_geneset(
                gs_id, ont_id, 'Publication, MI Annotator'
            )

    for ont_id in pub_annos[1]:
        if ont_id not in assoc_annos:
            geneweaverdb.add_ont_to_geneset(
                gs_id, ont_id, 'Publication, NCBO Annotator'
            )

    for ont_id in desc_annos[0]:
        if ont_id not in assoc_annos:
            geneweaverdb.add_ont_to_geneset(
                gs_id, ont_id, 'Description, MI Annotator'
            )

    for ont_id in desc_annos[1]:
        if ont_id not in assoc_annos:
            geneweaverdb.add_ont_to_geneset(
                gs_id, ont_id, 'Description, NCBO Annotator'
            )
