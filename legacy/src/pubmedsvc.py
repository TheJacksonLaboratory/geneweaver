import requests
import xml.etree.ElementTree as ET

# this is a template for a URL that looks like:
# http://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id=24818216&retmode=xml
PUB_MED_XML_SVC_URL = 'https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi?db=pubmed&id={0}&retmode=xml'


def get_pubmed_info(pub_med_id):
    resp = requests.get(PUB_MED_XML_SVC_URL.format(pub_med_id))
    if resp.status_code == 200:
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

        return pubmed_info
    else:
        raise Exception('unexpected response status code from pubmed service: {0}'.format(resp.status_code))


# run a little test code if this is the main module
if __name__ == '__main__':
    def print_pubmed_info(pubmed_id):
        print ''
        print '====================================================================================='
        print pubmed_id
        print PUB_MED_XML_SVC_URL.format(pubmed_id)
        for k, v in get_pubmed_info(pubmed_id).iteritems():
            print '-------'
            print k
            print v

    print_pubmed_info(17172759)
    print_pubmed_info(24818216)
    print_pubmed_info(16214803)
