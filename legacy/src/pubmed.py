#!/usr/bin/env python

import requests
import re

__PUBMED_URL = 'http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi'


# This is a modified version of this function from CurationServer
# I think it should be rewritten to use an XML parsing library
def __process_pubmed_response(response):
    articles = []

    for match in re.finditer('<PubmedArticle>(.*?)</PubmedArticle>', response,
                             re.S):
        article_ids = {}

        # article_dict keys match column names in the publications table
        # this way the article_dict can be passed as input to the Publication
        # __init__ function
        article_dict = {}
        article_dict['pub_abstract'] = ''
        fulltext_link = None

        article = match.group(1)
        articleid_matches = re.finditer(
            '<ArticleId IdType="([^"]*)">([^<]*?)</ArticleId>', article, re.S)
        abstract_matches = re.finditer(
            '<AbstractText([^>]*)>([^<]*)</AbstractText>', article, re.S)
        article_dict['pub_title'] = re.search('<ArticleTitle[^>]*>([^<]*)</ArticleTitle>',
                                 article, re.S).group(1).strip()

        # parse the various types of ID out of the response (e.g. pubmed, doi, pii)
        for amatch in articleid_matches:
            article_ids[amatch.group(1).strip()] = amatch.group(2).strip()

        # abstract can be split into multiple tags, join them all together
        for amatch in abstract_matches:
            article_dict['pub_abstract'] += amatch.group(2).strip() + ' '

        # GW publications table does not include a column for a link
        #if 'pmc' in article_ids:
        #    article_dict['fulltext_link'] = 'http://www.ncbi.nlm.nih.gov/pmc/articles/%s/' % (article_ids['pmc'],)
        #elif 'doi' in article_ids:
        #    article_dict['fulltext_link'] = 'http://dx.crossref.org/%s' % (article_ids['doi'],)

        article_dict['pub_pubmed'] = article_ids['pubmed'].strip()

        author_matches = re.finditer('<Author [^>]*>(.*?)</Author>', article,
                                     re.S)
        authors = []
        for match in author_matches:
            name = ''
            try:
                name = re.search('<LastName>([^<]*)</LastName>', match.group(1),
                                 re.S).group(1).strip()
                name = name + ' ' + re.search('<Initials>([^<]*)</Initials>',
                                              match.group(1),
                                              re.S).group(1).strip()
            except:
                pass
            authors.append(name)

        article_dict['pub_authors'] = ', '.join(authors)

        journal = re.search('<Journal[^>]*>(.*?)</Journal>', article,
                            re.S).group(1)
        article_dict['pub_journal'] = re.search('<Title>([^<]*)</Title>',
                                                 journal, re.S).group(1)

        volume = re.search('<Volume>([^<]*)</Volume>', journal, re.S)

        if volume:
            article_dict['pub_volume'] = volume.group(1).strip()
        else:
            article_dict['pub_volume'] = None

        pages = re.search('<MedlinePgn>([^<]*)</MedlinePgn>', article, re.S)

        if pages:
            article_dict['pub_pages'] = pages.group(1).strip()
        else:
            article_dict['pub_pages'] = None

        pubdate = re.search(
            '<PubDate>.*?<Year>([^<]*)</Year>.*?<Month>([^<]*)</Month>',
            article, re.S)

        # year month journal
        tomonthname = {
            '1': 'Jan', '2': 'Feb', '3': 'Mar', '4': 'Apr', '5': 'May',
            '6': 'Jun',
            '7': 'Jul', '8': 'Aug', '9': 'Sep', '10': 'Oct', '11': 'Nov',
            '12': 'Dec'
        }
        pm = pubdate.group(2).strip()
        if pm in tomonthname:
            pm = tomonthname[pm]
        article_dict['pub_month'] = pm
        article_dict['pub_year'] = pubdate.group(1).strip()

        articles.append(article_dict)

    return articles


def get_article_from_pubmed(pubmed_id):

    payload = {
        'db': 'pubmed',
        'id': pubmed_id,
        'retmode': 'xml'
    }

    #TODO GB: do error handling / retry
    response = requests.get(__PUBMED_URL, params=payload)

    articles = __process_pubmed_response(response.text)

    if articles:
        # this function only takes a single pubmed id, but
        # _process_pubmed_response works with multiple and returns a list
        # we will only have one, so just return that article dict
        return articles[0]
    else:
        return None


def main():
    print get_article_from_pubmed("15312160")
    print get_article_from_pubmed("xyz")


if __name__ == '__main__':
    main()
