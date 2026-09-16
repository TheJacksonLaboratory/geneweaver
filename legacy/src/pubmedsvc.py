import logging
import requests
import xml.etree.ElementTree as ET


logger = logging.getLogger(__name__)

# A GeneWeaver page must not wait indefinitely for an optional NCBI lookup.
# Keep connect failures short and allow enough time for NCBI to return XML.
NCBI_TIMEOUT = (3.05, 10)

# this is a template for a URL that looks like:
# http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=24818216&retmode=xml
PUB_MED_XML_SVC_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={0}&retmode=xml'
# SRP IMPLEMENTATION
SRP_ELINK_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/elink.fcgi?dbfrom=pubmed&db=sra&cmd=neighbor&id=%s'
SRP_EFETCH_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=sra&rettype=acc&id=%s'


def get_pubmed_info(pub_med_id):
    resp = requests.get(PUB_MED_XML_SVC_URL.format(pub_med_id),
                        timeout=NCBI_TIMEOUT)
    resp.raise_for_status()
    root = ET.fromstring(resp.text.encode('utf-8'))

    pubmed_info = dict()

    def add_if_some_val(name, val):
        if val is not None:
            pubmed_info[name] = val

    add_if_some_val('pub_title', root.findtext('.//ArticleTitle'))
    add_if_some_val('pub_abstract', root.findtext('.//AbstractText'))
    add_if_some_val('pub_journal', root.findtext('.//Journal/Title'))
    add_if_some_val('pub_volume', root.findtext('.//Volume'))
    add_if_some_val('pub_pages', root.findtext('.//MedlinePgn'))

    pub_date_node = root.find('.//PubDate')
    if pub_date_node is not None:
        add_if_some_val('pub_year', pub_date_node.findtext('Year'))
        add_if_some_val('pub_month', pub_date_node.findtext('Month'))
        add_if_some_val('pub_day', pub_date_node.findtext('Day'))

    def auth_node_to_str(auth_node):
        name_parts = []

        f_name = auth_node.findtext('ForeName')
        if f_name:
            name_parts.append(f_name)
        else:
            init = auth_node.findtext('Initials')
            if init:
                name_parts.append(init)

        l_name = auth_node.findtext('LastName')
        if l_name:
            name_parts.append(l_name)

        return ' '.join(name_parts)

    author_list_node = root.find('.//AuthorList')
    if author_list_node is not None:
        authors = ', '.join(map(auth_node_to_str, author_list_node.findall('.//Author')))
        if authors:
            try:
                if author_list_node.attrib['CompleteYN'] == 'N':
                    authors += ' et al.'
            except KeyError:
                pass

            pubmed_info['pub_authors'] = authors

    # make sure some required fields are here
    # I've found some pubmed ids don't have this information
    if 'pub_volume' not in pubmed_info:
        pubmed_info['pub_volume'] = None
    if 'pub_pages' not in pubmed_info:
        pubmed_info['pub_pages'] = None

    ## This function should add the pubmed ID to the object as well,
    ## otherwise the batch uploader may fail
    pubmed_info['pub_pubmed'] = pub_med_id

    return pubmed_info

# SRP IMPLEMENTATION
def get_SRP(pub_med_id):
    """Return the linked SRA project, or an empty string when NCBI is unavailable.

    SRP data is optional display metadata.  A timeout, rate limit, malformed
    response, or absent link must not hold a web worker or fail the geneset page.
    """
    try:
        response = requests.get(SRP_ELINK_URL % pub_med_id,
                                timeout=NCBI_TIMEOUT)
        response.raise_for_status()
        response_root = ET.fromstring(response.content)
        link = response_root.find('.//LinkSetDb/Link/Id')
        if link is None or not link.text:
            return ''

        response = requests.get(SRP_EFETCH_URL % link.text,
                                timeout=NCBI_TIMEOUT)
        response.raise_for_status()
        response_root = ET.fromstring(response.content)
        primary_id = response_root.find('.//STUDY/IDENTIFIERS/PRIMARY_ID')
        return primary_id.text if primary_id is not None and primary_id.text else ''
    except (requests.RequestException, ET.ParseError) as exc:
        logger.warning('NCBI SRA lookup failed for PubMed ID %s: %s',
                       pub_med_id, type(exc).__name__)
        return ''
# END SRP IMPLEMENTATION

# run a little test code if this is the main module
if __name__ == '__main__':
    def print_pubmed_info(pubmed_id):
        print('')
        print('=====================================================================================')
        print(pubmed_id)
        print(PUB_MED_XML_SVC_URL.format(pubmed_id))
        for k, v in get_pubmed_info(pubmed_id).items():
            print('-------')
            print(k)
            print(v)

    print_pubmed_info(17172759)
    print_pubmed_info(24818216)
    print_pubmed_info(16214803)
