"""
Definition of our API interface - Endpoints query the AGR database
"""

from flask_restx import Namespace, Resource, fields, abort, reqparse
from src.database import SessionLocal
from src.models import Algorithm, Ortholog, Gene, Species, OrthologAlgorithms, \
    Geneweaver_Species, Geneweaver_Gene, Geneweaver_GeneDB, Mouse_Human

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

gw_gene_model = NS.model('geneweaver_genes', {
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
# params: ode_ref - ode_ref_id of gene
#         ode_id - ode_gene_id of gene
# returns: agr gene object
def convertODEtoAGR(ode_ref, ode_id):
    # convert the ref_ids into how the agr ref ids are stored, same values but formatted
    #    slightly different in each database
    ref = ode_ref
    if ode_ref[0] == 'W':
        prefix = "WB"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'F':
        prefix = "FB"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'S':
        prefix = "SGD"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'Z':
        prefix = "ZFIN"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'R':
        ref = ode_ref[:3] + ":" + ode_ref[3:]

    agr = db.query(Gene).filter(Gene.reference_id == ref).first()
    return agr


# description: converts an agr gene_id into the ode gene_id
# params: agr_gene_id - id from gene table in agr database
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
@NS.route('/get_algorithm_by_name/<algorithm_name>')
class get_algorithm_by_name(Resource):
    '''
    :param algoritm_name: string of full species name, case sensitive
    :return: id and name for one algorithm
    '''
    @NS.doc('returns algorithm object with specified name')
    @NS.marshal_with(algorithm_model)
    def get(self, algorithm_name):
        result = db.query(Algorithm).filter(Algorithm.name == algorithm_name).first()
        return result


@NS.route('/all_algorithms')
class all_algorithms(Resource):
    '''
    :return: id and name for each algorithm
    '''
    @NS.doc('returns all algorithms')
    @NS.marshal_with(algorithm_model)
    def get(self):
        return db.query(Algorithm).all()


# Ortholog Table Endpoints
@NS.route('/get_orthologs_by_from_gene/<ode_ref_id>/<ode_id>')
class get_orthologs_by_from_gene(Resource):
    '''
    :param ode_ref_id - ode_ref_id of from gene
           ode_id - ode_gene_id of from gene
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog with specified from_gene
    '''
    @NS.doc('returns orthologs from a specified gene')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        # find gene and search orthologs based on gene_id
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.from_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs from the specified gene")
        return result


@NS.route('/get_orthologs_by_to_gene/<ode_ref_id>/<ode_id>')
class get_orthologs_by_to_gene(Resource):
    '''
    :param ode_ref_id - ode_ref_id of to gene
           ode_id - ode_gene_id of to gene
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog with specified to_gene
    '''
    @NS.doc('returns orthologs to a specified gene')
    @NS.marshal_with(ortholog_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Ortholog).filter(Ortholog.to_gene == gene.id).all()
        if not result:
            abort(404, message="Could not find any orthologs to the specified gene")
        return result


@NS.route('/all_orthologs')
class all_orthologs(Resource):
    '''
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms)
    '''
    @NS.doc('returns all orthologs')
    @NS.marshal_with(ortholog_model)
    def get(self):
        return db.query(Ortholog).all()


@NS.route('/get_ortholog_by_id/<ortho_id>')
class get_ortholog_by_id(Resource):
    '''
    :param ortho_id - id from ortholog table
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog with specified ortho_id
    '''
    @NS.doc('returns orthologs with specified id')
    @NS.marshal_with(ortholog_model)
    def get(self, ortho_id):
        result = db.query(Ortholog).filter(Ortholog.id == ortho_id).all()
        if not result:
            abort(404, message="Could not find any orthologs with that ortholog id")
        return result


@NS.route('/get_orthologs_by_to_and_from_gene/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>')
class get_orthologs_by_to_and_from_gene(Resource):
    '''
    :param from_ode_ref_id - ode_ref_id of from gene
           from_ode_id - ode_gene_id of from gene
           to_ode_ref_id - ode_ref_id of to gene
           to_ode_id - ode_gene_id of to gene
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog with specified from_gene and to_gene
    '''
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


@NS.route('/get_orthologs_by_from_gene_and_best/<from_ode_ref_id>/<from_ode_id>/<best>')
class get_orthologs_by_from_gene_and_best(Resource):
    '''
    :param from_ode_ref_id - ode_ref_id of from gene
           from_ode_id - ode_gene_id of from gene
           best - boolean to query the is_best column in ortholog table
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog from a specific gene and T or F for
             the is_best column
    '''
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


@NS.route('/get_orthologs_by_from_to_gene_and_best/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best>')
class get_orthologs_by_from_to_gene_and_best(Resource):
    '''
    :param from_ode_ref_id - ode_ref_id of from gene
           from_ode_id - ode_gene_id of from gene
           to_ode_ref_id - ode_ref_id of to gene
           to_ode_id - ode_gene_id of to gene
           best - boolean to query the is_best column in ortholog table
    :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for any ortholog with specified from_gene and to_gene
             and T or F for the is_best column
    '''
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


@NS.route('/get_orthologs_by_from_to_gene_and_revised/<from_ode_ref_id>/<from_ode_id>/<to_ode_ref_id>/<to_ode_id>/<best_revised>')
class get_orthologs_by_from_to_gene_and_revised(Resource):
    '''
        :param from_ode_ref_id - ode_ref_id of from gene
               from_ode_id - ode_gene_id of from gene
               to_ode_ref_id - ode_ref_id of to gene
               to_ode_id - ode_gene_id of to gene
               best_revised - boolean to query the is_best_revised column in ortholog table
        :return: all ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
                 and num_possible_match_algorithms) for any ortholog with specified from_gene and to_gene
                 and T or F for the is_best_revised column
        '''
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


@NS.route('/get_from_gene_of_ortholog_by_id/<ortho_id>')
class get_from_gene_of_ortholog_by_id(Resource):
    '''
    :param ortho_id: id from ortholog table
    :return: gene info (id, ref_id, prefix, species) of the from gene for that ortholog
    '''
    @NS.doc('return from_gene object of a ortholog')
    @NS.marshal_with(gene_model)
    def get(self, ortho_id):
        ortholog = db.query(Ortholog).filter(Ortholog.id == ortho_id).first()
        result = db.query(Gene).filter(Gene.id == ortholog.from_gene).first()
        if not ortholog:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result


@NS.route('/get_to_gene_of_ortholog_by_id/<ortho_id>')
class get_to_gene_of_ortholog_by_id(Resource):
    '''
    :param ortho_id: id from ortholog table
    :return: gene info (id, ref_id, prefix, species) of the to gene for that ortholog
    '''
    @NS.doc('return to_gene object of a specific ortholog')
    @NS.marshal_with(gene_model)
    def get(self, ortho_id):
        ortho = db.query(Ortholog).filter(Ortholog.id == ortho_id).first()
        result = db.query(Gene).filter(Gene.id == ortho.to_gene).first()
        if not ortho:
            abort(404, message="Could not find any orthologs with the given parameters")
        return result


@NS.route('/get_ortho_id_by_from_gene/<ode_gene_id>/<ode_ref_id>/<gdb_id>')
class get_id_by_from_gene(Resource):
    '''
    :param ode_ref_id - ode_ref_id of to gene
           ode_id - ode_gene_id of to gene
           gdb_id - gdb_id of specified gene, provided to make translating from ode gene
                    to agr gene faster within the endpoint
    :return: list of ortholog ids that have specified gene as the from_gene
    '''
    @NS.doc('returns the ortholog id filtering by the ortholog from gene, including the gdb_id')
    def get(self, ode_gene_id, ode_ref_id, gdb_id):
        ref = ode_ref_id
        gdb_id = int(gdb_id)

        # compressing the steps of calling convertODEtoAGR() so fewer queries are called,
        #    hopefully making this endpoint more efficient. this is why the gdb_id is provided
        if gdb_id == 15:
            prefix = "WB"
            ref = prefix + ":" + ref
        if gdb_id == 14:
            prefix = "FB"
            ref = prefix + ":" + ref
        if gdb_id == 16:
            prefix = "SGD"
            ref = prefix + ":" + ref
        if gdb_id == 13:
            prefix = "ZFIN"
            ref = prefix + ":" + ref
        if gdb_id == 12:
            ref = ref[:3] + ":" + ref[3:]

        # find matching agr gene and filter the ortholog table with the agr gene id
        agr_gene_id = (db.query(Gene).filter(Gene.reference_id == ref).first()).id
        id = ((db.query(Ortholog).filter(Ortholog.from_gene == agr_gene_id)).first()).id
        return id


@NS.route('/get_ortholog_by_from_gene_and_gdb/<from_ode_gene_id>/<gdb_id>')
class get_ortholog_by_from_gene_and_gdb(Resource):
    '''
    :param ode_gene_id - ode_gene_id of from gene
           gdb_id - gdb_id of specified gene, this is the gdb_id we are filtering by
    :return: to gene info (ode_ref_id) for any ortholog that has the given from
             gene. the goal is to find info about the orthologous gene from the given gene.
    '''
    @NS.doc('returns to gene ode_gene_id and ode_ref_id of any ortholog with the from gene matching'
            'the given ode_gene_id and to gene matching the gdb_id')
    def get(self, from_ode_gene_id, gdb_id):
        # any gene with a gdb_id that is not in the agr_compatible_gdb_ids will not be found in the agr
        #    database, so it is filtered out in the search.
        agr_compatible_gdb_ids = [10, 11, 12, 13, 14, 15, 16]
        genes = db.query(Geneweaver_Gene.ode_ref_id, Geneweaver_Gene.gdb_id).filter(Geneweaver_Gene.ode_gene_id
                                                                                    == from_ode_gene_id,
                                                                                    Geneweaver_Gene.gdb_id.in_(
                                                                                        agr_compatible_gdb_ids)).all()

        # the species from the geneweaver database is translated into the agr_species id so it can
        #   be used to filter by species (gdb_id) within the agr database.
        gdb_id = int(gdb_id)
        # mouse
        if gdb_id == 10: agr_species = 1
        # human
        elif gdb_id == 11: agr_species = 7
        # rat
        elif gdb_id == 12: agr_species = 2
        # danio rerio
        elif gdb_id == 13: agr_species = 6
        # drosophilia
        elif gdb_id == 14: agr_species = 5
        # c elegans
        elif gdb_id == 15: agr_species = 11
        # sacc
        elif gdb_id == 16: agr_species = 3
        else: agr_species = 0

        # ode_ref_ids are translated into the agr format found in the ref_id column of the
        #   agr gene table
        from_gene_refs = []
        for g in genes:
            ref = str(g[0])
            from_gdb_id = int(g[1])
            if from_gdb_id == 15:
                prefix = "WB"
                ref = prefix + ":" + ref
            if from_gdb_id == 14:
                prefix = "FB"
                ref = prefix + ":" + ref
            if from_gdb_id == 16:
                prefix = "SGD"
                ref = prefix + ":" + ref
            if from_gdb_id == 13:
                prefix = "ZFIN"
                ref = prefix + ":" + ref
            if from_gdb_id == 12:
                ref = ref[:3] + ":" + ref[3:]
            from_gene_refs.append(ref)

        # a list of agr gene ids that match the ref ids
        from_genes = db.query(Gene.id).filter(Gene.reference_id.in_(from_gene_refs)).all()
        # a list of to_gene ids where the from_gene value is in the from_genes list of ids
        to_gene_ids = db.query(Ortholog.to_gene).filter(Ortholog.from_gene.in_(from_genes)).all()
        # agr format info about to_genes
        to_gene_info = db.query(Gene.reference_id, Gene.id_prefix).filter(Gene.id.in_(to_gene_ids), Gene.species == agr_species).all()

        # translate the agr format ref_ids back to ode format
        to_gene_ode_refs = []
        for r in to_gene_info:
            ref = str(r[0])
            prefix = str(r[1])
            if prefix == "RGD":
                ref = ref.replace(":", "")
            elif prefix == "WB" or prefix == "FB" or prefix == "SGD" or prefix == "ZFIN":
                ind = ref.find(":") + 1
                ref = ref[ind:]
            to_gene_ode_refs.append(ref)

        return to_gene_ode_refs

@NS.route('/if_ode_gene_has_ortholog/<ode_gene_id>')
class if_ode_gene_has_ortholog(Resource):
    '''
    :param ode_gene_id
    :return: boolean, if gene is an ortholog
    '''
    @NS.doc('check if ode gene is an ortholog')
    def get(self, ode_gene_id):
        is_ortholog = 1
        # any gene with a gdb_id that is not in the agr_compatible_gdb_ids will not be found in the agr
        #    database, so it is filtered out in the search.
        agr_compatible_gdb_ids = [10, 11, 12, 13, 14, 15, 16]
        ode_genes = db.query(Geneweaver_Gene.ode_ref_id, Geneweaver_Gene.gdb_id).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id, Geneweaver_Gene.gdb_id.in_(
                                                                                        agr_compatible_gdb_ids)).all()

        # ode_ref_ids are translated into the agr format found in the ref_id column of the
        #   agr gene table
        agr_refs = []
        for g in ode_genes:
            ref = str(g[0])
            from_gdb_id = int(g[1])
            if from_gdb_id == 15:
                prefix = "WB"
                ref = prefix + ":" + ref
            if from_gdb_id == 14:
                prefix = "FB"
                ref = prefix + ":" + ref
            if from_gdb_id == 16:
                prefix = "SGD"
                ref = prefix + ":" + ref
            if from_gdb_id == 13:
                prefix = "ZFIN"
                ref = prefix + ":" + ref
            if from_gdb_id == 12:
                ref = ref[:3] + ":" + ref[3:]
            agr_refs.append(ref)

        # find ortholog ids that are from the gene with given ode_gene_id
        agr_gene_ids = db.query(Gene.id).filter(Gene.reference_id.in_(agr_refs)).all()
        from_gene = db.query(Ortholog.id).filter(Ortholog.from_gene.in_(agr_gene_ids)).all()

        # if the agr_gene_ids are not in any of the ortholog's from_gene or to_gene columns,
        #   the gene is not an ortholog
        if (len(from_gene) == 0):
            to_gene = db.query(Ortholog.id).filter(Ortholog.to_gene.in_(agr_gene_ids)).all()
            if (len(to_gene) == 0):
                is_ortholog = 0

        return is_ortholog

# gene Table Endpoints
@NS.route('/all_genes')
class all_genes(Resource):
    '''
    :return: all gene info (id, ref_id, prefix, species)
    '''
    @NS.doc('return all genes')
    @NS.marshal_with(gene_model)
    def get(self):
        return db.query(Gene).all()


@NS.route('/get_genes_by_prefix/<prefix>')
class get_genes_by_prefix(Resource):
    '''
    :param: prefix
    :return: gene info (id, ref_id, prefix, species) for genes with given prefix
    '''
    @NS.doc('return all genes with specified prefix')
    @NS.marshal_with(gene_model)
    def get(self, prefix):
        prefix = prefix.upper()
        result = db.query(Gene).filter(Gene.id_prefix == prefix).all()
        if not result:
            abort(404, message="Could not find any genes with that prefix")
        return result


@NS.route('/get_genes_by_ode_id/<ode_ref_id>/<ode_id>')
class get_genes_by_ode_id(Resource):
    '''
    :param ode_ref_id - ode_ref_id of gene
           ode_id - ode_gene_id of gene
    :return: gene info (id, ref_id, prefix, species) for agr gene, endpoint version of
            convertODEtoAGR()
    '''
    @NS.doc('return gene with specified ode_ref_id and ode_id')
    @NS.marshal_with(gene_model)
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        if not gene:
            abort(404, message="Could not find any matching genes")
        return gene


@NS.route('/get_genes_by_species/<species_name>')
class get_genes_by_species(Resource):
    '''
    :param: species_name - string for species name, case sensitive
    :return: info (id, ref_id, prefix, species) for genes of given species
    '''
    @NS.doc('returns ode_gene_ids for genes of a certain species')
    @NS.marshal_with(gene_model)
    def get(self, species_name):
        species = db.query(Species).filter(Species.name == species_name).first()
        genes = db.query(Gene).filter(Gene.species == species.id).all()
        if not genes:
            abort(404, message="Could not find any genes with that species")
        return genes


@NS.route('/get_gene_species_name/<ode_ref_id>/<ode_id>')
class get_gene_species_name(Resource):
    '''
    :param ode_ref_id - ode_ref_id of gene
           ode_id - ode_gene_id of gene
    :return: species name of gene
    '''
    @NS.doc('returns the species of a specified gene')
    def get(self, ode_ref_id, ode_id):
        gene = convertODEtoAGR(ode_ref_id, ode_id)
        result = db.query(Species).filter(Species.id == gene.species).first()
        if not result:
            abort(404, message="Species not found for that reference_id")
        return result.name


# species Table Endpoints
@NS.route('/all_species')
class all_species(Resource):
    '''
    :return: species info (id, name, taxon_id) for all species
    '''
    @NS.doc('return all species')
    @NS.marshal_with(species_model)
    def get(self):
        return db.query(Species).all()


@NS.route('/get_species_by_id/<s_id>')
class get_species_by_id(Resource):
    '''
    :param: s_id
    :return: species info (id, name, taxon_id) for species by id
    '''
    @NS.doc('return species specified by id')
    @NS.marshal_with(species_model)
    def get(self, s_id):
        return db.query(Species).filter(Species.id == s_id).all()


# ortholog_algorithms Table Endpoints
@NS.route('/get_orthologs_by_num_algoritms/<num>')
class get_orthologs_by_num_algoritms(Resource):
    '''
    :param: num - number of algoirthms
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs with num_algorithms
    '''
    @NS.doc('return all orthologs with specified num_possible_match_algorithms')
    @NS.marshal_with(ortholog_model)
    def get(self, num):
        result = db.query(Ortholog).filter(Ortholog.num_possible_match_algorithms == num).all()
        if not result:
            abort(404, message="Could not find any orthologs with that number "
                               "of possible match algorithms")
        return result


@NS.route('/get_ortholog_by_algorithm/<algorithm>')
class get_ortholog_by_algorithm(Resource):
    '''
    :param: algorithm - str algorithm by name
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs with that algorithm
    '''
    @NS.doc('return all orthologs for an algorithm')
    @NS.marshal_with(ortholog_algorithms_model)
    def get(self, algorithm):
        # get algorithm id from string of algorithm name
        algo_id = (db.query(Algorithm).filter(Algorithm.name == algorithm).first()).id
        orthologs = db.query(OrthologAlgorithms).filter(OrthologAlgorithms.algorithm_id == algo_id).all()
        return orthologs


# ORTHOLOG AND SPECIES TABLES
@NS.route('/get_ortholog_by_from_species/<species_name>')
class get_ortholog_by_from_species(Resource):
    '''
    :param: species_name - str, case sensitive, from gene species
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs from given species
    '''
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


@NS.route('/get_ortholog_by_to_species/<species_name>')
class get_ortholog_by_to_species(Resource):
    '''
    :param: species_name - str, case sensitive, to gene species
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs to given species
    '''
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


@NS.route('/get_ortholog_by_to_and_from_species/<to_species>/<from_species>')
class get_ortholog_by_to_and_from_species(Resource):
    '''
    :param: to_sepcies - str, case sensitive, to gene species name
            from_species - str, case sensitive, from gene species name
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs to and from the given species
    '''
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


@NS.route('/get_ortholog_by_to_from_species_and_algorithm/<to_species>/<from_species>/<algorithm>')
class get_ortholog_by_to_from_species_and_algorithm(Resource):
    '''
    :param: to_sepcies - str, case sensitive, to gene species name
            from_species - str, case sensitive, from gene species name
            algorithm - str, algoirthm name
    :return: ortholog info ortholog info (id, from_gene, to_gene, is_best, is_best_revised, is_best_adjusted,
             and num_possible_match_algorithms) for all orthologs to and from the given species
             and by algorithm
    '''
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

@NS.route('/agr_to_geneweaver_species/<species_id>')
class agr_to_geneweaver_species(Resource):
    '''
    :param: species_id - agr species id
    :return: geneweaver species id
    '''
    @NS.doc('translate an AGR species id to the corresponding species id in the geneweaver database')
    def get(self, species_id):
        agr_name = (db.query(Species).filter(Species.id == species_id).first()).name
        geneweaver_id = (db.query(Geneweaver_Species).filter(Geneweaver_Species.sp_name == agr_name).first()).sp_id
        if not geneweaver_id:
            abort(404, message="No matching species_id in the Geneweaver Species Table")
        return geneweaver_id


# similar to the convertAGRtoODE function
@NS.route('/id_convert_agr_to_ode/<agr_gene_id>')
class id_convert_agr_to_ode(Resource):
    '''
    :param: agr_gene_id
    :return: ode_id of corresponding gene in geneweaver database
    '''
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
@NS.route('/id_convert_ode_to_agr/<ode_gene_id>/<ode_ref_id>')
class id_convert_ode_to_agr(Resource):
    '''
    :param: ode_ref_id - ode_ref_id of gene
            ode_id - ode_gene_id of gene
    :return: agr gene id of corresponding gene
    '''
    @NS.doc('converts an ode gene id to the corresponding agr gene id')
    def get(self, ode_gene_id, ode_ref_id):
        ode_gene = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id
                                                    == ode_gene_id, Geneweaver_Gene.ode_ref_id
                                                    == ode_ref_id).first()
        genedb_id = ode_gene.gdb_id
        prefix = (db.query(Geneweaver_GeneDB).filter(Geneweaver_GeneDB.gdb_id
                                                     == genedb_id).first()).gdb_name
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


@NS.route('/get_ode_gene_by_gdb_id/<gdb_id>')
class get_ode_gene_by_gdb_id(Resource):
    '''
    :param: gdb_id
    :return: gene info (ode_gene_id, ode_ref_id, gdb_id, sp_id,
             ode_pref, ode_date, old_ode_gene_ids) of genes with
             gdb_id
    '''
    @NS.doc('return all ode_genes with the specified gdb_id')
    @NS.marshal_with(gw_gene_model)
    def get(self, gdb_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.gdb_id ==
                                                 gdb_id).all()
        if not genes:
            abort(404, message="No genes were found with specified gdb_id")
        return genes


@NS.route('/get_ode_gene_by_gene_id/<ode_gene_id>')
class get_ode_gene_by_gene_id(Resource):
    '''
    :param: ode_gene_id
    :return: gene info (ode_gene_id, ode_ref_id, gdb_id, sp_id,
             ode_pref, ode_date, old_ode_gene_ids) of genes with
             same ode_gene_id as given
    '''
    @NS.doc('return all ode_genes with the same ode_gene_id')
    @NS.marshal_with(gw_gene_model)
    def get(self, ode_gene_id):
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id
                                                 == ode_gene_id).all()
        if not genes:
            abort(404, message="No genes were found matching that ode_gene_id")
        return genes


@NS.route('/get_ode_gene_by_species/<ode_gene_id>/<species_name>')
class get_ode_gene_by_species(Resource):
    '''
    :param: ode_gene_id
            species_name - case sensitive
    :return: gene info (ode_gene_id, ode_ref_id, gdb_id, sp_id,
             ode_pref, ode_date, old_ode_gene_ids) of genes with
             same ode_gene_id as given and within same species
    '''
    @NS.doc('return all genes with matching ode_gene_id and species')
    @NS.marshal_with(gw_gene_model)
    def get(self, ode_gene_id, species_name):
        sp_id = (db.query(Geneweaver_Species).filter(Geneweaver_Species.sp_name ==
                                                     species_name).first()).sp_id
        genes = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id == ode_gene_id,
                                                 Geneweaver_Gene.sp_id == sp_id).all()
        if not genes:
            abort(404, message="No genes were found matching that ode_gene_id and species")
        return genes


# Mouse Human Mapping
# The following endpoints map from mouse to human and from human to mouse
#    while also returning the corresponding Ensembl ID

@NS.route('/HumanToMouse')
class HumanToMouse(Resource):
    '''
    :return: ortholog info (m_id, m_symbol, m_ensembl_id, h_id, h_symbol,
             h_ensembl_id, is_mouse_to_human) for human to mouse orthologs
    '''
    @NS.doc('returns all orthologs from human to mouse with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).filter(Mouse_Human.is_mouse_to_human
                                                 == False).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs


@NS.route('/MouseToHuman')
class MouseToHuman(Resource):
    '''
    :return: ortholog info (m_id, m_symbol, m_ensembl_id, h_id, h_symbol,
             h_ensembl_id, is_mouse_to_human) for mouse to human orthologs
    '''
    @NS.doc('returns all orthologs from mouse to human with Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).filter(Mouse_Human.is_mouse_to_human
                                                 == True).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs


@NS.route('/get_mouse_human_all')
class get_mouse_human_all(Resource):
    '''
    :return: ortholog info (m_id, m_symbol, m_ensembl_id, h_id, h_symbol,
             h_ensembl_id, is_mouse_to_human) any mouse to human or human
             to mouse ortholog
    '''
    @NS.doc('returns all orthologs containing human and mouse with '
            'Ensembl IDs')
    @NS.marshal_with(mouse_human_model)
    def get(self):
        orthologs = db.query(Mouse_Human).all()
        if not orthologs:
            abort(404, message="No orthologs were found")
        return orthologs

def convert_ode_ref_to_agr(ode_ref):
    ref = ode_ref
    if ode_ref[0] == 'W':
        prefix = "WB"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'F':
        prefix = "FB"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'S':
        prefix = "SGD"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'Z':
        prefix = "ZFIN"
        ref = prefix + ":" + ode_ref
    if ode_ref[0] == 'R':
        ref = ode_ref[:3] + ":" + ode_ref[3:]
    return ref

def convert_species_ode_to_agr(ode_sp_id):
    sp_dict = {1:1, 2:7, 3:9, 4:6, 5:12, 8:4, 9:3}
    return sp_dict[ode_sp_id]

def convert_agr_ref_to_ode(agr_ref):
    ref = agr_ref
    remove_first_letters = ['W', 'F', 'S', 'Z']
    if agr_ref[0] == "R":
        ref = ref.replace(":", "")
    elif agr_ref[0] in remove_first_letters:
        ind = ref.find(":") + 1
        ref = ref[ind:]
    return ref

parser = reqparse.RequestParser()
@NS.route('/transpose_genes_by_species', methods=['GET','POST'])
class transpose_genes_by_homology(Resource):
    '''
    :params: genes - taken through parser, list of ode_ref_ids to be tranposed
             species - newSpecies that genes will be transposed to through orthology
    :return: list of ode_ref_ids of transposed genes, genes that are orthologs to the
             original genes but are of the specified newSpecies
    '''
    @NS.expect(parser)
    def get(self):
        parser.add_argument('genes', type=str, action="append")
        parser.add_argument('species', type=int)
        data = parser.parse_args()
        sp = data['species']

        if sp not in [1, 2, 3, 4, 5, 8, 9]:
            abort(404, message = "No matching genes with that species")
        else:
            sp = convert_species_ode_to_agr(sp)

        refs = []
        for g in data['genes']:
            refs.append(convert_ode_ref_to_agr(g))

        from_gene_ids = db.query(Gene.id).filter(Gene.reference_id.in_(refs)).all()

        to_gene_ids = db.query(Ortholog.to_gene).filter(Ortholog.from_gene.in_(from_gene_ids)).all()
        to_gene_filtered_refs = db.query(Gene.reference_id).filter(Gene.id.in_(to_gene_ids),
                                                                   Gene.species == sp).all()

        ode_refs = []
        for r in to_gene_filtered_refs:
            ode_refs.append(convert_agr_ref_to_ode(r[0]))

        return ode_refs