"""
Definition of our API interface - Endpoints query the AGR database
"""

from flask_restx import Namespace, Resource, fields, abort
from src.database import SessionLocal
from src.models import Algorithm, Ortholog, Gene, Species, OrthologAlgorithms, Geneweaver_Species, Geneweaver_Gene, \
    Geneweaver_GeneDB, Mouse_Human

NS = Namespace('agr-service', description='Endpoints to query database')
db = SessionLocal()

# MODELS - correspond with models in models.py file, allow for output in JSON format
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

ortholog_algorithms_model = NS.model('ortholog_algorithms', {
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
# description: converts into agr gene_id using the ode_ref_id and ode_gene_id (both used
#     as primary key in geneweaver.gene table)
# returns: agr gene object
def convertODEtoAGR(ode_ref, ode_id):
    ode_gene = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_ref_id == ode_ref,
                                                Geneweaver_Gene.ode_gene_id == ode_id).first()
    genedb_id = ode_gene.gdb_id
    prefix = (db.query(Geneweaver_GeneDB).filter(Geneweaver_GeneDB.gdb_id == genedb_id).first()).gdb_name
    ref = ode_gene.ode_ref_id
    # convert the ref_ids into how the agr ref ids are stored, same values but formatted
    #    slightly different in each database
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


# description: converts an agr gene_id into the ode gene_id
# returns: ode gene object
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


# Algorithm Table Endpoints
@NS.route('/algorithm/<algorithm_name>')
class get_algorithm_by_name(Resource):
    @NS.doc('returns algorithm object with specified name')
    @NS.marshal_with(algorithm_model)
    def get(self, algorithm_name):
        result = db.query(Algorithm).filter(Algorithm.name == algorithm_name).first()
        return result


@NS.route('/algorithm')
class all_algorithms(Resource):
    @NS.doc('returns all algorithms')
    @NS.marshal_with(algorithm_model)
    def get(self):
        return db.query(Algorithm).all()


# Ortholog Table Endpoints
@NS.route('/ortholog/from/<ode_ref_id>/<ode_id>')
class get_orthologs_by_from_gene(Resource):
    @NS.doc('returns orthologs from the specified gene')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        # find gene and search orthologs based on gene_id
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs from the specified gene")
        return result


@NS.route('/ortholog/to/<ode_ref_id>/<ode_id>')
class get_orthologs_by_to_gene(Resource):
    @NS.doc('returns orthologs to specified the gene')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.to_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs to the specified gene")
        return result


@NS.route('/ortholog')
class all_orthologs(Resource):
    @NS.doc('returns all orthologs')
    @NS.marshal_with(ortholog_model)
    def get(self):
        return db.query(Ortholog).all()


@NS.route('/ortholog/<ortho_id>')
class get_ortholog_by_id(Resource):
    @NS.doc('returns orthologs with specified id')
    @NS.marshal_with(ortholog_model)
    def get(self, ortho_id):
        result = db.query(Ortholog).filter(Ortholog.id == ortho_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that ortholog id")
        return result


@NS.route('/ortholog/to_from/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>')
class get_orthologs_by_to_and_from_gene(Resource):
    @NS.doc('returns all orthologs to and from the specified genes')
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
class get_orthologs_by_from_gene_and_best(Resource):
    @NS.doc('returns all orthologs from specified gene and by the best variable')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, best):
        # best variable is a string, must convert it to a bool to use in query
        best = best.upper()
        if best == "FALSE" or best == "F":
            modified_best = False
        else:
            modified_best = True
        gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == gene.id,
                                           Ortholog.is_best == modified_best).all()
        if not result:
            abort(404, message="Could not find any orthologs with that from gene and is_best value")
        return result


@NS.route('/ortholog/best_from_to/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best>')
class get_orthologs_by_from_to_gene_and_best(Resource):
    @NS.doc('returns all orthologs from and to specified gene and by the best variable')
    @NS.marshal_with(ortholog_model)
    def get(self, from_ode_ref_id, from_ode_id, to_ode_ref_id, to_ode_id, best):
        # best variable is a string, must convert it to a bool to use in query
        best = best.upper()
        if best == "FALSE" or best == "F":
            modified_best = False
        else:
            modified_best = True
        # find from and to gene objects
        from_gene = convertODEtoAGR(from_ode_ref_id, from_ode_id)
        to_gene = convertODEtoAGR(to_ode_ref_id, to_ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == from_gene.id,
                                           Ortholog.to_gene == to_gene.id,
                                           Ortholog.is_best == modified_best).all()
        if not result:
            abort(404, message="Could not find any orthologs with that "
                               "from_gene, to_gene and is_best value")
        return result


@NS.route('/ortholog/best_revised_from_to/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best_revised>')
class get_orthologs_by_from_to_gene_and_revised(Resource):
    @NS.doc('returns all orthologs from and to specified gene and by the best_revised variable')
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
class get_from_gene_of_ortholog_by_id(Resource):
    @NS.doc('return from_gene object of a ortholog')
    @NS.marshal_with(gene_model)
    def get(self, ortho_id):
        ortholog = db.query(Ortholog).filter(Ortholog.id == ortho_id).first()
        result = db.query(Gene).filter(Gene.id == ortholog.from_gene).first()
        if not ortholog:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result


@NS.route('/ortholog/return_to_gene/<ortho_id>')
class get_to_gene_of_ortholog_by_id(Resource):
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
class get_genes(Resource):
    @NS.doc('return all genes')
    @NS.marshal_with(gene_model)
    def get(self):
        return db.query(Gene).all()


@NS.route('/gene/prefix/<prefix>')
class get_genes_by_prefix(Resource):
    @NS.doc('return all genes with specified prefix')
    @NS.marshal_with(gene_model)
    def get(self, prefix):
        prefix = prefix.upper()
        result = db.query(Gene).filter(Gene.id_prefix == prefix).all()
        if not result:
            abort(404, message="Could not find any genes with that prefix")
        return result


@NS.route('/gene/refID/<ode_ref_id>/<ode_id>')
class get_genes_by_ode_id(Resource):
    @NS.doc('return gene with specified ode_ref_id and ode_id')
    @NS.marshal_with(gene_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        if not gene:
            abort(404, message="Could not find any matching genes")
        return gene


@NS.route('/gene/species/<species_name>')
class get_genes_by_species(Resource):
    @NS.doc('returns ode_gene_ids for genes of a certain species')
    @NS.marshal_with(gene_model)
    def get(self, species_name):
        species = db.query(Species).filter(Species.name == species_name).first()
        genes = db.query(Gene).filter(Gene.species == species.id).all()
        if not genes:
            abort(404, message="Could not find any genes with that species")
        return genes


@NS.route('/gene/return_species_name/<ode_ref_id>/<ode_id>')
class get_gene_species_name(Resource):
    @NS.doc('returns the species of a specified gene')
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Species).filter(Species.id == gene.species).first()
        if not result:
            abort(404, message="Species not found for that reference_id")
        return result.name


# species Table Endpoints
@NS.route('/species')
class get_species(Resource):
    @NS.doc('return all species')
    @NS.marshal_with(species_model)
    def get(self):
        return db.query(Species).all()


@NS.route('/species/<s_id>')
class get_species_by_id(Resource):
    @NS.doc('return species specified by id')
    @NS.marshal_with(species_model)
    def get(self, s_id):
        return db.query(Species).filter(Species.id == s_id).all()


# ortholog_algorithms Table Endpoints
@NS.route('/ortholog/num_algorithms/<num>')
class get_orthologs_by_num_algoritms(Resource):
    @NS.doc('return all orthologs with specified num_possible_match_algorithms')
    @NS.marshal_with(ortholog_model)
    def get(self, num):
        result = db.query(Ortholog).filter(Ortholog.num_possible_match_algorithms == num).all()
        if not result:
            abort(404, message="Could not find any orthologs with that number "
                               "of possible match algorithms")
        return result


@NS.route('/ortholog_algorithms/ortholog/<algorithm>')
class get_ortholog_by_algorithm(Resource):
    @NS.doc('return all orthologs for an algorithm')
    @NS.marshal_with(ortholog_algorithms_model)
    def get(self, algorithm):
        # get algorithm id from string of algorithm name
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id
        orthologs = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id == algo_id).all()
        return orthologs


# ORTHOLOG AND SPECIES TABLES
@NS.route('/ortholog/from_species/<species_name>')
class get_ortholog_by_from_species(Resource):
    @NS.doc('return all orthologs from given species')
    @NS.marshal_with(ortholog_model)
    def get(self, species_name):
        # get species id from species_name string
        species_id = (db.query(Species).filter(Species.name == species_name).first()).id
        # find all genes with specified species and make a list of all the gene ids
        genes = db.query(Gene).filter(Gene.species == species_id).all()
        gene_ids = []
        for g in genes:
            gene_ids.append(g.id)
        # query orthologs for any from genes in the list of gene_ids
        from_orthos = db.query(Ortholog).filter(Ortholog.from_gene.in_(gene_ids)).all()
        if not from_orthos:
            abort(404, message="Could not find any matching orthologs")
        return from_orthos


@NS.route('/ortholog/to_species/<species_name>')
class get_ortholog_by_to_species(Resource):
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
class get_ortholog_by_to_and_from_species(Resource):
    @NS.doc('return all orthologs to and from given species')
    @NS.marshal_with(ortholog_model)
    def get(self, to_species, from_species):
        # get both species ids
        to_species_id = (db.query(Species).filter(Species.name == to_species).first()).id
        from_species_id = (db.query(Species).filter(Species.name == from_species).first()).id

        # create a list of all gene_ids to and from the species
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
class get_ortholog_by_to_from_species_and_algorithm(Resource):
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

        # get algorithm id from algorithm string
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id

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
class agr_to_geneweaver_species(Resource):
    @NS.doc('translate an AGR species id to the corresponding species id in the geneweaver database')
    def get(self, species_id):
        agr_name = (db.query(Species).filter(Species.id == species_id).first()).name
        geneweaver_id = (db.query(Geneweaver_Species).filter(Geneweaver_Species.sp_name == agr_name).first()).sp_id
        if not geneweaver_id:
            abort(404, message="No matching species_id in the Geneweaver Species Table")
        return geneweaver_id


# similar to the convertAGRtoODE function
@NS.route('/ode_gene_id/<agr_gene_id>')
class id_convert_agr_to_ode(Resource):
    @NS.doc('converts an agr gene id to the corresponding ode_gene_ide')
    def get(self, agr_gene_id):
        agr_gene = db.query(Gene).filter(Gene.id == agr_gene_id).first()
        # edit the ref id to be in the format of the ode_ref_id, then search geneweaver.gene
        ref = agr_gene.reference_id
        prefix = agr_gene.id_prefix
        if prefix == "RGD":
            ref = ref.replace(":", "")
        elif prefix == "WB" or prefix == "FB" or prefix == "SGD" or prefix == "ZFIN":
            ind = ref.find(":") + 1
            ref = ref[ind:]
        ode_id = (db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_ref_id == ref).first()).ode_gene_id
        if not ode_id:
            abort(404, message="matching ode_gene_id not found")
        return ode_id


# similar to the convertODEtoAGR function
@NS.route('/agr_gene_id/<ode_gene_id>/<ode_ref_id>')
class id_convert_ode_to_agr(Resource):
    @NS.doc('converts an ode gene id to the corresponding agr gene id')
    def get(self, ode_gene_id, ode_ref_id):
        ode_gene = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id,
                                                    Geneweaver_Gene.ode_ref_id == ode_ref_id).first()
        genedb_id = ode_gene.gdb_id
        prefix = (db.query(Geneweaver_GeneDB).filter(Geneweaver_GeneDB.gdb_id == genedb_id).first()).gdb_name
        # edit the ref id to be in the format of the AGR ref_id, then search the gene table
        ref = ode_gene.ode_ref_id
        # specific prefixes are formatted differently, only 6 total in AGR database
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
class get_ode_gene_by_gdb_id(Resource):
    @NS.doc('return all ode_genes with the specified gdb_id')
    @NS.marshal_with(ode_gene_model)
    def get(self, gdb_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.gdb_id == gdb_id).all()
        if not genes:
            abort(404, message="No genes were found with specified gdb_id")
        return genes


@NS.route('/ode_gene/<ode_gene_id>')
class get_ode_gene_by_gene_id(Resource):
    @NS.doc('return all ode_genes with the same ode_gene_id')
    @NS.marshal_with(ode_gene_model)
    def get(self, ode_gene_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id).all()
        if not genes:
            abort(404, message="No genes were found matching that ode_gene_id")
        return genes


@NS.route('/ode_gene/species/<ode_gene_id>/<species_name>')
class get_ode_gene_by_species(Resource):
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
# The following endpoints map from mouse to human and from human to mouse while also returning
#    the corresponding Ensembl ID

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
    @NS.doc('returns all orthologs from mouse to human with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).filter(Mouse_Human.is_mouse_to_human == True).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs


@NS.route('/ortholog/mouse_human_all')
class get_mouse_human_all(Resource):
    @NS.doc('returns all orthologs containing human and mouse with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs
