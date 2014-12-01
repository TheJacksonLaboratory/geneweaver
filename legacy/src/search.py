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

    #Get all of the selected species options from the form
    speciesList = {'sp0':'no','sp1':'no', 'sp2':'no', 'sp3':'no', 'sp4':'no', 'sp5':'no', 'sp6':'no', 'sp8':'no', 'sp9':'no', 'sp10':'no'}
    if (form.get("sp0")):
        speciesList['sp0'] = 'yes'
    if (form.get("sp1")):
        speciesList['sp1'] = 'yes'
    if (form.get("sp2")):
        speciesList['sp2'] = 'yes'
    if (form.get("sp3")):
        speciesList['sp3'] = 'yes'
    if (form.get("sp4")):
        speciesList['sp4'] = 'yes'
    if (form.get("sp5")):
        speciesList['sp5'] = 'yes'
    if (form.get("sp6")):
        speciesList['sp6'] = 'yes'
    if (form.get("sp8")):
        speciesList['sp8'] = 'yes'
    if (form.get("sp9")):
        speciesList['sp9'] = 'yes'
    if (form.get("sp10")):
        speciesList['sp10'] = 'yes'

    #Get the geneset size limits
    geneCounts = {'geneCountMin': '0', 'geneCountMax': '1000'}
    if(form.get("geneCountMin")):
        geneCounts['geneCountMin'] = form.get("geneCountMin")
    if(form.get("geneCountMax")):
        geneCounts['geneCountMax'] = form.get("geneCountMax")
    #Build the filter list into a dictionary type accepted search
    userFilters={'tierList':tierList, 'speciesList':speciesList, 'geneCounts': geneCounts}
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


def getSearchFilterValues(search_results):
    #Define a results dict used for template display
    #TODO further document the expected use of this structure here
    #
    #Given search results from sphinx, this functions counts how many of each filter type, ie how many tier 1 results there are, for building filter side bar.
    #The partial search_filters_panel.html relies on data from this function. It should be given a searchFilters dictionary that contains filter data discovered here.
    #For each type of filter, count and set filter value, ie count how many of each tier there is, and set that as a filter in the structure
    #First, get a list of all the tiers available and the number of them in the results
    tierCountArray = [0,0,0,0,0,0]
    speciesCountArray = [0,0,0,0,0,0,0,0,0,0,0]
    #Keep track of the largest and smallest gene count
    minGeneCount = 999999
    maxGeneCount = 0
    #Count the number of all tiers
    for match in search_results['matches']:
        #Count the number of each tier type
        tierCountArray[int(match['attrs']['cur_id'])] += 1
        #Count the number of each species type
        speciesCountArray[int(match['attrs']['sp_id'])] += 1
        #Update largest and smalles gs_counts
        if(int(match['attrs']['gs_count']) > maxGeneCount):
            maxGeneCount = int(match['attrs']['gs_count'])
        if(int(match['attrs']['gs_count']) < minGeneCount):
            minGeneCount = int(match['attrs']['gs_count'])
    #Convert the count arrays to a dict
    tierList = {'noTier': tierCountArray[0], 'tier1': tierCountArray[1],'tier2': tierCountArray[2],'tier3': tierCountArray[3],'tier4': tierCountArray[4],'tier5': tierCountArray[5]}
    speciesList = {'sp0':speciesCountArray[0],'sp1':speciesCountArray[1], 'sp2':speciesCountArray[2], 'sp3':speciesCountArray[3], 'sp4':speciesCountArray[4], 'sp5':speciesCountArray[5], 'sp6':speciesCountArray[6], 'sp8':speciesCountArray[8], 'sp9':speciesCountArray[9], 'sp10':speciesCountArray[10]}
    geneCounts = {'geneCountMin': minGeneCount, 'geneCountMax': maxGeneCount}
    #Combine various dictionaries into a single search results dictionary and return
    return {'tierList': tierList, 'speciesList': speciesList, 'geneCounts': geneCounts}

def buildFilterSelectStatementSetFilters(userFilters, client):
    #Given a set of filters established by the user (this is a list of what is selected on the filter side bar) -
    #update the sphinxQL select statement, and set appropriate filters on the Sphinx client
    sphinxSelect = '* '
    #sphinxSelect += ', count(cur_id=1) AS tier1Count'
    #sphinxSelect += ', cur_id IN('+','.join(str(i) for i in list(curationLevelsAllowed))+')'
    #sphinxSelect += ', cur_id AS curationLevel'
    #sphinxSelect+=
    #sphinxSelect += ', (gs) AS publicGeneSets'
    #print sphinxSelect
    client.SetSelect(sphinxSelect)
    #client.SetFilter('isReadable', [1])
    #client.SetFilter('curationLevel', [0,1,2,3,4,5])
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
    if (userFilters['speciesList']['sp0'] == 'yes'):
        speciesIDs.append(0)
    if (userFilters['speciesList']['sp1'] == 'yes'):
        speciesIDs.append(1)
    if (userFilters['speciesList']['sp2'] == 'yes'):
        speciesIDs.append(2)
    if (userFilters['speciesList']['sp3'] == 'yes'):
        speciesIDs.append(3)
    if (userFilters['speciesList']['sp4'] == 'yes'):
        speciesIDs.append(4)
    if (userFilters['speciesList']['sp5'] == 'yes'):
        speciesIDs.append(5)
    if (userFilters['speciesList']['sp6'] == 'yes'):
        speciesIDs.append(6)
    if (userFilters['speciesList']['sp8'] == 'yes'):
        speciesIDs.append(8)
    if (userFilters['speciesList']['sp9'] == 'yes'):
        speciesIDs.append(9)
    if (userFilters['speciesList']['sp10'] == 'yes'):
        speciesIDs.append(10)
    client.SetFilter('sp_id', speciesIDs)
    '''
    Set the filters for geneset size
    '''
    geneCountMin = int(userFilters['geneCounts']['geneCountMin'])
    geneCountMax = int(userFilters['geneCounts']['geneCountMax'])
    client.SetFilterRange('gs_count', geneCountMin, geneCountMax)
    return None

def api_search(search_term, search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid'):
    '''
    The purpose of api search is to do a simple keyword search based on a simple keyword. The results returned are what only guests would see, so there are no tier 5 results returned.
    '''
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    query = '@('+search_fields+') '+search_term
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    client.SetFilter('cur_id', [0,1,2,3,4])
    client.SetLimits(0, 1000, 1000)
    results = client.Query(query)
    if (results == None):
        print client.GetLastError()
    return results

def keyword_paginated_search(search_term, pagination_page, search_fields='name,description,label,genes,pub_authors,pub_title,pub_abstract,pub_journal,ontologies,gs_id,gsid_prefixed,species,taxid', userFilters=None):
    #do a query of the search term, fetch the matching genesets and pagination information
    #search_term - the term to search for
    #pagination_page - the page within the results to go to
    ################################
    client = sphinxapi.SphinxClient()
    client.SetServer(sphinx_server, sphinx_port)
    #Set the limit to get all results within the range of 1000
    #Retrieve only the results within the limit of the current page specified in the pagination option
    resultsPerPage = 25
    offset=resultsPerPage*(pagination_page - 1)
    limit = resultsPerPage
    #Combine the search fields and search term into a Sphinx query
    query = '@('+search_fields+') '+search_term
    #Set the user ID
    userId = -1
    if flask.session.get('user_id'):
        userId = flask.session.get('user_id')
    #Get additional user ID's to determine which private GS's the user can see
    #visibleUsers = getOtherUsersAccessForGroups()
    #Establish filters based on the user, if filters are given
    #Perform the query
    #Important to set the correct match mode
    client.SetMatchMode(sphinxapi.SPH_MATCH_EXTENDED)
    #Also get the results for the full search - this is used for creating filters. To create filters, we need all the results, not just the paginated number of results.
    client.SetLimits(0, 1000, 1000)
    #Set wide filter (select everything filter nothing)
    #client.SetSelect("*")
    #Get the full results used to build filter bar statistics before performing a filtered search
    full_results = client.Query(query)
    #If filters are specified apply filters and perform a filtered search
    if(userFilters):
        buildFilterSelectStatementSetFilters(userFilters, client)
    #Set limits based on pagination
    client.SetLimits(offset, limit, max_matches)
    results = client.Query(query)
    #print results
    #print 'ran all queries'
    #print results
    if (results == None):
        print client.GetLastError()
    #Transform the genesets into geneset objects for Jinga display
    genesets = list()
    #Only get the first page of results
    for match in results['matches']:
        genesetID = match['id']
        genesets.append(geneweaverdb.get_geneset_no_user(genesetID))
    #Calculate pagination information for display
    ##############################
    #Get the number of matches to present
    numResults = int(results['total'])
    #Get the total number of matches
    totalFound = int(results['total_found'])
    #Do ceiling integer division
    numPages = ((numResults - 1) // resultsPerPage) + 1
    currentPage = pagination_page
    #Calculate the bouding numbers for pagination
    end_page_number = currentPage + 4
    if end_page_number > numPages:
        end_page_number = numPages
    paginationValues = {'numResults': numResults,'totalFound':totalFound, 'numPages': numPages, 'currentPage': currentPage, 'resultsPerPage': resultsPerPage, 'search_term': search_term, 'end_page_number': end_page_number};
    #Create filter information to send to the template for use in displaying search_filters_panel.html
    #Get a dictionary representing the search filter values present. Use the full search results to do this.
    searchFilters = getSearchFilterValues(full_results)
    return_values = {'searchresults': results, 'genesets': genesets, 'paginationValues': paginationValues, 'searchFilters': searchFilters}
    #render the page with the genesets
    #print 'finished actually searching'
    return return_values
