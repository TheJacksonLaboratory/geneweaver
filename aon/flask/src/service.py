"""
The code that actually performs the work
"""
from itertools import islice, chain

from src.database import SessionLocal
from src.models import Gene, Species, Ortholog, Algorithm

db = SessionLocal()

ORTHO_FILE = "/Users/sophiekearney/PycharmProjects/agr-normalizer/agr-normalizer/" \
             "ORTHOLOGY-ALLIANCE_COMBINED_37.tsv"

def read_file_by_line(file):
    for line in file:
        yield line

def read_n_lines(file, n):
    iterator = iter(read_file_by_line(file))
    for first in iterator:
        yield chain([first], islice(iterator, n - 1))

def get_algorithm_by_name(name):
    return db.query(Algorithm).filter(Algorithm.name == name).first()

def add_ortholog_batch(batch):
    algorithms_dict = {
        'PANTHER': get_algorithm_by_name('PANTHER'),
        'ZFIN': get_algorithm_by_name('ZFIN'),
        'Ensembl Compara': get_algorithm_by_name('Ensembl Compara'),
        'PhylomeDB': get_algorithm_by_name('PhylomeDB'),
        'OrthoFinder': get_algorithm_by_name('OrthoFinder'),
        'InParanoid': get_algorithm_by_name('InParanoid'),
        'Roundup': get_algorithm_by_name('Roundup'),
        'OrthoInspector': get_algorithm_by_name('OrthoInspector'),
        'OMA': get_algorithm_by_name('OMA'),
        'Hieranoid': get_algorithm_by_name('Hieranoid'),
        'HGNC': get_algorithm_by_name('HGNC'),
        'TreeFam': get_algorithm_by_name('TreeFam')
    }

    is_best_map = {
        'Yes': True,
        'No': False,
        'Yes_Adjusted': True
    }

    orthologs = []
    for line in batch:
        spl = line.split('\t')
        gene1 = db.query(Gene).filter(Gene.reference_id == spl[0]).first()
        gene2 = db.query(Gene).filter(Gene.reference_id == spl[4]).first()

        is_best = spl[11].strip()
        is_best_is_adjusted = False
        if is_best == 'Yes_Adjusted':
            is_best_is_adjusted = True
        is_best = is_best_map[is_best]
        is_best_revised = is_best_map[spl[12].strip()]
        num_algo = int(spl[10].strip())

        ortholog = Ortholog(from_gene=gene1.id, to_gene=gene2.id,
                            is_best=is_best, is_best_revised=is_best_revised,
                            is_best_is_adjusted=is_best_is_adjusted,
                            num_possible_match_algorithms=num_algo)

        algorithms = [algorithms_dict[algo] for algo in spl[8].split('|')]
        for algorithm in algorithms:
            ortholog.algorithms.append(algorithm)

        #orthologs.append(ortholog)

    #db.bulk_save_objects(orthologs)
    db.commit()


def init_species():
    species = [
        (10090, 'Mus musculus'),
        (10116, 'Rattus norvegicus'),
        (559292, 'Saccharomyces cerevisiae'),
        (6239, 'Caenorhabditis elegans'),
        (7227, 'Drosophila melanogaster'),
        (7955, 'Danio rerio'),
        (9606, 'Homo sapiens')
    ]
    db.bulk_save_objects([
        Species(name=s[1], taxon_id=s[0])
        for s in species
    ])
    db.commit()


def add_orthologs(batch_size, batches_to_process=-1):
    heading_size = 15

    with open(ORTHO_FILE, 'r') as f:
        for i in range(heading_size):
            discard = f.readline()
            print(f"DISCARDING --[{discard}]" + discard)
        header = f.readline()
        print(f"HEADER: {header}")

        i = 1
        for batch in read_n_lines(f, batch_size):
            add_ortholog_batch(batch)
            i += 1
            if batches_to_process != -1 and i > batches_to_process:
                break

    db.close()

def species_id_from_taxon_id(taxon_id):
    return db.query(Species).filter(Species.taxon_id == taxon_id).first().id

def add_genes():
    heading_size = 15

    species = {
        'NCBITaxon:10090': species_id_from_taxon_id(10090),
        'NCBITaxon:10116': species_id_from_taxon_id(10116),
        'NCBITaxon:559292': species_id_from_taxon_id(559292),
        'NCBITaxon:6239': species_id_from_taxon_id(6239),
        'NCBITaxon:7227': species_id_from_taxon_id(7227),
        'NCBITaxon:7955': species_id_from_taxon_id(7955),
        'NCBITaxon:9606': species_id_from_taxon_id(9606)
    }

    with open(ORTHO_FILE, 'r') as f:
        for i in range(heading_size):
            discard = f.readline()
            print(f"DISCARDING --[{discard}]" + discard)
        header = f.readline()
        print(f"HEADER: {header}")

        genes = {}
        for line in read_file_by_line(f):
            sp = line.split('\t')
            # The first gene
            # key: reference_id, value: (reference_prefix, species_id)
            genes[sp[0]] = (sp[0].split(':')[0], species[sp[2]])
            # The second gene
            genes[sp[4]] = (sp[4].split(':')[0], species[sp[6]])

        db.bulk_save_objects([
            Gene(reference_id=key, id_prefix=value[0], species=value[1])
            for key, value in genes.items()
        ])
        db.commit()

    db.close()

def add_algorithms():
    heading_size = 15
    with open(ORTHO_FILE, 'r') as f:
        for i in range(heading_size):
            discard = f.readline()
            print(f"DISCARDING --[{discard}]" + discard)
        header = f.readline()
        print(f"HEADER: {header}")

        algos = set()
        for line in read_file_by_line(f):
            sp = line.split('\t')
            for algo in sp[8].split('|'):
                algos.add(algo)

        db.bulk_save_objects([
            #Algorithm(name=algo)
            #for algo in algos
        ])
        db.commit()


if __name__ == "__main__":
    #init_species()
    add_algorithms()
    #add_genes()
    add_orthologs(1000)
