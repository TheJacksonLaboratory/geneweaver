"""
Definition of our API interface
"""

from flask_restx import Namespace, Resource, fields, abort
from src.service import get_algorithm_by_name, db
from src.models import Algorithm, Ortholog, Gene, Species, OrthologAlgorithms, Geneweaver_Species, Geneweaver_Gene, \
    Geneweaver_GeneDB, Mouse_Human

# Namespaces group API endpoints
# TODO: Fix namespace name and description
NS = Namespace('controller', description='Endpoints to query database')

# MODELS - correspond with models in models.py file
algorithm_model = NS.model('algorithms', {
    'id': fields.Integer(),
    'name': fields.String()
})

ortholog_model = NS.model('orthologs', {
    'id': fields.Integer(),
    'from_gene': fields.Integer(),
    'to_gene': fields.Integer(),
    'is_best': fields.Boolean(),
    'is_best_revised': fields.Boolean(),
    'is_best_adjusted': fields.Boolean(),
    'num_possible_match_algorithms': fields.Integer()
})

gene_model = NS.model('genes', {
    'id': fields.Integer(),
    'reference_id': fields.String(),
    'id_prefix': fields.String(),
    'species': fields.Integer()
})

species_model = NS.model('species', {
    'id': fields.Integer(),
    'name': fields.String(),
    'taxon_id': fields.Integer()
})

ortholog_algorithms_model = NS.model('ortholog_algortihms', {
    'id': fields.Integer(),
    'algorithm_id': fields.Integer(),
    'ortholog_id': fields.Integer()
})

ode_gene_model = NS.model('geneweaver_genes', {
    'ode_gene_id': fields.Integer(),
    'ode_ref_id': fields.String(),
    'gdb_id': fields.Integer(),
    'sp_id': fields.Integer(),
    'ode_pref': fields.Boolean(),
    'ode_date': fields.Date(),
    'old_ode_gene_ids': fields.Integer()
})

mouse_human_model = NS.model('mouse_human_map', {
    'm_id': fields.String(),
    'm_symbol': fields.String(),
    'm_ensembl_id': fields.String(),
    'h_id': fields.String(),
    'h_symbol': fields.String(),
    'h_ensembl_id': fields.String(),
    'is_mouse_to_human': fields.Boolean()
})


# CONVERTER FUNCTIONS
# these functions convert between ODE gene ids and the gene ids used within the AGR database

# ode_ref_id and ode_gene_id must be used whenever referencing a gene from the geneweaver database because
# both are used as the primary key for the gene table
def convertODEtoAGR(ode_ref, ode_id):
    ode_gene = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_ref_id == ode_ref,
                                                Geneweaver_Gene.ode_gene_id == ode_id).first()
    genedb_id = ode_gene.gdb_id
    prefix = (db.query(Geneweaver_GeneDB).filter(Geneweaver_GeneDB.gdb_id == genedb_id).first()).gdb_name
    ref = ode_gene.ode_ref_id
    # convert the ref_ids into how the agr ref ids are stored
    if prefix == "Wormbase":
        prefix = "WB"
        ref = prefix + ":" + ref
    if prefix == "FlyBase":
        prefix = "FB"
        ref = prefix + ":" + ref
    if prefix == "SGD" or prefix == "ZFIN":
        ref = prefix + ":" + ref
    if prefix == "RGD":
        ref = ref[:3] + ":" + ref[3:]

    agr = db.query(Gene).filter(Gene.reference_id == ref).first()
    return agr


def convertAGRtoODE(agr_gene_id):
    agr_gene = db.query(Gene).filter(Gene.id == agr_gene_id).first()
    ref = agr_gene.reference_id
    prefix = agr_gene.id_prefix
    # convert the ref ids into the format they are stored in the geneweaver gene table
    if prefix == "RGD":
        ref = ref.replace(":", "")
    elif prefix == "WB" or prefix == "FB" or prefix == "SGD" or prefix == "ZFIN":
        ind = ref.find(":") + 1
        ref = ref[ind:]
    ode_id = (db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_ref_id == ref).first()).ode_gene_id
    return ode_id


# algorithm Table Endpoints
@NS.route('/algorithm/<algorithm_name>')
class AlgorithmByName(Resource):
    @NS.doc('get algorithm object sorted by name')
    @NS.marshal_with(algorithm_model)
    def get(self, algorithm_name):
        result = get_algorithm_by_name(algorithm_name)
        if not result:
            abort(404, message="Could not find algorithm with that name")
        return result


@NS.route('/algorithm')
class AllAlgorithms(Resource):
    @NS.doc('returns all algorithms')
    @NS.marshal_with(algorithm_model)
    def get(self):
        return db.query(Algorithm).all()


# ortholog Table Endpoints
@NS.route('/ortholog/from/<ode_ref_id>/<ode_id>')
class OrthoFrom(Resource):
    @NS.doc('returns orthologs that are from the ode_ref_id')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from_gene")
        return result


@NS.route('/ortholog/to/<ode_ref_id>/<ode_id>')
class OrthoTo(Resource):
    @NS.doc('returns orthologs that are to the ode_ref_id')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.to_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that to_gene")
        return result


@NS.route('/ortholog')
class OrthologsAll(Resource):
    @NS.doc('return all orthologs')
    @NS.marshal_with(ortholog_model)
    def get(self):
        return db.query(Ortholog).all()


@NS.route('/ortholog/<ortho_id>')
class OrthoID(Resource):
    @NS.doc('get ortholog from id')
    @NS.marshal_with(ortholog_model)
    def get(self, ortho_id):
        result = db.query(Ortholog).filter(Ortholog.id == ortho_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that gene id")
        return result


@NS.route('/ortholog/to_from/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>')
class OrthoToAndFrom(Resource):
    @NS.doc('get ortholog with to gene and from gene using ode_ref_id')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, to_ode_ref_id, to_ode_id):
        from_gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        to_gene = convertODEtoAGR(to_ode_ref_id, to_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == from_gene.id,
                                           Ortholog.to_gene == to_gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from and to gene")
        return result


@NS.route('/ortholog/best_and_from/<from_ode_ref_id>/<from_ode_id>/<best>')
class OrthoBestFrom(Resource):
    @NS.doc('query best and from_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, best):
        best = best.upper()
        # best variable is a string, convert to bool to query the is_best column
        if best == "FALSE" or best == "F":
            inp = False
        else:
            inp = True
        gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == gene.id,
                                           Ortholog.is_best == inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from gene and is_best value")
        return result


@NS.route('/ortholog/best_from_to/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best>')
class OrthoBestFromTo(Resource):
    @NS.doc('query best, from_gene, and to_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, to_ode_ref_id, to_ode_id, best):
        best = best.upper()
        # best variable is a string, convert to bool to query the is_best column
        if best == "FALSE" or best == "F":
            inp = False
        else:
            inp = True
        from_gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        to_gene = convertODEtoAGR(to_ode_ref_id, to_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == from_gene.id,
                                           Ortholog.to_gene == to_gene.id,
                                           Ortholog.is_best == inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that "
                               "from_gene, to_gene and is_best value")
        return result


@NS.route('/ortholog/best_revised_from_to/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best_revised>')
class OrthoBestRevisedFromTo(Resource):
    @NS.doc('query is_best_revised, from_gene, and to_gene columns')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, to_ode_ref_id, to_ode_id, best_revised):
        best_revised = best_revised.upper()
        if best_revised == "FALSE" or best_revised == "F":
            inp = False
        else:
            inp = True
        from_gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        to_gene = convertODEtoAGR(to_ode_ref_id, to_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == from_gene.id,
                                           Ortholog.to_gene == to_gene.id,
                                           Ortholog.is_best_revised == inp).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from_gene,"
                               " to_gene and is_best_revised value")
        return result


@NS.route('/ortholog/return_from_gene/<ortho_id>')
class OrthoReturnFromGene(Resource):
    @NS.doc('return from_gene object of a ortholog')
    @NS.marshal_with(gene_model)
    def get(self, ortho_id):
        ortho = db.query(Ortholog).filter(Ortholog.id == ortho_id).first()
        result = db.query(Gene).filter(Gene.id == ortho.from_gene).first()
        if not ortho:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result


@NS.route('/ortholog/return_to_gene/<ortho_id>')
class OrthoReturnToGene(Resource):
    @NS.doc('return to_gene object of a specific ortholog')
    @NS.marshal_with(gene_model)
    def get(self, ortho_id):
        ortho = db.query(Ortholog).filter(Ortholog.id == ortho_id).first()
        result = db.query(Gene).filter(Gene.id == ortho.to_gene).first()
        if not ortho:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result


# gene Table Endpoints
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
    @NS.doc('query genes by prefix')
    @NS.marshal_with(gene_model)
    def get(self, prefix):
        prefix = prefix.upper()
        result = db.query(Gene).filter(Gene.id_prefix == prefix).all()
        if not result:
            abort(404, message="Could not find any genes with that prefix")
        return result


@NS.route('/gene/refID/<ode_ref_id>/<ode_id>')
class GeneRefID(Resource):
    @NS.doc('query genes by ode_ref_id')
    @NS.marshal_with(gene_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        if not gene:
            abort(404, message="Could not find any genes with that ref_id")
        return gene


@NS.route('/gene/species/<species_name>')
class GeneSpecies(Resource):
    @NS.doc('returns ode_gene_ids for genes of a certain species')
    @NS.marshal_with(gene_model)
    def get(self, species_name):
        sp = db.query(Species).filter(Species.name == species_name).first()
        genes = db.query(Gene).filter(Gene.species == sp.id).all()
        if not genes:
            abort(404, message="Could not find any genes with that species")
        return genes


@NS.route('/gene/return_species_name/<ode_ref_id>/<ode_id>')
class GeneReturnSpeciesName(Resource):
    @NS.doc('returns the species of a gene from the ode_ref_id')
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Species).filter(Species.id == gene.species).first()
        if not result:
            abort(404, message="Species not found for that reference_id")
        return result.name


# species Table Endpoints
@NS.route('/species')
class SpeciesList(Resource):
    @NS.doc('return all species')
    @NS.marshal_with(species_model)
    def get(self):
        result = db.query(Species).all()
        if not result:
            abort(404, message="Could not find any species")
        return result


@NS.route('/species/<s_id>')
class SpeciesID(Resource):
    @NS.doc('query Species with species id')
    @NS.marshal_with(species_model)
    def get(self, s_id):
        return db.query(Species).filter(Species.id == s_id).all()


# ortholog_algorithms Table Endpoints
@NS.route('/ortholog/num_algorithms/<num>')
class OrthoNumAlgorithms(Resource):
    @NS.doc('filter ortholog table by number of possible match algorithms')
    @NS.marshal_with(ortholog_model)
    def get(self, num):
        result = db.query(Ortholog).filter(Ortholog.num_possible_match_algorithms == num).all()
        if not result:
            abort(404, message="Could not find any orthologs with that number "
                               "of possible match algorithms")
        return result


@NS.route('/ortholog_algorithms/ortholog/<algorithm>')
class OrthoAlgorithm(Resource):
    @NS.doc('return all orthologs for an algorithm')
    @NS.marshal_with(ortholog_algorithms_model)
    def get(self, algorithm):
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id
        ortho_algor = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id == algo_id).all()
        return ortho_algor


@NS.route('/ortholog/from_species/<species_name>')
class OrthologFromSpecies(Resource):
    @NS.doc('return all orthologs from given species')
    @NS.marshal_with(ortholog_model)
    def get(self, species_name):
        species_id = (db.query(Species).filter(Species.name == species_name).first()).id
        genes = db.query(Gene).filter(Gene.species == species_id).all()
        gene_ids = []
        for g in genes:
            gene_ids.append(g.id)
        from_orthos = db.query(Ortholog).filter(Ortholog.from_gene.in_(gene_ids)).all()
        if not from_orthos:
            abort(404, message="Could not find any matching orthologs")
        return from_orthos


# ORTHOLOG AND SPECIES TABLES
@NS.route('/ortholog/to_species/<species_name>')
class OrthologToSpecies(Resource):
    @NS.doc('return all orthologs to a given species')
    @NS.marshal_with(ortholog_model)
    def get(self, species_name):
        species_id = (db.query(Species).filter(Species.name == species_name).first()).id
        genes = db.query(Gene).filter(Gene.species == species_id).all()
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

        to_genes = db.query(Gene).filter(Gene.species == to_species_id).all()
        from_genes = db.query(Gene).filter(Gene.species == from_species_id).all()

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
class OrthologToFromSpeciesAlgorithm(Resource):
    @NS.doc('return all orthologs to and from given species with specific algorithm')
    @NS.marshal_with(ortholog_model)
    def get(self, to_species, from_species, algorithm):

        to_species_id = (db.query(Species).filter(Species.name == to_species).first()).id
        from_species_id = (db.query(Species).filter(Species.name == from_species).first()).id

        to_genes = db.query(Gene).filter(Gene.species == to_species_id).all()
        from_genes = db.query(Gene).filter(Gene.species == from_species_id).all()

        to_gene_ids = []
        from_gene_ids = []

        for g in to_genes:
            to_gene_ids.append(g.id)
        for g in from_genes:
            from_gene_ids.append(g.id)

        # get algorithm id because user puts in a string for algorithm name
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id

        # this query will not work, attritute error no "algorithm_id"
        orthos_algorithm = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id == algo_id).all()

        # get list of ortholog ids using the algorithm
        ortho_ids = []
        for o in orthos_algorithm:
            ortho_ids.append(o.ortholog_id)

        # filter for Orthologs with from and to genes with given species and orthologs
        # using specified algorithm
        orthos = db.query(Ortholog).filter(Ortholog.to_gene.in_(to_gene_ids),
                                           Ortholog.from_gene.in_(from_gene_ids),
                                           Ortholog.id.in_(ortho_ids)).all()

        if not orthos:
            abort(404, message="Could not find any matching orthologs")
        return orthos


# AGR and Geneweaver Database Endpoints
# The following endpoints allow for connections to be made between the agr database and the geneweweaver database
#    by linking the species table and gene ids
@NS.route('/species/AGRSpecies_to_geneweaverSpecies/<species_id>')
class AGRtoGeneweaverSpecies(Resource):
    @NS.doc('translate an AGR species id to the species id in the geneweaver database')
    def get(self, species_id):
        agr_name = (db.query(Species).filter(Species.id == species_id).first()).name
        geneweaver_id = (db.query(Geneweaver_Species).filter(Geneweaver_Species.sp_name == agr_name).first()).sp_id
        if not geneweaver_id:
            abort(404, message="No matching species_id in the Geneweaver Species Table")
        return geneweaver_id


@NS.route('/ode_gene_id/<agr_gene_id>')
class IDCovertAGRtoODE(Resource):
    @NS.doc('converts an agr gene id to the corresponding ode_gene_ide')
    def get(self, agr_gene_id):
        agr_gene = db.query(Gene).filter(Gene.id == agr_gene_id).first()
        ref = agr_gene.reference_id
        prefix = agr_gene.id_prefix
        if prefix == "RGD":
            ref = ref.replace(":", "")
        elif prefix == "WB" or prefix == "FB" or prefix == "SGD" or prefix == "ZFIN":
            ind = ref.find(":") + 1
            ref = ref[ind:]
        ode_id = (db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_ref_id == ref).first()).ode_gene_id
        if not ode_id:
            abort(404, message="mathcing ode_gene_id not found")
        return ode_id


@NS.route('/agr_gene_id/<ode_gene_id>/<ode_ref_id>')
class IDConvertODEtoAGR(Resource):
    @NS.doc('converts an ode gene id to the corresponding agr gene id')
    def get(self, ode_gene_id, ode_ref_id):
        ode_gene = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id,
                                                    Geneweaver_Gene.ode_ref_id == ode_ref_id).first()
        genedb_id = ode_gene.gdb_id
        prefix = (db.query(Geneweaver_GeneDB).filter(Geneweaver_GeneDB.gdb_id == genedb_id).first()).gdb_name
        ref = ode_gene.ode_ref_id
        if prefix == "Wormbase":
            prefix = "WB"
            ref = prefix + ":" + ref
        if prefix == "FlyBase":
            prefix = "FB"
            ref = prefix + ":" + ref
        if prefix == "SGD" or prefix == "ZFIN":
            ref = prefix + ":" + ref
        if prefix == "RGD":
            ref = ref[:3] + ":" + ref[3:]
        agr_id = (db.query(Gene).filter(Gene.reference_id == ref).first()).id
        if not agr_id:
            abort(404, message="No matching agr gene found")
        return agr_id


@NS.route('/ode_gene/database/<gdb_id>')
class ODEGeneDbId(Resource):
    @NS.doc('return all ode_genes with the specified gdb_id')
    @NS.marshal_with(ode_gene_model)
    def get(self, gdb_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.gdb_id == gdb_id).all()
        if not genes:
            abort(404, message="No genes were found with specified gdb_id")
        return genes


@NS.route('/ode_gene/<ode_gene_id>')
class ODEGeneId(Resource):
    @NS.doc('return all ode_genes with the same ode_gene_id')
    @NS.marshal_with(ode_gene_model)
    def get(self, ode_gene_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id).all()
        if not genes:
            abort(404, message="No genes were found matching that ode_gene_id")
        return genes


@NS.route('/ode_gene/species/<ode_gene_id>/<species_name>')
class ODEGeneIdBySpecies(Resource):
    @NS.doc('return all genes with matching ode_gene_id and species')
    @NS.marshal_with(ode_gene_model)
    def get(self, ode_gene_id, species_name):
        sp_id = (db.query(Geneweaver_Species).filter(Geneweaver_Species.sp_name == species_name).first()).sp_id
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id,
                                                 Geneweaver_Gene.sp_id == sp_id).all()
        if not genes:
            abort(404, message="No genes were found matching that ode_gene_id and species")
        return genes


# Mouse Human Mapping
# The following endpoints map from mouse to humand and from human to mouse while also returning
# the corresponding Ensembl ID

@NS.route('/ortholog/human_to_mouse')
class HumanToMouse(Resource):
    @NS.doc('returns all orthologs from human to mouse with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).filter(Mouse_Human.is_mouse_to_human == False).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs


@NS.route('/ortholog/mouse_to_human')
class MouseToHuman(Resource):
    @NS.doc('returns all orthologs from human to mouse with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).filter(Mouse_Human.is_mouse_to_human == True).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs


@NS.route('/ortholog/mouse_human_all')
class MouseHumanAll(Resource):
    @NS.doc('returns all orthologs containing human and mouse with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs
