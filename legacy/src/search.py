import flask
import geneweaverdb
import sphinxapi

#Sphinx server connection information
sphinx_server = 'bepo.ecs.baylor.edu'
#sphinx_server = 'localhost'
sphinx_port = 9312
#The number of maximum search results to return (not by page, but in total)
max_matches=1000
#The total number of genesets to conider in counting results in the filter set on the side bar
max_filter_matches = 5000

def search_sphinxql_diagnostic(sphinxQLQuery):
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    return client.Query(sphinxQLQuery)

def getOtherUsersAccessForGroups():
    #This function will return a comma seperated list of user ID's that belong to the groups that the user belongs's to.

    #Filtering for GS view access is done via usr_id from Sphinx. Normally, this would mean that the user can only see GS's they have created. 
    #However, a GS may belong to a group that the user is a member of. This implies that either the user, 
    #or another member of a group created that GS and is the author (signified by usr_id in GS). So, to determine which additional GS's the user can see, 
    #we must determine which GS authors are in groups the user is also in, so that those GS's will be visible to the user (GS's associated with the groups the user is in).

    #
    visibleUsers = list()
    if flask.session.get('user_id'):
        groupIds = geneweaverdb.get_user_groups(flask.session.get('user_id'))
        #Convert the group IDS to user ID's
        visibleUsers = set()
        for i in groupIds:
            usersInGroup = geneweaverdb.get_group_users(i)
            for j in usersInGroup:
                visibleUsers.add(j)
    return  ','.join(str(i) for i in list(visibleUsers))

def getUserFiltersFromApplicationRequest(form):
    #TODO update to handle both post and get with parameters
    #Given a request form object from the application post, pick apart the filters in the request. 
    #This is intended to be used in the filtering route that handles an ajax request
    #The return value, a dictionary of filters specified by the user, will be further used by the route function.
    #Build the filter list in a similar manner (dictionary of dictionaries) as search.py getSearchFilterValues defines. 
    #Instead of associating filters with count values, use 'yes' or 'no' to indicate if a certain field is checked
    tierList = {'noTier': 'no', 'tier1': 'no','tier2': 'no','tier3': 'no','tier4': 'no','tier5': 'no'}
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
    if(form.get("deprecated")):
        statusList['deprecated'] = 'yes'
    if(form.get("provisional")):
        statusList['provisional'] = 'yes'

    #Get all of the selected species options from the form
    #First, get the list of speicies and ID's from the database
    speciesListFromDB = geneweaverdb.get_all_species()
    speciesList = {}
    #Build the default list
    for sp_id,sp_name in speciesListFromDB.items():
        speciesList['sp'+str(sp_id)] = 'no'
    #Check for form items from user
    for sp_id,sp_name in speciesListFromDB.items():
        if (form.get('sp'+str(sp_id))):
            speciesList['sp'+str(sp_id)] = 'yes'

    #Get all of the selected attribution options from the form
    #First, get the list of attributions and ID's from the database
    attributionListFromDB = geneweaverdb.get_all_attributions()
    attributionsList = {}

    #Build the default list
    for at_id,at_name in attributionListFromDB.items():
        attributionsList['at'+str(at_id)] = 'no'
    #TODO remove after updating database
    attributionsList['at0'] = 'no'
    #Check for form items from user
    for at_id,at_name in attributionListFromDB.items():
        if (form.get('at'+str(at_id))):
            attributionsList['at'+str(at_id)] = 'yes'
    #TODO remove after updating database
    if (form.get('at0')):
        attributionsList['at0'] = 'yes'
    #Get the geneset size limits
    geneCounts = {'geneCountMin': '0', 'geneCountMax': '1000'}
    if(form.get("geneCountMin")):
        geneCounts['geneCountMin'] = form.get("geneCountMin")
    if(form.get("geneCountMax")):
        geneCounts['geneCountMax'] = form.get("geneCountMax")
    #Build the filter list into a dictionary type accepted search
    userFilters={'statusList':statusList,'tierList':tierList, 'speciesList':speciesList, 'attributionsList': attributionsList, 'geneCounts': geneCounts}
    #Build the search bar data list
    #Search term is given from the searchbar in the form
    search_term = form.get('searchbar')
    #pagination_page is a hidden value that indicates which page of results to go to. Start at page one.
    pagination_page = int(form.get('pagination_page'))
    #Build a list of search fields selected by the user (checkboxes) passed in as URL parameters
    #Associate the correct fields with each option given by the user
    field_list = {'searchGenesets': False, 'searchGenes': False, 'searchAbstracts': False, 'searchOntologies': False}
    search_fields = list()
    if(form.get('searchGenesets')):
        search_fields.append('name,description,label')
        field_list['searchGenesets'] = True
    if(form.get('searchGenes')):
        search_fields.append('genes')
        field_list['searchGenes'] = True
    if(form.get('searchAbstracts')):
        search_fields.append('pub_authors,pub_title,pub_abstract,pub_journal')
        field_list['searchAbstracts'] = True
    if(form.get('searchOntologies')):
        search_fields.append('ontologies')
        field_list['searchOntologies'] = True
    #Add the default case, at least be able to search these values for all searches
    search_fields.append('gs_id,gsid_prefixed,species,taxid')
    search_fields =  ','.join(search_fields)
    return {'userFilters': userFilters, 'search_term': search_term, 'pagination_page': pagination_page, 'search_fields': search_fields, 'field_list': field_list}

'''
Given a sphinx query, this function will return a list of counts of various filters, intended to be displayed as filter
counts, ie how many of each species, in search_filters_panel.html

The function performs a query to a separate sphinx server connection, so it will not have any previously applied user
search filters.
'''
def getSearchFilterValues(query):
    '''
    Create an initial sphinx server connection
    '''
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    client.SetLimits(0, 1000, 1000)
    '''
    Get counts for each filter type
    '''
    #Query for GS min and max gene size counts
    sphinxSelect = '*'
    sphinxSelect += ', MIN(gs_count) low, MAX(gs_count) high, 0 as OneRow'
    client.SetSelect(sphinxSelect)
    client.SetGroupBy('OneRow', sphinxapi.SPH_GROUPBY_ATTR);
    results = client.Query(query)
    if (results == None):
        print client.GetLastError()

    #Retrieve the geneset min and max counts
    if (results['total']>0):
        minGeneCount = int(results['matches'][0]['attrs']['low'])
        maxGeneCount = int(results['matches'][0]['attrs']['high'])
    #Have a default case, in case the search term has no results
    else:
        minGeneCount = 0
        maxGeneCount = 0

    #Query for tier counts
    sphinxSelect = '*'
    client.SetSelect(sphinxSelect)
    client.SetGroupBy('cur_id', sphinxapi.SPH_GROUPBY_ATTR);
    results = client.Query(query)
    if (results == None):
        print client.GetLastError()
    #Retrieve the curation tier ID counts
    tierCountArray = [0,0,0,0,0,0]
    if (results['total']>0):
        for match in results['matches']:
            tierCountArray[int(match['attrs']['cur_id'])] = int(match['attrs']['@count'])

    #Query for species counts
    #First, get the list of speicies and ID's from the database
    speciesListFromDB = geneweaverdb.get_all_species()
    speciesList = {}
    #Build the default list
    for sp_id,sp_name in speciesListFromDB.items():
        speciesList['sp'+str(sp_id)] = 0
    #Perform a sphinx query
    client.SetGroupBy('sp_id', sphinxapi.SPH_GROUPBY_ATTR);
    results = client.Query(query)
    #Count all of the results
    if (results['total']>0):
        for match in results['matches']:
            speciesList['sp'+str(match['attrs']['sp_id'])] = int(match['attrs']['@count'])

    #Query for attribution counts
    #First, get the list of attributions and ID's from the database
    attributionsListFromDB = geneweaverdb.get_all_attributions()
    attributionsList = {}
    #Build the default list
    for at_id, at_name in attributionsListFromDB.items():
        attributionsList['at'+str(at_id)] = 0
    #TODO remove this after updating the database
    attributionsList['at0'] = 0
    #Perform a sphinx query
    client.SetGroupBy('attribution', sphinxapi.SPH_GROUPBY_ATTR);
    results = client.Query(query)
    #Count all of the results
    if (results['total']>0):
        for match in results['matches']:
            attributionsList['at'+str(match['attrs']['attribution'])] = int(match['attrs']['@count'])

    #Query for status counts
    statusCountArray = [0,0,0]
    client.SetGroupBy('gs_status', sphinxapi.SPH_GROUPBY_ATTR);
    results = client.Query(query)
    #Count the results
    if (results['total']>0):
        for match in results['matches']:
            statusCountArray[int(match['attrs']['@groupby'])] = int(match['attrs']['@count'])
    '''
    Create dictionaries with names that search_filters_panel.html understands and return the resulting dictionary
    '''
    statusList = {'provisional': statusCountArray[1], 'deprecated': statusCountArray[2]}
    tierList = {'noTier': tierCountArray[0], 'tier1': tierCountArray[1],'tier2': tierCountArray[2],'tier3': tierCountArray[3],'tier4': tierCountArray[4],'tier5': tierCountArray[5]}
    geneCounts = {'geneCountMin': minGeneCount, 'geneCountMax': maxGeneCount}
    #Combine various dictionaries into a single search results dictionary and return
    return {'statusList': statusList,'tierList': tierList, 'speciesList': speciesList,
            'attributionsList': attributionsList, 'geneCounts': geneCounts}

'''
Given a set of filters from the user, and a client connection to a sphinx server, this function will set the
appropriate filters to the client connection.
'''
def buildFilterSelectStatementSetFilters(userFilters, client):
    #Given a set of filters established by the user (this is a list of what is selected on the filter side bar) -
    #update the sphinxQL select statement, and set appropriate filters on the Sphinx client
    sphinx_select = '*'

    if 'user_id' in flask.session:
        user_id = flask.session['user_id']
    else:
        user_id = 0

    ## User info and groups for geneset access
    user_info = geneweaverdb.get_user(user_id)
    user_grps = geneweaverdb.get_user_groups(user_id)

    ## Empty user group
    if not user_grps:
        user_grps = [0]

    ## Begin applying various filters to the search results
    ## Always filter out genesets the user can't access
    access_filter = '*'

    ## If the user is an administrator, we don't have to do this filtering
    if not user_info.is_admin:
        access_filter += ', (usr_id=' + str(user_id)
        access_filter += ' OR IN(grp_id,' + ','.join(str(s) for s in user_grps)
        access_filter += ')) AS isReadable'

        client.SetSelect(access_filter)
        client.SetFilter('isReadable', [1])

    excludes = []

    ## Filter by provisional/deprecated
    if(userFilters['statusList']['provisional'] != 'yes'):
        excludes.append(1)
    if(userFilters['statusList']['deprecated'] != 'yes'):
        excludes.append(2)
    if excludes:
        client.SetFilter('gs_status', excludes, True)
    
    '''
    Set the filters for selected Tiers
    
    Build a list of all allowable tier levels, filter the results to match those levels
    '''
    curationLevels = list()
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
    #For all species in the user's filter that has 'yes' as a value, add the ID to a list
    speciesListFromDB = geneweaverdb.get_all_species()

    for sp_id,sp_name in speciesListFromDB.items():
        if (userFilters['speciesList']['sp'+str(sp_id)] == 'yes'):
            speciesIDs.append(sp_id)

    client.SetFilter('sp_id', speciesIDs)

    '''
    Set the filters for the selected attribution ID's

    Build a list of all allowable atribution ID's, filter the results to match those attribution ID's
    '''
    attributionIDs = list()
    #For all attributions in the user's filter that has 'yes' as a value, add the ID to a list
    attributionListFromDB = geneweaverdb.get_all_attributions()

    for at_id,at_name in attributionListFromDB.items():
        if (userFilters['attributionsList']['at'+str(at_id)] == 'yes'):
            attributionIDs.append(at_id)
    #TODO remove this after updating the DB
    if(userFilters['attributionsList']['at0'] == 'yes'):
        attributionIDs.append(0)
    client.SetFilter('attribution', attributionIDs)

    '''
    Set the filters for geneset size
    '''
    geneCountMin = int(userFilters['geneCounts']['geneCountMin'])
    geneCountMax = int(userFilters['geneCounts']['geneCountMax'])
    client.SetFilterRange('gs_count', geneCountMin, geneCountMax)
    '''
    Filter by GS Status
    '''

    return None


'''
keyword_paginated_search is the main way to do a search. It returns a dict object of search data for use in the search template files
search.html and associated files in templates/search/

 The function is given a search term used to make a query
 a pagination page, which is a page number to into results to display
 a set of search fields understood by sphinx.conf as attributes of which to search. These are built in accordance with the checkboxes under the search bar
 and a dict userFilters, as defined in getUserFiltersFromApplicationRequest which is optional. If supplied, this will limit the search
'''
def keyword_paginated_search(terms, pagination_page, search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid', userFilters=None):
    '''
    Set up initial search connection and build queries
    TODO make this work with multiple query boxes (Will have to do multiple queries and combine results)
    '''
    #Connect to the sphinx indexed search server
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    #Set the number of GS results to fetch per page
    resultsPerPage = 25
    #Calculate the paginated offset into the results to start from
    offset = resultsPerPage*(pagination_page - 1)
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

    #query = '@('+search_fields+') '+search_term
    #Set the user ID TODO update this to limit tiers to start, then set filter appropriately
    #userId = -1
    #if flask.session.get('user_id'):
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
    #Check to see if the user has applied any filters (ie if this is not a search from the home page or initial search)
    if(userFilters):
        #If there are filters to apply, set the select statement and filters appropiately based on form data
        buildFilterSelectStatementSetFilters(userFilters, client)
    #Set limits based on pagination
    client.SetLimits(offset, limit, max_matches)

    #TODO remove diagnostic query
    print 'debug query: ' + query

    #Run the actual query
    results = client.Query(query)
    #Check if the query had an error
    if (results == None):
        return {'STATUS': 'ERROR'}
    #Transform the genesets into geneset objects for Jinga display
    #This is done by creating a list of genesets from the database.
    #TODO make this use only indexed data???
    genesets = list()
    for match in results['matches']:
        genesetID = match['id']
        genesets.append(geneweaverdb.get_geneset_no_user(genesetID))
    '''
    Calculate pagination information for display
    '''
    numResults = int(results['total'])
    #Get the total number of matches
    totalFound = int(results['total_found'])
    #Do ceiling integer division
    numPages = ((numResults - 1) // resultsPerPage) + 1
    currentPage = pagination_page
    #Calculate the bounding numbers for pagination
    end_page_number = currentPage + 4
    if end_page_number > numPages:
        end_page_number = numPages
    #Create a dict to send to the template for dispay
    paginationValues = {'numResults': numResults,'totalFound':totalFound,
            'numPages': numPages, 'currentPage': currentPage, 'resultsPerPage':
            resultsPerPage, 'search_term': terms, 'end_page_number': end_page_number};
    '''
    Perform the second search that gets the total filter counts for display in search_filters_panel.html
    '''
    #Get a dictionary representing the search filter values present. Use the full search results to do this.
    searchFilters = getSearchFilterValues(query)
    '''
    Get filter label information, ie species names.
    The key name prefix is used so that names are unique for use in html DOM, ie sp0, sp1 ... for species.
    '''
    #Get the species list
    speciesListFromDB = geneweaverdb.get_all_species()
    speciesList = {}
    #Associate a key name with a species name
    for sp_id,sp_name in speciesListFromDB.items():
        speciesList['sp'+str(sp_id)] = sp_name
    #Get the attributions list
    attributionsListFromDB = geneweaverdb.get_all_attributions()
    attributionsList = {}
    #Associate a key name with a attribution name
    for at_id,at_name in attributionsListFromDB.items():
        attributionsList['at'+str(at_id)] = at_name
    #TODO update the database to remove this requirement
    #Add an additional item for null or no attribution
    attributionsList['at0'] = 'No Attribution'
    #Create a filter label dict to send to the template for display
    filterLabels = {'speciesList': speciesList, 'attributionsList': attributionsList}
    #Build a set of return values to send to the template for display.
    return_values = {'searchresults': results, 'genesets': genesets, 'paginationValues': paginationValues,
                     'searchFilters': searchFilters, 'filterLabels': filterLabels,
                     #Indicate the status of the search. Since we reached this point in execution, the search was OK.
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
def api_search(search_term, search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid'):
    '''
    The purpose of api search is to do a simple keyword search based on a simple keyword. The results returned are what only guests would see, so there are no tier 5 results returned.
    '''
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    query = '@('+search_fields+') '+search_term
    #Note that this uses extended syntax http://sphinxsearch.com/docs/current.html#extended-syntax
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    #Only show publically visible genesets
    client.SetFilter('cur_id', [0,1,2,3,4])
    client.SetLimits(0, 1000, 1000)
    results = client.Query(query)
    if (results == None):
        print client.GetLastError()
    return results
