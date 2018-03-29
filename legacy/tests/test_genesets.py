import unittest, json
import geneweaverdb, application
import xmlrunner

'''class for testing the paging on the view geneset details page'''
class TestViewGenesets(unittest.TestCase):
    '''i like denmark'''
    email = "unit.tester@email.dk"
    first = "unitTester"
    last = "user"

    def setUp(self):
        # Create a test user if one does not already exist
        user = geneweaverdb.get_user_byemail(self.email)
        if not user:
            user = geneweaverdb.register_user(self.first, self.last, self.email, "pw")
        self.user_id = user.user_id
        #set up flask test client
        application.app.config['DEBUG'] = True
        application.app.config['TESTING'] = True
        self.app = application.app.test_client()
        #set flask user session
        with self.app.session_transaction() as sess:
            sess['user_id'] = user.user_id
        #create temp geneset and populate it
        self.create_test_geneset()
        self.add_genes_to_geneset()


    def tearDown(self):
        #remove test data
        self.remove_geneset_data()

    def test_get_geneset_genes(self):
        '''test the json response from get_geneset_values'''
        #get a search term
        self.get_search_term_from_geneset()
        ep_root = "/get_geneset_values?gs_id={}".format(self.gs_id)
        ep_test_page = ep_root + '&start=100&gs_len=50'
        ep_search_page = ep_root + '&start=1&gs_len=10' + '&search[value]={}'.format(self.search_term)
        print "testing route {}".format(ep_test_page)
        rqp = self.app.get(ep_test_page)
        self.assertEqual(rqp.status, '200 OK')
        self.assertEqual(self.check_JSON_response(rqp), True)
        print "testing route {}".format(ep_search_page)
        rqs = self.app.get(ep_search_page)
        self.assertEqual(rqs.status, '200 OK')
        json_resp = json.loads(rqs.data)
        print json_resp
        # check we get at least one result
        self.assertGreater(len(json_resp['aaData']), 1)

    def check_JSON_response(self, req):
        '''make sure the length of the main json data is 50 elements long'''
        d = json.loads(req.data)
        if len(d['aaData']) == 50:
            return True
        else:
            return False

    def test_view_geneset_details(self):
        '''testing view geneset details page'''
        #this currently will fail  with a python error the way the temp geneset is getting created
        print "testing view geneset details page for gsid {}".format(self.gs_id)
        ep = "/viewgenesetdetails/{}".format(self.gs_id)
        rq = self.app.get(ep)
        assert '200 OK' in rq.status
        self.assertIn('A GeneSet for Testing Paging', rq.data)

    def test_my_genesets(self):
        '''test that you are logged in and can see your genesets'''
        rq = self.app.get('/mygenesets')
        assert '200 OK' in rq.status
        self.assertIn('My GeneSets', rq.data)

    def add_genes_to_geneset(self):
        '''add a large geneset for testing
        TODO: needs more column data - not sure which one yet.
        this works for testing the paging backend but not for testing
        the frontend of the app - viewgenesetdetails endpoint'''
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''insert into extsrc.geneset_value (gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list, 
                              gsv_value_list, gsv_in_threshold, gsv_date) (select %s, ode_gene_id, 1, 0, ARRAY[ode_ref_id], 
                              ARRAY[1.0], 't', now() from extsrc.gene where ode_pref = 't'
                              and gdb_id = (select gdb_id FROM odestatic.genedb WHERE gdb_name = 'Gene Symbol')
                              and sp_id = (select sp_id FROM production.geneset WHERE gs_id = %s) limit 1000) returning gs_id''',
                              (self.gs_id, self.gs_id))

            cursor.connection.commit()

    def remove_geneset_data(self):
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''delete from extsrc.geneset_value where gs_id = {}'''.format(self.gs_id))
            cursor.execute('''delete from production.geneset where gs_id = {}'''.format(self.gs_id))
            cursor.connection.commit()

    def get_search_term_from_geneset(self):
        '''get a substring to search on from a geneset.
        gets a 3 character string with the most occurrences in the gsv_source_list
        column of the geneset_value table.
        -- this could probably be done with a more elegant query, but it runs pretty quickly'''
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''select substring(cast(gsv_source_list as varchar),2,3) 
                          as search_term from extsrc.geneset_value where gs_id = {}'''.format(self.gs_id))
            search_terms = [row[0] for row in cursor]
            counts = {}
            for search_term in search_terms:
                if search_term not in counts.keys():
                    counts[search_term] = 1
                else:
                    counts[search_term] += 1
            occurences = 0
            term = ""
            for key in counts.keys():
                if counts[key] > occurences:
                    occurences = counts[key]
                    term = key

            self.search_term = term

    def create_test_geneset(self):
        '''creating test geneset
        FYI: this doesn't have the correct data in it
        to work on the viewgenesetdetails page, but it works for
        testing the paging JSON responses'''
        #create a geneset
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation,
                              gs_description, sp_id, gs_count, gs_gene_id_type, gs_created, gs_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                           (self.user_id, 0, 'Testing Geneset Paging', 'TGP', 'A GeneSet for Testing Paging', 1, 0, 0, 'normal',))
            gs_id = cursor.fetchone()[0]
            cursor.connection.commit()
            assert gs_id > 1
            self.gs_id = gs_id

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='reports/test-genesets'))
