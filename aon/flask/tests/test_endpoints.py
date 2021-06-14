import unittest
import xmlrunner
import json

from src.wsgi import application


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
        rv = self.app.get('/controller/algorithm/ZFIN')
        # only one algorithm is returned, so the assertion verifies the algorithm id and name
        assert (b'12' in rv.data and b'ZFIN' in rv.data)
        assert '200 OK' in rv.status

    def test_AllAlgorithms(self):
        rv = self.app.get('/controller/algorithm')
        with open('tests/results/AllAlgorithms.json') as algoFile:
            expected = json.load(algoFile)
        apiAlgos = json.loads(rv.data.decode('utf8'))
        assert expected == apiAlgos
        assert '200 OK' in rv.status

    def test_OrthoID(self):
        rv = self.app.get('/controller/ortholog/1')
        ortholog = json.loads(rv.data.decode('utf8'))
        assert ortholog[0]["id"] == 1
        assert '200 OK' in rv.status

    def test_OrthoFrom(self):
        rv = self.app.get('/controller/ortholog/from/ZDB-GENE-040426-960/181874')
        with open('tests/results/OrthoFrom.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthoTo(self):
        rv = self.app.get('/controller/ortholog/to/S000000004/366222')
        with open('tests/results/OrthoTo.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthologsAll(self):
        rv = self.app.get('/controller/ortholog')
        with open('tests/results/OrthologsAll.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthoToAndFrom(self):
        rv = self.app.get('/controller/ortholog/to_from/WBGene00019900/336853/FBgn0260453/254551')
        with open('tests/results/OrthoToFrom.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthoBestFrom(self):
        rv = self.app.get('/controller/ortholog/best_and_from/HGNC:3211/78104/T')
        with open('tests/results/OrthoBestFrom.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthoBestFromTo(self):
        rv = self.app.get('/controller/ortholog/best_from_to/RGD620664/91714/S000000004/366222/true')
        with open('tests/results/OrthoBestFromTo.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert expected == orthologs
        assert '200 OK' in rv.status

    def test_OrthoBestRevisedFromTo(self):
        rv = self.app.get('/controller/ortholog/best_revised_from_to/RGD620664/91714/S000000004/366222/false')
        # same results as the OrthoBestFromTo endpoint, so the same file is used to verify results
        with open('tests/results/OrthoBestFromTo.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert expected == orthologs
        assert '200 OK' in rv.status

    def test_OrthoReturnFromGene(self):
        rv = self.app.get('/controller/ortholog/return_from_gene/395')
        # only returns one ortholog object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'34754' in rv.data and b'ZFIN:ZDB-GENE-050522-443' in rv.data)
        assert '200 OK' in rv.status

    def test_OrthoReturnToGene(self):
        rv = self.app.get('/controller/ortholog/return_to_gene/112199')
        # only returns one ortholog object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'75555' in rv.data and b'FB:FBgn0030607' in rv.data)
        assert '200 OK' in rv.status

    def test_Genes(self):
        rv = self.app.get('/controller/gene')
        with open('tests/results/Genes.json') as file:
            expected = json.load(file)
        genes = json.loads(rv.data.decode('utf8'))
        assert genes == expected
        assert '200 OK' in rv.status

    def test_GenePrefix(self):
        rv = self.app.get('/controller/gene/prefix/MGI')
        with open('tests/results/GenePrefix.json') as file:
            expected = json.load(file)
        genes = json.loads(rv.data.decode('utf8'))
        assert expected == genes
        assert '200 OK' in rv.status

    def test_GeneRefID(self):
        rv = self.app.get('/controller/gene/refID/HGNC:3211/78104')
        # only returns one gene object, so the assertion just looks for the agr id and ode_ref_id in the results
        assert (b'34375' in rv.data and b'HGNC:3211' in rv.data)
        assert '200 OK' in rv.status

    def test_GeneSpecies(self):
        rv = self.app.get('/controller/gene/species/Danio%20rerio')
        with open('tests/results/GeneSpecies.json') as file:
            expected = json.load(file)
        genes = json.loads(rv.data.decode('utf8'))
        assert expected == genes
        assert '200 OK' in rv.status

    def test_GeneReturnSpeciesName(self):
        rv = self.app.get('/controller/gene/return_species_name/FBgn0013275/267529')
        # This endpoint only returns the species name of the gene specified
        assert (b'Drosophila melanogaster' in rv.data)
        assert '200 OK' in rv.status

    def test_SpeciesList(self):
        rv = self.app.get('/controller/species')
        with open('tests/results/SpeciesList.json') as file:
            expected = json.load(file)
        species = json.loads(rv.data.decode('utf8'))
        assert expected == species
        assert '200 OK' in rv.status

    def test_SpeciesID(self):
        rv = self.app.get('/controller/species/3')
        # this endpoint returns a Species object, so the species name and taxon id are verified
        assert (b'Saccharomyces cerevisiae' in rv.data and b'559292' in rv.data)
        assert '200 OK' in rv.status

    def test_OrthoNumAlgorithms(self):
        rv = self.app.get('/controller/ortholog/num_algorithms/11')
        with open('tests/results/OrthoNumAlgorithms.json') as file:
            expected = json.load(file)
        orthos = json.loads(rv.data.decode('utf8'))
        assert orthos == expected
        assert '200 OK' in rv.status

    def test_OrthoAlgorithm(self):
        rv = self.app.get('/controller/ortholog_algorithms/ortholog/HGNC')
        with open('tests/results/OrthoAlgorithm.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthologFromSpecies(self):
        rv = self.app.get('/controller/ortholog/from_species/Homo%20sapiens')
        with open('tests/results/OrthologFromSpecies.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthologToSpecies(self):
        rv = self.app.get('/controller/ortholog/to_species/Saccharomyces%20cerevisiae')
        with open('tests/results/OrthologToSpecies.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthologToFromSpecies(self):
        rv = self.app.get('/controller/ortholog/to_and_from_species/Danio%20rerio/Mus%20musculus')
        with open('tests/results/OrthologToFromSpecies.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_OrthologToFromSpeciesAlgorithm(self):
        rv = self.app.get('/controller/ortholog/to_from_species_algo/Saccharomyces%20cerevisiae/Drosophila%20melanogaster/PANTHER')
        with open('tests/results/OrthologToFromSpeciesAlgorithm.json') as file:
            expected = json.load(file)
            ids = []
            for obj in expected:
                ids.append(obj["id"])
        orthologs = json.loads(rv.data.decode('utf8'))
        for obj in orthologs:
            assert obj["id"] in ids
        assert '200 OK' in rv.status

    def test_AGRtoGeneweaverSpecies(self):
        rv = self.app.get('/controller/species/AGRSpecies_to_geneweaverSpecies/2')
        # returns only the species id for the corresponding species in the geneweaver table
        assert b'3' in rv.data
        assert '200 OK' in rv.status

    def test_IDConvertAGRtoODE(self):
        rv = self.app.get('/controller/ode_gene_id/34387')
        # returns the corresponding ode_gene_id to the agr_gene_id 661
        assert b'366222' in rv.data
        assert '200 OK' in rv.status

    def test_IDConvertODEtoAGR(self):
        rv = self.app.get('/controller/agr_gene_id/366222/S000000004')
        # returns only the agr gene id
        assert b'34387' in rv.data
        assert '200 OK' in rv.status

    def test_ODEGeneDbId(self):
        rv = self.app.get('/controller/ode_gene/database/13')
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
        rv = self.app.get('/controller/ode_gene/96483')
        assert b'LOC100363666' in rv.data and b'RGD2322584' in rv.data
        assert '200 OK' in rv.status

    def test_ODEGeneIdBySpecies(self):
        rv = self.app.get('/controller/ode_gene/species/96602/Rattus%20norvegicus')
        assert b'LOC100363817' in rv.data and b'RGD2322238' in rv.data
        assert '200 OK' in rv.status

    def test_HumanToMouse(self):
        rv = self.app.get('/controller/ortholog/human_to_mouse')
        with open('tests/results/HumanToMouse.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status

    def test_MouseToHuman(self):
        rv = self.app.get('/controller/ortholog/mouse_to_human')
        with open('tests/results/MouseToHuman.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status

    def test_MouseHumanAll(self):
        rv = self.app.get('/controller/ortholog/mouse_human_all')
        with open('tests/results/MouseHumanAll.json') as file:
            expected = json.load(file)
        orthologs = json.loads(rv.data.decode('utf8'))
        assert len(expected) == len(orthologs)
        assert '200 OK' in rv.status

if __name__ == '__main__':
    unittest.main(testRunner=xmlrunner.XMLTestRunner(output='reports/test-application'))
