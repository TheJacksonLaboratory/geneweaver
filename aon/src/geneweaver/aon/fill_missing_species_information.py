from geneweaver.aon.models import Gene, Ortholog, Geneweaver_Gene, Species
from psycopg2.pool import ThreadedConnectionPool
from controller import convert_ode_ref_to_agr
from sqlalchemy.ext.declarative import declarative_base
import itertools
from geneweaver.aon.controller import convert_species_ode_to_agr
from geneweaver.aon.database import SessionLocal
import time
start_time = time.time()

BASE = declarative_base()

db = SessionLocal()

##########################################################################################
# connection to both databases using connection pool

class GeneWeaverThreadedConnectionPool(ThreadedConnectionPool):
    """Extend ThreadedConnectionPool to initialize the search_path"""

    def __init__(self, minconn, maxconn, *args, **kwargs):
        ThreadedConnectionPool.__init__(self, minconn, maxconn, *args, **kwargs)

    def _connect(self, key=None):
        """Create a new connection and set its search_path"""
        conn = super(GeneWeaverThreadedConnectionPool, self)._connect(key)
        conn.set_client_encoding('UTF-8')
        cursor = conn.cursor()
        cursor.execute('SET search_path TO production, extsrc, odestatic;')
        conn.commit()

        return conn

# the global threaded connection pool that should be used for all DB
# connections in this application

# TODO - update database information to relevant databases
pool = GeneWeaverThreadedConnectionPool(
    5, 20,
    database='geneweaver',
    user='user',
    password='pass',
    host='localhost',
    port='2222'
)
pool_agr = GeneWeaverThreadedConnectionPool(
    5, 20,
    database='agr',
    user='user',
    password='pass',
    host='localhost',
    port='5432'
)

# creates cursor for both geneweaver and agr databases
class PooledCursor(object):
    """
    This is the cursor for the Geneweaver database
    A cursor obtained from a connection pool. This is suitable for using in a with ... as ...: construct (the
    underlying connection will be automatically returned to the connection pool
    """

    def __init__(self, conn_pool=pool, rollback_on_exception=False):
        self.conn_pool = conn_pool
        self.rollback_on_exception = rollback_on_exception
        self.connection = None

    def __enter__(self):
        self.connection = self.conn_pool.getconn()
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection is not None:
            if self.rollback_on_exception and exc_type is not None:
                self.connection.rollback()

            self.conn_pool.putconn(self.connection)

class PooledCursorAGR(object):
    """
    This is the cursor for the AGR database
    """

    def __init__(self, conn_pool=pool_agr, rollback_on_exception=False):
        self.conn_pool = conn_pool
        self.rollback_on_exception = rollback_on_exception
        self.connection = None

    def __enter__(self):
        self.connection = self.conn_pool.getconn()
        return self.connection.cursor()

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.connection is not None:
            if self.rollback_on_exception and exc_type is not None:
                self.connection.rollback()

            self.conn_pool.putconn(self.connection)

##########################################################################################

def add_missing_species():
    '''
        :description: adds three missing species to sp_species table
    '''
    species_dict = {
        'Gallus gallus': 9031,
        'Canis familiaris': 9615,
        'Macaca mulatta': 9544
    }
    i = 8
    for s in species_dict.keys():
        species = Species(sp_id=i, sp_name=s, sp_taxon_id=species_dict[s])
        db.add(species)
        i += 1
    db.commit()

##########################################################################################

def convert_gdb_to_prefix(gdb_id):
    '''
        :param: gdb_id - gdb_id from genedb table in geneweaver database, used as key for
                gn_prefix in agr gn_gene table because in agr, each prefix corresponds to
                one genedb
        :return: gn_prefix from gdb_dict corresponding to param gdb_id
        :description: converts gdb_id to gn_prefix to communicate between agr and geneweaver
                databases
    '''
    gdb_dict = {1:'entrez', 2:'ensembl', 3:'ensembl_protein', 4:'ensembl_transcript', 5:'unigene',
                7:'symbol', 8:'unannotated', 10:'MGI', 11:'HGNC', 12:'RGD', 13:'ZFIN', 14:'FB',
                15:'WB', 16:'SGD', 17:'miRBase', 20:'CGNC', 21:'Variant'}
    return gdb_dict[int(gdb_id)]

def add_missing_genes():
    '''
        :description: adds genes from geneweaver gene table for the three missing species.
                parses information from this table to create Gene objects to go into gn_gene
                table in agr.
    '''

    # query for a list of geneweaver genes from Gallus gallus (sp_id=10, gdb_id=20),
    #    Canis familiaris(sp_id=11, gdb_id=2), and Macaca mulatta (sp_id=6, gdb_id=1)
    with PooledCursor() as cursor:
        cursor.execute('''
        SELECT ode_ref_id, gdb_id, sp_id FROM extsrc.gene WHERE sp_id IN (6,10,11)
        AND gdb_id in (1,2,20);
        ''')
        gw_genes = cursor.fetchall()

    i = 0
    genes = []
    for g in gw_genes:
        gn_ref_id = g[0]
        gn_prefix = convert_gdb_to_prefix(g[1])
        sp_id = convert_species_ode_to_agr(int(g[2]))

        gene = Gene(gn_ref_id=gn_ref_id, gn_prefix=gn_prefix,
                    sp_id=sp_id)
        genes.append(gene)

        # adds genes to database 1000 at a time
        if i % 1000 == 0 and i != 0:
            db.bulk_save_objects(genes)
            db.commit()
            genes = []
            i = 0
        else:
            i += 1

##########################################################################################

def get_homolog_information():
    with PooledCursorAGR() as cursorAGR:
        # get all ode_gene_ids of the genes in the gn_gene table for the 3 missing species
        cursorAGR.execute('''
                select ode_gene_id from geneweaver.gene where ode_ref_id in (
        		select gn_ref_id from public.gn_gene where sp_id in (8,9,10))
        		;
                ''')
        output = cursorAGR.fetchall()

        # put output into list format
        gw_genes = []
        for g in output:
            gw_genes.append(str(g[0]))

        with PooledCursor() as cursor:
            # get hom_id, ode_gene_id, and sp_id from the geneweaver homology table for any homolog
            #   that is a member of a cluster that contains a gene in agr and of the 3 missing species,
            #   also orders by hom_id to make it easier to parse
            cursor.execute('''
                         select hom_id, ode_gene_id, sp_id from extsrc.homology h1 where h1.hom_id in (
                                         select hom_id from extsrc.homology h2 where ode_gene_id in ({}))
                                     order by hom_id;
                         '''.format(",".join([str(i) for i in gw_genes])))
            homologs = cursor.fetchall()

            return homologs

def add_missing_orthologs(homologs):
    # starting hom_id is the first hom_id of the first homolog, keeps track of current cluster
    curr_hom_id = homologs[0][0]
    # will hold all homolog genes that are not from the new species
    homolog_set = []
    # holds all homolog genes from the new species
    new_species_homologs = []

    for h in homologs:

        # h is in current cluster
        if h[0] == curr_hom_id:
            # check if h is part of the new species
            if h[2] in [6, 10, 11]:
                new_species_homologs.append(h)
            # if h is not in new species, check if the gene is in the agr database. if it is,
            #    add to homolog_set
            else:
                # check if in agr database by getting ode_ref_id, converting that to gn_ref_id,
                #    and searching gn_gene with that agr_ref_id. if all queries are valid, gene is
                #    in agr.
                gw_gene_ref = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id ==
                                                               h[1], Geneweaver_Gene.sp_id ==
                                                               h[2], Geneweaver_Gene.gdb_id.in_([10,11,12,13,14,15,16])).first()
                if gw_gene_ref:
                    agr_ref = convert_ode_ref_to_agr(gw_gene_ref.ode_ref_id)
                    gene_in_agr = db.query(Gene).filter(Gene.gn_ref_id == agr_ref).first()
                    if gene_in_agr:
                        homolog_set.append(h)

        # h is not in current cluster, new homology set
        #    add new relations from new_species_homologs to rest of homolog_set
        #    reset homolog_set and new_species_homologs
        if h[0] != curr_hom_id:
            orthos = []
            from_agr_genes = {}

            # iterate through new_species_homologs to get the gn_id of each gene
            for n in new_species_homologs:
                n_gw_ref = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id ==
                                                               n[1], Geneweaver_Gene.sp_id ==
                                                               n[2], Geneweaver_Gene.gdb_id.in_([1,2,10])).first()
                n_agr_gene = db.query(Gene).filter(Gene.gn_ref_id == n_gw_ref.ode_ref_id).first()
                from_agr_genes[n[1]] = n_agr_gene.gn_id

            # get permutations of every combination between new_species_homologs and
            #    homolog_set
            pairs = list(itertools.product(new_species_homologs, homolog_set))

            for p in pairs:
                # from gene is first pairs object, to gene is second
                f = p[0]
                t = p[1]

                # get to_gene gn_ref_id
                t_gene_ref = db.query(Geneweaver_Gene).filter(Geneweaver_Gene.ode_gene_id ==
                                                                  t[1], Geneweaver_Gene.sp_id ==
                                                                  t[2], Geneweaver_Gene.gdb_id.in_(
                                                                  [10, 11, 12, 13, 14, 15, 16])).first()
                t_agr_ref = convert_ode_ref_to_agr(t_gene_ref.ode_ref_id)

                # check that to gene is in agr and geneweaver database
                if not t_gene_ref or not t_agr_ref:
                    continue
                agr_to_gene = db.query(Gene).filter(Gene.gn_ref_id == t_agr_ref).first()
                if not agr_to_gene:
                    continue

                to_gene = agr_to_gene.gn_id
                from_gene = from_agr_genes[f[1]]
                ort_is_best = True
                ort_is_best_revised = True
                ort_is_best_adjusted = True
                ort_num_possible_match_algorithms = 0
                ortho = Ortholog(from_gene=from_gene, to_gene=to_gene, ort_is_best=ort_is_best,
                                 ort_is_best_revised=ort_is_best_revised, ort_is_best_is_adjusted=
                                 ort_is_best_adjusted, ort_num_possible_match_algorithms=
                                 ort_num_possible_match_algorithms, ort_source_name = "Homologene")
                orthos.append(ortho)
            db.bulk_save_objects(orthos)
            db.commit()

            # reset homolog_set and new_species_homologs
            homolog_set = []
            new_species_homologs = []

            # add current gene to appropriate list
            if h[2] in [6, 10, 11]:
                new_species_homologs.append(h)
            else:
                homolog_set.append(h)

        # reset curr_hom_id
        curr_hom_id = h[0]

##########################################################################################

if __name__ == '__main__':
    add_missing_species()
    add_missing_genes()
    h = get_homolog_information()
    add_missing_orthologs(h)
    db.close()