"""
Definition of our API interface
"""

from flask_restx import Namespace, Resource, fields, abort
from flask import jsonify
# TODO: Import functionality from service.py
from src.service import get_algorithm_by_name, db
from src.models import Algorithm, Ortholog, Gene, Species, OrthologAlgorithms

# Namespaces group API endpoints
# TODO: Fix namespace name and description
NS = Namespace('controller', description='Main functionality of service performed')

# TODO: Replace example code

#PROBLEM ENDPOINT STARTS ON LINE 368

algorithm_model = NS.model('algorithms', {
    'id': fields.Integer(),
    'name': fields.String()
})

ortholog_model = NS.model('orthologs',{
    'id': fields.Integer(),
    'from_gene': fields.Integer(),
    'to_gene': fields.Integer(),
    'is_best': fields.Boolean(),
    'is_best_revised': fields.Boolean(),
    'is_best_adjusted': fields.Boolean(),
    'num_possible_match_algorithms': fields.Integer()
})

gene_model = NS.model('genes',{
    'id': fields.Integer(),
    'reference_id': fields.String(),
    'id_prefix': fields.String(),
    'species': fields.Integer()
})

species_model = NS.model('species',{
    'id': fields.Integer(),
    'name': fields.String(),
    'taxon_id': fields.Integer()
})

ortholog_algorithms_model = NS.model('ortholog_algortihms',{
    'id': fields.Integer(),
    'algorithm_id': fields.Integer(),
    'ortholog_id': fields.Integer()
})

list_model = NS.model('lists',{
    'id': fields.Integer()
})

@NS.route('/algorithm/<algorithm_name>')
class AlgorithmEndpoint(Resource):
    @NS.doc('get algorithm by name')
    @NS.marshal_with(algorithm_model)
    def get(self, algorithm_name):
        result = get_algorithm_by_name(algorithm_name)
        if not result:
            abort(404, message="Could not find algorithm with that name")
        return result

@NS.route('/algorithm')
class AlgorithmsEndpoint(Resource):
    @NS.doc('get all algorithms')
    @NS.marshal_with(algorithm_model)
    def get(self):
        return db.query(Algorithm).all()


@NS.route('/ortholog/best/<best>')
class OrthoBest(Resource):
    @NS.doc('list best')
    @NS.marshal_with(ortholog_model)
    def get(self,best):
        return db.query(Ortholog).filter(Ortholog.is_best==best).all()

@NS.route('/ortholog/from/<int:from_gene_id>')
class OrthoFrom(Resource):
    @NS.doc('from gene')
    @NS.marshal_with(ortholog_model)
    def get(self, from_gene_id):
        result = db.query(Ortholog).filter(Ortholog.from_gene == from_gene_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from_gene")
        return result


@NS.route('/ortholog/to/<int:to_gene_id>')
class OrthoTo(Resource):
    @NS.doc('to gene')
    @NS.marshal_with(ortholog_model)
    def get(self, to_gene_id):
        result = db.query(Ortholog).filter(Ortholog.to_gene==to_gene_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that to_gene")
        return result

@NS.route('/ortholog')
class Orthologs(Resource):
    @NS.doc('return all orthologs')
    @NS.marshal_with(ortholog_model)
    def get(self):
        return db.query(Ortholog).all()

@NS.route('/ortholog/<gene_id>')
class OrthoID(Resource):
    @NS.doc('get ortholog from id')
    @NS.marshal_with(ortholog_model)
    def get(self, gene_id):
        result = db.query(Ortholog).filter(Ortholog.id==gene_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that gene id")
        return result

@NS.route('/ortholog/to_from/<from_id>/<to_id>')
class OrthoToAndFrom(Resource):
    @NS.doc('get ortholog with to and from')
    @NS.marshal_with(ortholog_model)
    def get(self, from_id, to_id):
        result = db.query(Ortholog).filter(Ortholog.from_gene==from_id, Ortholog.to_gene==to_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from and to gene")
        return result

@NS.route('/ortholog/best_and_from/<int:from_id>/<best>')
class OrthoBestFrom(Resource):
    @NS.doc('query best and from_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_id, best):
        best = best.upper()
        if (best=="FALSE" or best=="F"):
            inp = False
        else:
            inp = True
        result = db.query(Ortholog).filter(Ortholog.from_gene==from_id,Ortholog.is_best==inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from gene and is_best value")
        return result

@NS.route('/ortholog/best_from_to/<int:from_id>/<int:to_id>/<best>')
class OrthoBestFromTo(Resource):
    @NS.doc('query best, from_gene, and to_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_id, to_id, best):
        best = best.upper()
        if (best=="FALSE" or best=="F"):
            inp = False
        else:
            inp = True
        result = db.query(Ortholog).filter(Ortholog.from_gene==from_id,
                                           Ortholog.to_gene==to_id,
                                           Ortholog.is_best==inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that "
                               "from_gene, to_gene and is_best value")
        return result

@NS.route('/ortholog/best_revised_from_to/<int:from_id>/<int:to_id>/<best_revised>')
class OrthoBestRevisedFromTo(Resource):
    @NS.doc('query is_best_revised, from_gene, and to_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_id, to_id, best_revised):
        best_revised = best_revised.upper()
        if (best_revised=="FALSE" or best_revised=="F"):
            inp = False
        else:
            inp = True
        result = db.query(Ortholog).filter(Ortholog.from_gene==from_id,
                                           Ortholog.to_gene==to_id,
                                           Ortholog.is_best_revised==inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from_gene,"
                               " to_gene and is_best_revised value")
        return result

@NS.route('/ortholog/num_algorithms/<num>')
class OrthoNumAlgorithms(Resource):
    @NS.doc('number of possible match algorithms')
    @NS.marshal_with(ortholog_model)
    def get(self,num):
        result = db.query(Ortholog).filter(Ortholog.num_possible_match_algorithms==num).all()
        if not result:
            abort(404, message="Could not find any orthologs with that number "
                               "of possible match algorithms")
        return result


@NS.route('/ortholog/all/<from_id>/<to_id>/<best>/<best_revised>/<best_adjusted>/<matches>')
class OrthoAllParameters(Resource):
    @NS.doc('query database with all parameters')
    @NS.marshal_with(ortholog_model)
    def get(self, from_id, to_id, best, best_revised, best_adjusted, matches):
        result = db.query(Ortholog).filter(Ortholog.from_gene==from_id, Ortholog.to_gene==to_id,
                                           Ortholog.is_best==best, Ortholog.is_best_revised==best_revised,
                                           Ortholog.is_best_is_adjusted==best_adjusted,
                                           Ortholog.num_possible_match_algorithms==matches).all()
        if not result:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result

@NS.route('/ortholog/return_from_gene/<id>')
class OrthoReturnFromGene(Resource):
    @NS.doc('return from_gene object')
    @NS.marshal_with(gene_model)
    def get(self, id):
        ortho = db.query(Ortholog).filter(Ortholog.id==id).first()

        result = db.query(Gene).filter(Gene.id==ortho.from_gene).first()
        if not ortho:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result

@NS.route('/ortholog/return_to_gene/<id>')
class OrthoReturnToGene(Resource):
    @NS.doc('return to_gene object')
    @NS.marshal_with(gene_model)
    def get(self, id):
        ortho = db.query(Ortholog).filter(Ortholog.id==id).first()

        result = db.query(Gene).filter(Gene.id==ortho.to_gene).first()
        if not ortho:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result

@NS.route('/gene')
class Genes(Resource):
    @NS.doc('return all genes')
    @NS.marshal_with(gene_model)
    def get(self):
        result = db.query(Gene).all()
        if not result:
            abort(404, message="Could not find any genes")
        return result

@NS.route('/gene/prefix/<prefix>')
class GenePrefix(Resource):
    @NS.doc('query genes with prefix')
    @NS.marshal_with(gene_model)
    def get(self, prefix):
        prefix = prefix.upper()
        result = db.query(Gene).filter(Gene.id_prefix==prefix).all()
        if not result:
            abort(404, message="Could not find any genes with that prefix")
        return result

@NS.route('/gene/refID/<ref>')
class GeneRefID(Resource):
    @NS.doc('query genes with ref_id')
    @NS.marshal_with(gene_model)
    def get(self, ref):
        ref = ref.upper()
        result = db.query(Gene).filter(Gene.reference_id==ref).all()
        if not result:
            abort(404, message="Could not find any genes with that ref_id")
        return result

@NS.route('/gene/species/<sp>')
class GeneSpecies(Resource):
    @NS.doc('query genes with species')
    @NS.marshal_with(gene_model)
    def get(self, sp):
        result = db.query(Gene).filter(Gene.species==sp).all()
        if not result:
            abort(404, message="Could not find any genes with that species")
        return result

@NS.route('/gene/return_species/<ref_id>')
class GeneSpeciesName(Resource):
    @NS.doc('query Gene with ref_id and return species oject')
    @NS.marshal_with(species_model)
    def get(self, ref_id):
        ref_id = ref_id.upper()
        gene = db.query(Gene).filter(Gene.reference_id==ref_id).first()
        result = db.query(Species).filter(Species.id==gene.species).first()
        if not result:
            abort(404, message="Species not found for that reference_id")
        return result

@NS.route('/species')
class SpeciesList(Resource):
    @NS.doc('return all genes')
    @NS.marshal_with(species_model)
    def get(self):
        result = db.query(Species).all()
        if not result:
            abort(404, message="Could not find any species")
        return result

@NS.route('/species/<id>')
class SpeciesID(Resource):
    @NS.doc('query Species with id')
    @NS.marshal_with(species_model)
    def get(self,id):
        return db.query(Species).filter(Species.id==id).all()


#THIS ALSO DOES NOT WORK BECAUSE ORTHOLOGALGORITHM DOES NOT WORK
@NS.route('/ortholog_algorithms/ortholog/<algorithm>')
class OrthoAlgorithmSpecies(Resource):
    @NS.doc('return all orthologs for an algorithm')
    @NS.marshal_with(ortholog_algorithms_model)
    def get(self,algorithm):
        algo_id = (db.query(Algorithm).filter(Algorithm.name==algorithm).first()).id
        ortho_algor = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id==algo_id).all()
        return ortho_algor


@NS.route('/ortholog/from_species/<species_name>')
class OrthologFromSpecies(Resource):
    @NS.doc('return all orthologs from given species')
    @NS.marshal_with(ortholog_model)
    def get(self, species_name):
        species_id = (db.query(Species).filter(Species.name==species_name).first()).id
        genes = db.query(Gene).filter(Gene.species==species_id).all()
        gene_ids = []
        for g in genes:
            gene_ids.append(g.id)
        from_orthos = db.query(Ortholog).filter(Ortholog.from_gene.in_(gene_ids)).all()
        if not from_orthos:
            abort(404, message="Could not find any matching orthologs")
        return from_orthos

@NS.route('/ortholog/to_species/<species_name>')
class OrthologToSpecies(Resource):
    @NS.doc('return all orthologs to a given species')
    @NS.marshal_with(ortholog_model)
    def get(self, species_name):
        species_id = (db.query(Species).filter(Species.name==species_name).first()).id
        genes = db.query(Gene).filter(Gene.species==species_id).all()
        gene_ids = []
        for g in genes:
            gene_ids.append(g.id)
        to_orthos = db.query(Ortholog).filter(Ortholog.to_gene.in_(gene_ids)).all()
        if not to_orthos:
            abort(404, message="Could not find any matching orthologs")
        return to_orthos

@NS.route('/ortholog/to_and_from_species/<to_species>/<from_species>')
class OrthologToFromSpecies(Resource):
    @NS.doc('return all orthologs to and from given species')
    @NS.marshal_with(ortholog_model)
    def get(self, to_species, from_species):
        to_species_id = (db.query(Species).filter(Species.name == to_species).first()).id
        from_species_id = (db.query(Species).filter(Species.name == from_species).first()).id

        to_genes = db.query(Gene).filter(Gene.species==to_species_id).all()
        from_genes = db.query(Gene).filter(Gene.species==from_species_id).all()

        to_gene_ids = []
        from_gene_ids = []

        for g in to_genes:
            to_gene_ids.append(g.id)
        for g in from_genes:
            from_gene_ids.append(g.id)

        orthos = db.query(Ortholog).filter(Ortholog.to_gene.in_(to_gene_ids),
                                           Ortholog.from_gene.in_(from_gene_ids)).all()
        if not orthos:
            abort(404, message="Could not find any matching orthologs")
        return orthos

@NS.route('/ortholog/to_from_species_algo/<to_species>/<from_species>/<algorithm>')
class OrthologToFromSpecies(Resource):
    @NS.doc('return all orthologs to and from given species with specific algorithm')
    @NS.marshal_with(ortholog_model)
    def get(self, to_species, from_species, algorithm):

        to_species_id = (db.query(Species).filter(Species.name == to_species).first()).id
        from_species_id = (db.query(Species).filter(Species.name == from_species).first()).id

        to_genes = db.query(Gene).filter(Gene.species==to_species_id).all()
        from_genes = db.query(Gene).filter(Gene.species==from_species_id).all()

        to_gene_ids = []
        from_gene_ids = []

        for g in to_genes:
            to_gene_ids.append(g.id)
        for g in from_genes:
            from_gene_ids.append(g.id)

        #get algorithm id because user puts in a string for algorithm name
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id

        #this query will not work, attritute error no "algorithm_id"
        orthos_algorithm = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id==algo_id).all()

        #get list of ortholog ids using the algorithm
        ortho_ids = []
        for o in orthos_algorithm:
            ortho_ids.append(o.ortholog_id)

        #filter for Orthologs with from and to genes with given species and orthologs
        #using specified algorithm
        orthos = db.query(Ortholog).filter(Ortholog.to_gene.in_(to_gene_ids),
                                           Ortholog.from_gene.in_(from_gene_ids),
                                           Ortholog.id.in_(ortho_ids) ).all()

        if not orthos:
            abort(404, message="Could not find any matching orthologs")
        return orthos


# Resources
# @NS.route('/')
# class ExampleList(Resource):
#     @NS.doc('list_viewers')
#     @NS.marshal_list_with(example_model)
#     def get(self):
#         return [e for _, e in Examples.items()]
#
#     @NS.doc('create_viewer')
#     @NS.expect(qtlviewer_create_request_model)
#     @NS.marshal_with(qtlviewer_model)
#     def post(self):
#         posted_example = NS.payload
#         # TODO: Act on posted payload
#         return posted_example
#
# @NS.route('/<example_id>')
# class Example(Resource):
#     @NS.doc('get_details_on_viewer')
#     @NS.marshal_with(qtlviewer_model)
#     def get(self, example_id):
#         return EXAMPLES.get(example_id)
# END TODO
