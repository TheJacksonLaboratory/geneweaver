from collections import defaultdict
import flask
import geneweaverdb
from uploader import Uploader
import sphinxapi
import config

# Sphinx server connection information
# sphinx_server = 'bepo.ecs.baylor.edu'
sphinx_server = config.get('sphinx', 'host')
# sphinx_server = 'localhost'
# sphinx_port = 9312
sphinx_port = config.getInt('sphinx', 'port')
# The number of maximum search results to return (not by page, but in total)
max_matches = 1000
# The total number of genesets to conider in counting results in the filter set on the side bar
max_filter_matches = 5000

# uploader obj to manage database connection
uploader = Uploader()

def search_sphinxql_diagnostic(sphinxQLQuery):
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    return client.Query(sphinxQLQuery)


def getOtherUsersAccessForGroups():
    # This function will return a comma seperated list of user ID's that belong to the groups
    # that the user belongs's to.

    # Filtering for GS view access is done via usr_id from Sphinx. Normally, this would mean that the user
    # can only see GS's they have created.
    # However, a GS may belong to a group that the user is a member of. This implies that either the user,
    # or another member of a group created that GS and is the author (signified by usr_id in GS).
    # So, to determine which additional GS's the user can see, we must determine which GS authors are in
    # groups the user is also in, so that those GS's will be visible to the user (GS's associated with the
    # groups the user is in).

    visibleUsers = []
    if flask.session.get('user_id'):
        groupIds = uploader.get_user_groups(flask.session.get('user_id'))
        print groupIds
        # Convert the group IDS to user ID's
        visibleUsers = set()
        for i in groupIds:
            usersInGroup = uploader.get_group_users(i)
            for j in usersInGroup:
                visibleUsers.add(j)
    return ','.join(str(i) for i in list(visibleUsers))


def getUserFiltersFromApplicationRequest(form):
    # TODO update to handle both post and get with parameters
    # Given a request form object from the application post, pick apart the filters in the request.
    # This is intended to be used in the filtering route that handles an ajax request
    # The return value, a dictionary of filters specified by the user, will be further used by the route function.
    # Build the filter list in a similar manner (dictionary of dictionaries) as search.py getSearchFilterValues defines.
    # Instead of associating filters with count values, use 'yes' or 'no' to indicate if a certain field is checked
    tierList = {'noTier': 'no', 'tier1': 'no', 'tier2': 'no', 'tier3': 'no', 'tier4': 'no', 'tier5': 'no'}
    if (form.get("noTier")):
        tierList['noTier'] = 'yes'

    if (form.get("tier1")):
        tierList['tier1'] = 'yes'

    if (form.get("tier2")):
        tierList['tier2'] = 'yes'

    if (form.get("tier3")):
        tierList['tier3'] = 'yes'

    if (form.get("tier4")):
        tierList['tier4'] = 'yes'

    if (form.get("tier5")):
        tierList['tier5'] = 'yes'

    statusList = {'deprecated': 'no', 'provisional': 'no'}
    if (form.get("deprecated")):
        statusList['deprecated'] = 'yes'
    if (form.get("provisional")):
        statusList['provisional'] = 'yes'

    # Get all of the selected species options from the form
    # First, get the list of speicies and ID's from the database
    speciesListFromDB = uploader.get_speciesTypes()
    speciesList = {}
    # Build the default list
    for sp_id, sp_name in speciesListFromDB.items():
        speciesList['sp' + str(sp_id)] = 'no'
    # Check for form items from user
    for sp_id, sp_name in speciesListFromDB.items():
        if (form.get('sp' + str(sp_id))):
            speciesList['sp' + str(sp_id)] = 'yes'

    # Get all of the selected attribution options from the form
    # First, get the list of attributions and ID's from the database
    attributionListFromDB = uploader.get_attributionTypes()
    attributionsList = {}

    # Build the default list
    for at_id, at_name in attributionListFromDB.items():
        attributionsList['at' + str(at_id)] = 'no'
    # TODO remove after updating database
    attributionsList['at0'] = 'no'
    # Check for form items from user
    for at_id, at_name in attributionListFromDB.items():
        if (form.get('at' + str(at_id))):
            attributionsList['at' + str(at_id)] = 'yes'
    # TODO remove after updating database
    if (form.get('at0')):
        attributionsList['at0'] = 'yes'
    # Get the geneset size limits
    geneCounts = {'geneCountMin': '0', 'geneCountMax': '1000'}
    if (form.get("geneCountMin")):
        geneCounts['geneCountMin'] = form.get("geneCountMin")
    if (form.get("geneCountMax")):
        geneCounts['geneCountMax'] = form.get("geneCountMax")
    # Build the filter list into a dictionary type accepted search
    userFilters = {'statusList': statusList, 'tierList': tierList, 'speciesList': speciesList,
                   'attributionsList': attributionsList, 'geneCounts': geneCounts}
    # Build the search bar data list
    # Search term is given from the searchbar in the form
    search_term = form.get('searchbar')
    # pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    pagination_page = int(form.get('pagination_page'))
    # Build a list of search fields selected by the user (checkboxes) passed in as URL parameters
    # Associate the correct fields with each option given by the user
    field_list = {'searchGenesets': False, 'searchGenes': False, 'searchAbstracts': False, 'searchOntologies': False}
    search_fields = list()
    if (form.get('searchGenesets')):
        search_fields.append('name,description,label')
        field_list['searchGenesets'] = True
    if (form.get('searchGenes')):
        search_fields.append('genes')
        field_list['searchGenes'] = True
    if (form.get('searchAbstracts')):
        search_fields.append('pub_authors,pub_title,pub_abstract,pub_journal')
        field_list['searchAbstracts'] = True
    if (form.get('searchOntologies')):
        search_fields.append('ontologies')
        field_list['searchOntologies'] = True
    # Add the default case, at least be able to search these values for all searches
    search_fields.append('gs_id,gsid_prefixed,species,taxid')
    search_fields = ','.join(search_fields)

    ## Check to see if the user wants to sort search results
    if (form.get('sortBy')):
        sort_by = form.get('sortBy')
    else:
        sort_by = None

    return {'userFilters': userFilters, 'search_term': search_term,
            'pagination_page': pagination_page, 'search_fields': search_fields,
            'field_list': field_list, 'sort_by': sort_by}


def applyUserRestrictions(client, select=''):
    """
    Applies user and group restrictions to a sphinx query so users can't acces
    data that doesn't belong to them. If the select argument is null, the
    function resets the current select query otherwise the access restrictions
    are added to the given select statement.

    :arg client: the current sphinx client
    :type client: Sphinx client object

    :arg select: A select statement to apply restrictions to
    :type select: str
    """

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']

    else:
        user_id = 0

    usr_info = uploader.get_user_info(user_id, out_admin=True)
    is_admin = usr_info == 2 or usr_info == 3
    user_grps = uploader.get_user_groups(user_id)

    # not everyone has a user group
    if not user_grps:
        user_grps = [0]

    if select:
        access = select
    else:
        access = '*'

    # Admins don't get filtered results
    if not is_admin:
        access += ', (usr_id=' + str(user_id)
        access += ' OR IN(grp_id,' + ','.join(str(s) for s in user_grps)
        access += ')) AS isReadable'

        client.SetFilter('isReadable', [1])

    client.SetSelect(access)

def getSearchFilterValues(query):
    """
    Rewrite of getSearchFilterValues because the original wasn't returning the
    proper counts for the sidebar filters. This function more closely matches
    the original PHP code.
    """

    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    client.SetLimits(0, 1000, 1000)

    sphinxSelect = '*'
    sphinxSelect += ', MIN(gs_count) low, MAX(gs_count) high, 0 as OneRow'

    applyUserRestrictions(client, sphinxSelect)
    #client.SetSelect(sphinxSelect)
    client.SetGroupBy('OneRow', sphinxapi.SPH_GROUPBY_ATTR);
    client.AddQuery(query, 'geneset, geneset_delta')

    ## Resets the select and limits
    #client.SetSelect(sphinxSelect)
    applyUserRestrictions(client, sphinxSelect)
    client.SetLimits(0, 1000, 1000)

    client.SetGroupBy('gs_status', sphinxapi.SPH_GROUPBY_ATTR)
    client.AddQuery(query, 'geneset, geneset_delta')
    # client.SetGroupBy('grp_id', sphinxapi.SPH_GROUPBY_ATTR)
    client.SetGroupBy('attribution', sphinxapi.SPH_GROUPBY_ATTR)
    client.AddQuery(query, 'geneset, geneset_delta')

    ## Generates a six digit number representing all combinations of tier,
    ## species, and attributions. Every two characters represent these three
    ## values.
    sphinxSelect += ', (cur_id*10000 + sp_id*100 + attribution) AS tsa_group'

    #client.SetSelect(sphinxSelect)
    applyUserRestrictions(client, sphinxSelect)
    client.SetGroupBy('tsa_group', sphinxapi.SPH_GROUPBY_ATTR)
    client.AddQuery(query, 'geneset, geneset_delta')

    ## srange is the range of geneset sizes
    srange, status, grp, filt = client.RunQueries()

    ## Geneset sizes, min and max
    glow = srange['matches'][0]['attrs']['low']
    ghigh = srange['matches'][0]['attrs']['high']
    geneCounts = {'geneCountMin': glow, 'geneCountMax': ghigh}

    provs = 0
    deps = 0

    ## Status counts: 1 == provisional, 2 == deprecated, 0 = everything else
    for match in status['matches']:
        if match['attrs']['gs_status'] == 1:
            provs = match['attrs']['@count']
        elif match['attrs']['gs_status'] == 2:
            deps = match['attrs']['@count']

    status_counts = {'provisional': provs, 'deprecated': deps}

    tier_counts = defaultdict(int)
    sp_counts = defaultdict(int)
    att_counts = defaultdict(int)

    ## dict of dicts: tier-species, species-tier, att-tier
    ts_counts = defaultdict(lambda: defaultdict(int))
    st_counts = defaultdict(lambda: defaultdict(int))
    at_counts = defaultdict(lambda: defaultdict(int))

    ## triple dicts: tier-species-att, species-tier-att, att-species-tier
    tsa_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    sta_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
    ats_counts = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))

    def chunkList(l, n):
        """
        Splits a list l into n sized pieces.
        """
        if n == 0:
            n = len(l)

        nl = []

        for i in xrange(0, len(l), n):
            nl.append(l[i:i + n])

        return nl

    # now begin the process of converting useless IDs into names
    attrmap = uploader.get_attributionTypes()
    attrmap[0] = 'No Attribution'  ## The function doesn't add No Att. idk why

    for atid, atname in attrmap.items():
        attrmap['at' + str(atid)] = atname
        del attrmap[atid]

    spmap = uploader.get_speciesTypes()
    spmap[0] = 'No Species'

    for spid, spname in spmap.items():
        spmap['sp' + str(spid)] = spname
        del spmap[spid]

    tiermap = {0: 'No Tier', 1: 'I: Resources', 2: 'II: Pro-Curated',
               3: 'III: Curated', 4: 'IV: Provisional', 5: 'V: Private'}

    ## Loops through each match and generates counts for our filters
    for match in filt['matches']:
        keys = str(match['attrs']['@groupby'])

        ## See comment above about the two character codes
        if len(keys) < 6:
            keys = ('0' * (6 - len(keys))) + keys

        keys = chunkList(keys, 2)
        tier = int(keys[0])  ## The tier ID for this match
        spec = int(keys[1])  ## The species for this match
        attr = int(keys[2])  ## The attribution tag for this match
        cnt = match['attrs']['@count']

        ## Convert to the weird string keys, only here b/c otherwise I'd have
        ## to rewrite a shit ton more code :(
        spec = 'sp' + str(spec)
        attr = 'at' + str(attr)

        ## For some reason the DB has two "No Attribution" attributes. The
        ## majority of genesets indicate this with a NULL gs_attribution, while
        ## some others have a reference to the "No Attribution" row in the
        ## attribution table.
        if not attrmap.get(attr, None):
            attr = 'at0'

        # tier = tiermap.get(tier, 'No Tier')
        # spec = spmap.get(spec, 'No Species')
        # attr = attmap.get(attr, 'No Attribution')

        tier_counts[tier] += cnt
        ts_counts[tier][spec] += cnt
        tsa_counts[tier][spec][attr] += cnt

        sp_counts[spec] += cnt
        st_counts[spec][tier] += cnt
        sta_counts[spec][tier][attr] += cnt

        att_counts[attr] += cnt
        at_counts[attr][tier] += cnt
        ats_counts[attr][tier][spec] += cnt

    return {'tier_counts': tier_counts, 'ts_counts': ts_counts, 'tsa_counts':
        tsa_counts, 'sp_counts': sp_counts, 'st_counts': st_counts,
            'sta_counts': sta_counts, 'att_counts': att_counts, 'at_counts':
                at_counts, 'ats_counts': ats_counts, 'status_counts':
                status_counts, 'spmap': spmap, 'attrmap': attrmap, 'tiermap':
                tiermap, 'geneCounts':geneCounts}





'''
Given a set of filters from the user, and a client connection to a sphinx server, this function will set the
appropriate filters to the client connection.
'''


def buildFilterSelectStatementSetFilters(userFilters, client):
    # Given a set of filters established by the user (this is a list of what is selected on the filter side bar) -
    # update the sphinxQL select statement, and set appropriate filters on the Sphinx client
    sphinx_select = '*'

    ## There are some things users shouldn't see...
    applyUserRestrictions(client)

    excludes = []

    ## Filter by provisional/deprecated
    if 'statusList' in userFilters:
        if (userFilters['statusList']['provisional'] != 'yes'):
            excludes.append(1)
        if (userFilters['statusList']['deprecated'] != 'yes'):
            excludes.append(2)
        if excludes:
            client.SetFilter('gs_status', excludes, True)

    '''
    Set the filters for selected Tiers
    
    Build a list of all allowable tier levels, filter the results to match those levels
    '''
    curationLevels = list()

    if 'tierList' in userFilters:
        if (userFilters['tierList']['noTier'] == 'yes'):
            curationLevels.append(0)
        if (userFilters['tierList']['tier1'] == 'yes'):
            curationLevels.append(1)
        if (userFilters['tierList']['tier2'] == 'yes'):
            curationLevels.append(2)
        if (userFilters['tierList']['tier3'] == 'yes'):
            curationLevels.append(3)
        if (userFilters['tierList']['tier4'] == 'yes'):
            curationLevels.append(4)
        if (userFilters['tierList']['tier5'] == 'yes'):
            curationLevels.append(5)

        client.SetFilter('cur_id', curationLevels)
    '''
    Set the filters for the selected species ID's

    Build a list of all allowable species ID's, filter the results to match those species ID's
    '''
    speciesIDs = list()
    # For all species in the user's filter that has 'yes' as a value, add the ID to a list
    speciesListFromDB = uploader.get_speciesTypes()

    if 'speciesList' in userFilters:
        for sp_id, sp_name in speciesListFromDB.items():
            if (userFilters['speciesList']['sp' + str(sp_id)] == 'yes'):
                speciesIDs.append(sp_id)

        client.SetFilter('sp_id', speciesIDs)

    '''
    Set the filters for the selected attribution ID's

    Build a list of all allowable atribution ID's, filter the results to match those attribution ID's
    '''
    attributionIDs = list()
    # For all attributions in the user's filter that has 'yes' as a value, add the ID to a list
    attributionListFromDB = uploader.get_attributionTypes()

    if 'attributionsList' in userFilters:
        for at_id, at_name in attributionListFromDB.items():
            if (userFilters['attributionsList']['at' + str(at_id)] == 'yes'):
                attributionIDs.append(at_id)
        # TODO remove this after updating the DB
        if (userFilters['attributionsList']['at0'] == 'yes'):
            attributionIDs.append(0)
        client.SetFilter('attribution', attributionIDs)

    '''
    Set the filters for geneset size
    '''
    if 'geneCounts' in userFilters:
        geneCountMin = int(userFilters['geneCounts']['geneCountMin'])
        geneCountMax = int(userFilters['geneCounts']['geneCountMax'])
        client.SetFilterRange('gs_count', geneCountMin, geneCountMax)

    return None


#### sortSearchResults
##
#### Sorts the set of search results using user given criteria. Results can be
#### sorted by tier, species, geneset size, or relevance (default). 
##
def sortSearchResults(client, sortby):
    if sortby == 'tier':
        client.SetSortMode(sphinxapi.SPH_SORT_ATTR_ASC, 'cur_id')
    elif sortby == 'species':
        client.SetSortMode(sphinxapi.SPH_SORT_ATTR_ASC, 'common_name')
    elif sortby == 'size':
        client.SetSortMode(sphinxapi.SPH_SORT_ATTR_ASC, 'gs_count')
    else:
        client.SetSortMode(sphinxapi.SPH_SORT_RELEVANCE)


'''
keyword_paginated_search is the main way to do a search. It returns a dict object of search data for use in the search template files
search.html and associated files in templates/search/

 The function is given a search term used to make a query
 a pagination page, which is a page number to into results to display
 a set of search fields understood by sphinx.conf as attributes of which to search. These are built in accordance with the checkboxes under the search bar
 and a dict userFilters, as defined in getUserFiltersFromApplicationRequest which is optional. If supplied, this will limit the search
'''


def keyword_paginated_search(terms, pagination_page,
                             search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid',
                             userFilters={}, sortby=None):
    '''
    Set up initial search connection and build queries
    TODO make this work with multiple query boxes (Will have to do multiple queries and combine results)
    '''
    # Connect to the sphinx indexed search server
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    # Set the number of GS results to fetch per page
    resultsPerPage = 25
    # Calculate the paginated offset into the results to start from
    offset = resultsPerPage * (pagination_page - 1)
    limit = resultsPerPage
    queries = []

    ## For each search term, build them into sphinx queries
    for t in terms:
        query = '@(' + search_fields + ') ' + t
        query = query.replace(' OR ', ' | ')
        query = query.replace(' NOT ', ' -')
        queries.append(query)

    ## The query list converted to space separated strings
    query = ' '.join(queries)

    # query = '@('+search_fields+') '+search_term
    # Set the user ID TODO update this to limit tiers to start, then set filter appropriately
    # userId = -1
    # if flask.session.get('user_id'):
    #    userId = flask.session.get('user_id')



    '''
    We will have to perform three sphinx searches -

    1. The first search will take pagination and applied user filters into account. This will get our actual results
    for a particular page.

    #TODO Implement this search and resulting labels
    2. The second search will count the number of each filter as applied. So, that means that a filtered broad search
    is performed to get the counts of filters as applied, ie, there are 240 tier one out of 50 possible (perhaps a
    species or other filter removed some from the results). This data is used for labeling the
    filter checkbox counts, etc.

    3. The third search is a broad unfiltered search, and is used to get accurate counts of how many of each filter,
    ie species exist, regardless of the filters applied. This data is used for labeling the filter checkbox counts, etc.

    '''

    ## Default sort (sortby = None) uses relevance
    sortSearchResults(client, sortby)

    # Check to see if the user has applied any filters (ie if this is not a search from the home page or initial search)
    # if(userFilters):
    # If there are filters to apply, set the select statement and filters appropiately based on form data
    buildFilterSelectStatementSetFilters(userFilters, client)

    # Set limits based on pagination
    client.SetLimits(offset, limit, max_matches)

    # Run the actual query
    results = client.Query(query)

    # Check if the query had an error
    if (results == None):
        return {'STATUS': 'ERROR'}

    # Transform the genesets into geneset objects for Jinga display
    # This is done by creating a list of genesets from the database.
    # TODO make this use only indexed data???
    genesets = list()
    for match in results['matches']:
        genesetID = match['id']
        genesets.append(geneweaverdb.get_geneset_no_user(genesetID))

    '''
    Calculate pagination information for display
    '''
    numResults = int(results['total'])
    # Get the total number of matches
    totalFound = int(results['total_found'])

    ## No matches
    if totalFound == 0:
        return {'STATUS': 'NO MATCHES'}

    # Do ceiling integer division
    numPages = ((numResults - 1) // resultsPerPage) + 1
    currentPage = pagination_page
    # Calculate the bounding numbers for pagination
    end_page_number = currentPage + 4
    if end_page_number > numPages:
        end_page_number = numPages
    # Create a dict to send to the template for dispay
    paginationValues = {'numResults': numResults, 'totalFound': totalFound,
                        'numPages': numPages, 'currentPage': currentPage, 'resultsPerPage':
                            resultsPerPage, 'search_term': terms, 'end_page_number': end_page_number};
    '''
    Perform the second search that gets the total filter counts for display in search_filters_panel.html
    '''
    # Get a dictionary representing the search filter values present. Use the full search results to do this.
    searchFilters = getSearchFilterValues(query)
    '''
    Get filter label information, ie species names.
    The key name prefix is used so that names are unique for use in html DOM, ie sp0, sp1 ... for species.
    '''
    # Get the species list
    speciesListFromDB = uploader.get_speciesTypes()
    speciesList = {}
    # Associate a key name with a species name
    for sp_id, sp_name in speciesListFromDB.items():
        speciesList['sp' + str(sp_id)] = sp_name
    # Get the attributions list
    attributionsListFromDB = uploader.get_attributionTypes()
    attributionsList = {}
    # Associate a key name with a attribution name
    for at_id, at_name in attributionsListFromDB.items():
        attributionsList['at' + str(at_id)] = at_name
    # TODO update the database to remove this requirement
    # Add an additional item for null or no attribution
    attributionsList['at0'] = 'No Attribution'
    # Create a filter label dict to send to the template for display
    filterLabels = {'speciesList': speciesList, 'attributionsList': attributionsList}
    # Build a set of return values to send to the template for display.
    return_values = {'searchresults': results, 'genesets': genesets, 'paginationValues': paginationValues,
                     'searchFilters': searchFilters, 'filterLabels': filterLabels,
                     # Indicate the status of the search. Since we reached this point in execution, the search was OK.
                     'STATUS': 'OK'}
    return return_values


'''
api_search is a basic way to perform a search that returns a json style representation of the search results. This is
intended for use in the API.

search_term is a term to build a query from
search fields are a set of fields understood by sphinx.conf of which the search should be performed
There are no other filters available for this search. It is intended to be a simple search, although could be expanded
in the future.
'''


def api_search(search_term,
               search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid'):
    '''
    The purpose of api search is to do a simple keyword search based on a simple keyword. The results returned are what only guests would see, so there are no tier 5 results returned.
    '''
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    query = '@(' + search_fields + ') ' + search_term
    # Note that this uses extended syntax http://sphinxsearch.com/docs/current.html#extended-syntax
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    # Only show publically visible genesets
    client.SetFilter('cur_id', [0, 1, 2, 3, 4])
    client.SetLimits(0, 1000, 1000)
    results = client.Query(query)
    if (results == None):
        print client.GetLastError()
    return results
