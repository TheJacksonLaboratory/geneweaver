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

from src.wsgi import application

# description: opens file from given file path and asserts that the information in the
#     file is the same as the resulting data from the endpoint
# file_path: path to corresponding json file in flask/tests/results directory
# return_value: response_class object storing output from request
def testExactOutput(file_path, return_value):
    output = json.loads(return_value.data.decode('utf8'))
    with open(file_path) as file:
        expected = json.load(file)
    assert output == expected
    assert '200 OK' in return_value.status

# description: tests that each ortholog in the output from the endpoint has an ID
#     found in the file of expected output
# file_path: path to corresponding json file in flask/tests/results directory
# return_value: response_class object storing output from request
def testOutputIDs(file_path, return_value):
    output = json.loads(return_value.data.decode('utf8'))
    with open(file_path) as file:
        expected = json.load(file)
        # creates a list of the expected ortholog ids from the json file
        ids = []
        for obj in expected:
            ids.append(obj["id"])
    # iterates through the returned orthologs to check if the item's id is in the list
    # of expected ids
    for obj in output:
        assert obj["id"] in ids
    assert '200 OK' in return_value.status

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

    def test_AlgorithmByName(self):
        rv = self.app.get('/agr-service/algorithm/ZFIN')
        # only one algorithm is returned, so the assertion verifies the algorithm id and name
        assert (b'12' in rv.data and b'ZFIN' in rv.data)
        assert '200 OK' in rv.status

    def test_AllAlgorithms(self):
        rv = self.app.get('/agr-service/algorithm')
        testExactOutput('tests/results/AllAlgorithms.json', rv)

    def test_OrthologID(self):
        rv = self.app.get('/agr-service/ortholog/1')
        ortholog = json.loads(rv.data.decode('utf8'))
        # only one ortholog should be returned, the first one, so the ortholog id is checked
        assert ortholog[0]["id"] == 1
        assert '200 OK' in rv.status

    def test_OrthologFrom(self):
        rv = self.app.get('/agr-service/ortholog/from/ZDB-GENE-040426-960/181874')
        testOutputIDs('tests/results/OrthologFrom.json', rv)

    def test_OrthologTo(self):
        rv = self.app.get('/agr-service/ortholog/to/S000000004/366222')
        testOutputIDs('tests/results/OrthologTo.json', rv)

    def test_OrthologsAll(self):
        rv = self.app.get('/agr-service/ortholog')
        testOutputIDs('tests/results/OrthologsAll.json', rv)

    def test_OrthologToAndFrom(self):
        rv = self.app.get('/agr-service/ortholog/to_from/WBGene00019900/336853/FBgn0260453/254551')
        testOutputIDs('tests/results/OrthologToAndFrom.json', rv)

    def test_OrthologBestFrom(self):
        rv = self.app.get('/agr-service/ortholog/best_and_from/HGNC:3211/78104/T')
        testOutputIDs('tests/results/OrthologBestFrom.json', rv)

    def test_OrthologBestFromTo(self):
        rv = self.app.get('/agr-service/ortholog/best_from_to/RGD620664/91714/S000000004/366222/true')
        testExactOutput('tests/results/OrthologBestFromTo.json', rv)

    def test_OrthologBestRevisedFromTo(self):
        rv = self.app.get('/agr-service/ortholog/best_revised_from_to/RGD620664/91714/S000000004/366222/false')
        # same results as the OrthoBestFromTo endpoint, so the same file is used to verify results
        testExactOutput('tests/results/OrthologBestFromTo.json', rv)

    def test_OrthologReturnFromGene(self):
        rv = self.app.get('/agr-service/ortholog/return_from_gene/395')
        # only returns one ortholog object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'34754' in rv.data and b'ZFIN:ZDB-GENE-050522-443' in rv.data)
        assert '200 OK' in rv.status

    def test_OrthologReturnToGene(self):
        rv = self.app.get('/agr-service/ortholog/return_to_gene/112199')
        # only returns one ortholog object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'75555' in rv.data and b'FB:FBgn0030607' in rv.data)
        assert '200 OK' in rv.status

    def test_Genes(self):
        rv = self.app.get('/agr-service/gene')
        testExactOutput('tests/results/Genes.json', rv)

    def test_GenePrefix(self):
        rv = self.app.get('/agr-service/gene/prefix/MGI')
        testExactOutput('tests/results/GenePrefix.json', rv)

    def test_GeneRefID(self):
        rv = self.app.get('/agr-service/gene/refID/HGNC:3211/78104')
        # only returns one gene object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'34375' in rv.data and b'HGNC:3211' in rv.data)
        assert '200 OK' in rv.status

    def test_GeneSpecies(self):
        rv = self.app.get('/agr-service/gene/species/Danio%20rerio')
        testExactOutput('tests/results/GeneSpecies.json', rv)

    def test_GeneReturnSpeciesName(self):
        rv = self.app.get('/agr-service/gene/return_species_name/FBgn0013275/267529')
        # This endpoint only returns the species name of the gene specified
        assert (b'Drosophila melanogaster' in rv.data)
        assert '200 OK' in rv.status

    def test_SpeciesList(self):
        rv = self.app.get('/agr-service/species')
        testExactOutput('tests/results/SpeciesList.json', rv)

    def test_SpeciesID(self):
        rv = self.app.get('/agr-service/species/3')
        # this endpoint returns a Species object, so the species name and taxon id are verified
        assert (b'Saccharomyces cerevisiae' in rv.data and b'559292' in rv.data)
        assert '200 OK' in rv.status

    def test_OrthologNumAlgorithms(self):
        rv = self.app.get('/agr-service/ortholog/num_algorithms/11')
        testExactOutput('tests/results/OrthologNumAlgorithms.json', rv)

    def test_OrthologAlgorithm(self):
        rv = self.app.get('/agr-service/ortholog_algorithms/ortholog/HGNC')
        testOutputIDs('tests/results/OrthologAlgorithm.json', rv)

    def test_OrthologFromSpecies(self):
        rv = self.app.get('/agr-service/ortholog/from_species/Homo%20sapiens')
        testOutputIDs('tests/results/OrthologFromSpecies.json', rv)

    def test_OrthologToSpecies(self):
        rv = self.app.get('/agr-service/ortholog/to_species/Saccharomyces%20cerevisiae')
        testOutputIDs('tests/results/OrthologToSpecies.json', rv)

    def test_OrthologToFromSpecies(self):
        rv = self.app.get('/agr-service/ortholog/to_and_from_species/Danio%20rerio/Mus%20musculus')
        testOutputIDs('tests/results/OrthologToFromSpecies.json', rv)

    def test_OrthologToFromSpeciesAlgorithm(self):
        rv = self.app.get('/agr-service/ortholog/to_from_species_algo/Saccharomyces%20cerevisiae/Drosophila'
                          '%20melanogaster/PANTHER')
        testOutputIDs('tests/results/OrthologToFromSpeciesAlgorithm.json', rv)

    def test_AGRtoGeneweaverSpecies(self):
        rv = self.app.get('/agr-service/species/AGRSpecies_to_geneweaverSpecies/2')
        assert b'3' in rv.data
        assert '200 OK' in rv.status

    def test_IDConvertAGRtoODE(self):
        rv = self.app.get('/agr-service/ode_gene_id/34387')
        # returns the corresponding ode_gene_id to the agr_gene_id 661
        assert b'366222' in rv.data
        assert '200 OK' in rv.status

    def test_IDConvertODEtoAGR(self):
        rv = self.app.get('/agr-service/agr_gene_id/366222/S000000004')
        assert b'34387' in rv.data
        assert '200 OK' in rv.status

    def test_ODEGeneDbId(self):
        rv = self.app.get('/agr-service/ode_gene/database/13')
        with open('tests/results/ODEGeneDbId.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["ode_ref_id"])
        genes = json.loads(rv.data.decode('utf8'))
        for obj in genes:
            assert obj["ode_ref_id"] in ids
        assert '200 OK' in rv.status

    def test_ODEGeneId(self):
        rv = self.app.get('/agr-service/ode_gene/96483')
        # two genes are returned, so their ode_ref_ids are checked in the following assertion
        assert b'LOC100363666' in rv.data and b'RGD2322584' in rv.data
        assert '200 OK' in rv.status

    def test_ODEGeneIdBySpecies(self):
        rv = self.app.get('/agr-service/ode_gene/species/96602/Rattus%20norvegicus')
        # the same two genes from the ODEGeneId endpoint are returned, so their ode_ref_ids are checked
        assert b'LOC100363817' in rv.data and b'RGD2322238' in rv.data
        assert '200 OK' in rv.status

    def test_HumanToMouse(self):
        rv = self.app.get('/agr-service/ortholog/human_to_mouse')
        with open('tests/results/HumanToMouse.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        # this assertion checks that both the file and the request return the same number
        # of orthologs
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status

    def test_MouseToHuman(self):
        rv = self.app.get('/agr-service/ortholog/mouse_to_human')
        with open('tests/results/MouseToHuman.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status

    def test_MouseHumanAll(self):
        rv = self.app.get('/agr-service/ortholog/mouse_human_all')
        with open('tests/results/MouseHumanAll.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status


if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='reports/test-application'))