import requests
import xml.etree.ElementTree as ET

# this is a template for a URL that looks like:
# http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=24818216&retmode=xml

def get_gtex_info(gencode_id):
    """ Retrieves GTEx info from GTEx Portal.

    Parameters
    ----------
    gencode_id: GTEx Gene Identifier

    """

    # use 'requests' package to pull info from GTEx
    req = requests.get('http://www.gtexportal.org/home/eqtls/tissue?tissueName=All')

