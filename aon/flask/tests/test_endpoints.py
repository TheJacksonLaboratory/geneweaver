"""
Tests every endpoint

Endpoints that return many items are compared to json file in the results directory to
confirm correct output. This can be done by directly comparing the output and the file,
or comparing the IDs of both.

Endpoints that return a couple items or less information are directly compared in a single
assertion.

All endpoints are checked for a '200 OK' status. If the query was unsuccessful, this assertion
will not pass in the first place.
"""
import unittest
import xmlrunner
import json

import sys, os
sys.path.append(os.path.abspath(os.path.join('..', 'src')))

from wsgi import application


# description: opens file from given file path and asserts that the information in the
#     file is the same as the resulting data from the endpoint
# file_path: path to corresponding json file in flask/results directory
# return_value: response_class object storing output from request
# def testExactOutput(file_path, return_value):
#     output = json.loads(return_value.data.decode('utf8'))
#     with open(file_path) as file:
#         expected = json.load(file)
#     assert output == expected
#     assert '200 OK' in return_value.status
#
# # description: tests that each ortholog in the output from the endpoint has an ID
# #     found in the file of expected output
# # file_path: path to corresponding json file in flask/results directory
# # return_value: response_class object storing output from request
# def testOutputIDs(file_path, return_value):
#     output = json.loads(return_value.data.decode('utf8'))
#     with open(file_path) as file:
#         expected = json.load(file)
#         # creates a list of the expected ortholog ids from the json file
#         ids = []
#         for obj in expected:
#             ids.append(obj["id"])
#     # iterates through the returned orthologs to check if the item's id is in the list
#     # of expected ids
#     for obj in output:
#         assert obj["id"] in ids
#     assert '200 OK' in return_value.status

class testEndpoints(unittest.TestCase):

    def setUp(self):
        # initialize logic for test method, is run before each test
        application.app.config['DEBUG'] = True
        application.app.config['TESTING'] = True
        self.app = application.app.test_client()

    def tearDown(self):
        # take down anything we've specifically created for each test method
        self.app = None

    def test_app_root(self):
        rv = self.app.get('/')
        # then expect a 200...
        assert '200 OK' in rv.status

    def test_get_algorithm_by_name(self):
        rv = self.app.get('/agr-service/get_algorithm_by_name/ZFIN')
        # only one algorithm is returned, so the assertion verifies the algorithm id and name
        assert (b'12' in rv.data and b'ZFIN' in rv.data)
        assert '200 OK' in rv.status

    def test_all_algorithms(self):
        rv = self.app.get('/agr-service/all_algorithms')
        assert len(rv.json) == 12

    def test_all_orthologs(self):
        rv = self.app.get('/agr-service/all_orthologs')
        assert len(rv.json) == 560722

    def test_get_orthologs_by_from_gene(self):
        rv = self.app.get('/agr-service/get_orthologs_by_from_gene/ZDB-GENE-040426-960/181874')
        assert len(rv.json) == 6
        assert (rv.json)[0]['ort_id'] == 1335999

    def test_get_orthologs_by_to_gene(self):
        rv = self.app.get('/agr-service/get_orthologs_by_to_gene/S000000004/366222')
        print(rv.json)
        assert len(rv.json) == 32
        assert (rv.json)[0]['ort_id'] == 1310653

    def test_get_ortholog_by_id(self):
        rv = self.app.get('/agr-service/get_ortholog_by_id/1')
        ortholog = rv.json
        # only one ortholog should be returned, the first one, so the ortholog id is checked
        assert ortholog[0]['ort_id'] == 1
        assert '200 OK' in rv.status

    def test_get_orthologs_by_to_and_from_gene(self):
        rv = self.app.get('/agr-service/get_orthologs_by_to_and_from_gene/WBGene00019900/336853/FBgn0260453/254551')
        assert (rv.json)[0]['from_gene'] == 47057 and (rv.json)[0]['to_gene'] == 47074

    def test_get_orthologs_by_from_gene_and_best(self):
        rv = self.app.get('/agr-service/get_orthologs_by_from_gene_and_best/HGNC:3211/78104/T')
        assert len(rv.json) == 7

    def test_get_orthologs_by_from_to_gene_and_best(self):
        rv = self.app.get('/agr-service/get_orthologs_by_from_to_gene_and_best/RGD620664/91714/S000000004/366222/true')
        assert (rv.json)[0]['from_gene'] == 34406 and (rv.json)[0]['to_gene'] == 34387 and (rv.json)[0]['ort_is_best'] == True

    def test_get_orthologs_by_from_to_gene_and_revised(self):
        rv = self.app.get('/agr-service/get_orthologs_by_from_to_gene_and_revised/RGD620664/91714/S000000004/366222/false')
        assert len(rv.json) == 1
        assert (rv.json)[0]['ort_id'] == 1310672

    def test_get_from_gene_of_ortholog_by_id(self):
        rv = self.app.get('/agr-service/get_from_gene_of_ortholog_by_id/1')
        assert (rv.json)['gn_id'] == 1 and (rv.json)['gn_ref_id'] == 'WB:WBGene00011502'

    def test_get_to_gene_of_ortholog_by_id(self):
        rv = self.app.get('/agr-service/get_to_gene_of_ortholog_by_id/112199')
        assert rv.json['gn_id'] == 65603 and rv.json['gn_ref_id'] == 'ZFIN:ZDB-GENE-010309-3'

    def test_all_genes(self):
        rv = self.app.get('/agr-service/all_genes')
        assert len(rv.json) == 100430

    def test_get_genes_by_prefix(self):
        rv = self.app.get('/agr-service/get_genes_by_prefix/MGI')
        assert len(rv.json) == 20670

    def test_get_genes_by_ode_gene_id(self):
        rv = self.app.get('/agr-service/get_genes_by_ode_gene_id/HGNC%3A3211/78104')
        assert rv.json['gn_id'] == 3781 and rv.json['gn_ref_id'] == 'HGNC:3211'

    def test_get_genes_by_species(self):
        rv = self.app.get('/agr-service/get_genes_by_species/Danio%20rerio')
        assert len(rv.json) == 18660

    def test_get_gene_species_name(self):
        rv = self.app.get('/agr-service/get_gene_species_name/FBgn0013275/267529')
        assert (b'Drosophila melanogaster' in rv.data)
        assert '200 OK' in rv.status

    def test_all_species(self):
        rv = self.app.get('/agr-service/all_species')
        assert len(rv.json) == 7

    def test_get_species_by_id(self):
        rv = self.app.get('/agr-service/get_species_by_id/3')
        assert (b'Saccharomyces cerevisiae' in rv.data and b'559292' in rv.data)
        assert '200 OK' in rv.status

    def test_get_orthologs_by_num_algoritms(self):
        rv = self.app.get('/agr-service/get_orthologs_by_num_algoritms/11')
        assert len(rv.json) == 160862

###################################################################################################

    # def test_get_ortholog_by_algorithm(self):
    #     rv = self.app.get('/agr-service/get_ortholog_by_algorithm/HGNC')
    #     print(len(rv.json))

###################################################################################################

    # def test_all_homology(self):
    #     rv = self.app.get('/agr-service/all_homology')
    #     homologs = json.loads(rv.data.decode('utf8'))
    #     print(len(homologs))

    # def test_get_ortholog_by_from_species(self):
    #     rv = self.app.get('/agr-service/get_ortholog_by_from_species/Homo%20sapiens')
    #     testOutputIDs('results/OrthologFromSpecies.json', rv)
    #
    # def test_get_ortholog_by_to_species(self):
    #     rv = self.app.get('/agr-service/get_ortholog_by_to_species/Saccharomyces%20cerevisiae')
    #     testOutputIDs('results/OrthologToSpecies.json', rv)
    #
    # def test_get_ortholog_by_to_and_from_species(self):
    #     rv = self.app.get('/agr-service/get_ortholog_by_to_and_from_species/Danio%20rerio/Mus%20musculus')
    #     testOutputIDs('results/OrthologToFromSpecies.json', rv)
    #
    # def test_get_ortholog_by_to_from_species_and_algorithm(self):
    #     rv = self.app.get('/agr-service/get_ortholog_by_to_from_species_and_algorithm/Saccharomyces%20cerevisiae/Drosophila'
    #                       '%20melanogaster/PANTHER')
    #     testOutputIDs('results/OrthologToFromSpeciesAlgorithm.json', rv)

    # def test_agr_to_geneweaver_species(self):
    #     rv = self.app.get('/agr-service/agr_to_geneweaver_species/2')
    #     assert b'3' in rv.data
    #     assert '200 OK' in rv.status
    #
    # def test_id_convert_agr_to_ode(self):
    #     rv = self.app.get('/agr-service/id_convert_agr_to_ode/34387')
    #     # returns the corresponding ode_gene_id to the agr_gene_id 661
    #     assert b'366222' in rv.data
    #     assert '200 OK' in rv.status
    #
    # def test_id_convert_ode_to_agr(self):
    #     rv = self.app.get('/agr-service/id_convert_ode_to_agr/366222/S000000004')
    #     assert b'34387' in rv.data
    #     assert '200 OK' in rv.status

    # def test_get_ode_gene_by_gdb_id(self):
    #     rv = self.app.get('/agr-service/get_ode_gene_by_gdb_id/13')
    #     with open('results/ODEGeneDbId.json') as file:
    #         expected = json.load(file)
    #         ids = []
    #         for obj in expected:
    #             ids.append(obj["ode_ref_id"])
    #     genes = json.loads(rv.data.decode('utf8'))
    #     for obj in genes:
    #         assert obj["ode_ref_id"] in ids
    #     assert '200 OK' in rv.status
    #
    # def test_get_ode_gene_by_gene_id(self):
    #     rv = self.app.get('/agr-service/get_ode_gene_by_gene_id/96483')
    #     # two genes are returned, so their ode_ref_ids are checked in the following assertion
    #     assert b'LOC100363666' in rv.data and b'RGD2322584' in rv.data
    #     assert '200 OK' in rv.status
    #
    # def test_get_ode_gene_by_species(self):
    #     rv = self.app.get('/agr-service/get_ode_gene_by_species/96602/Rattus%20norvegicus')
    #     # the same two genes from the ODEGeneId endpoint are returned, so their ode_ref_ids are checked
    #     assert b'LOC100363817' in rv.data and b'RGD2322238' in rv.data
    #     assert '200 OK' in rv.status

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='reports/test-application'))