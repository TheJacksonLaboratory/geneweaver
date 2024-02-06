"""
This code takes the information from the Orthology file, parses it, and adds it to the database
"""
from itertools import islice, chain
import sys, requests, os, gzip, shutil
from geneweaver.aon.database import SessionLocal
from geneweaver.aon.models import Gene, Species, Ortholog, Algorithm, Homology

# get the most recent release from AGR's API
release = (requests.get("https://www.alliancegenome.org/api/releaseInfo")).json()
version = release["releaseVersion"]


argument_length = len(sys.argv)
if argument_length > 1:
    if sys.argv[1] == "-f":
        file_name = sys.argv[2]
        data_url = f"https://download.alliancegenome.org/{version}/ORTHOLOGY-ALLIANCE/COMBINED/{file_name}"
        request = requests.get(data_url, allow_redirects=True)

        if request.status_code == 200:
            print(f"{file_name} downloaded successfully.")

            # download file
            open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv.gz', 'wb').write(request.content)

            # unzip file
            with gzip.open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv.gz', 'rb') as f_in:
                with open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv', 'wb') as f_out:
                    shutil.copyfileobj(f_in, f_out)

        else:
            print(f"An error occurred when downloading {file_name}. Please check the file name.")
            exit()
else:
    # arbitrary limit to prevent infinite loop if the path is incorrect
    version_limit = 50

    # starting with version 1, the program will try each version of the file until finding the version not yet available
    #     and will use that one as the most recent data
    version_number = 1
    data_url = f"https://download.alliancegenome.org/{version}/ORTHOLOGY-ALLIANCE/COMBINED/ORTHOLOGY-ALLIANCE_COMBINED_{version_number}.tsv.gz"
    request = requests.get(data_url, allow_redirects=True)

    # loop through all the valid versions
    while (request.status_code == 200 and version_number < version_limit):
        version_number += 1
        data_url = f"https://download.alliancegenome.org/{version}/ORTHOLOGY-ALLIANCE/COMBINED/ORTHOLOGY-ALLIANCE_COMBINED_{version_number}.tsv.gz"
        request = requests.get(data_url, allow_redirects=True)

    if version_number == version_limit-1:
        print("The maximum number of versions was tried. Please check the file path for downloading the orthology file at https://www.alliancegenome.org/downloads.")
        exit()

    data_url = f"https://download.alliancegenome.org/{version}/ORTHOLOGY-ALLIANCE/COMBINED/ORTHOLOGY-ALLIANCE_COMBINED_{version_number-1}.tsv.gz"
    request = requests.get(data_url, allow_redirects=True)

    # download file
    open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv.gz', 'wb').write(request.content)

    # unzip file
    with gzip.open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv.gz', 'rb') as f_in:
        with open(f'{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv', 'wb') as f_out:
            shutil.copyfileobj(f_in, f_out)

ORTHO_FILE = f"{os.path.dirname(os.path.abspath(__file__))}/AGR_Orthology_Data.tsv"

db = SessionLocal()


def read_file_by_line(file):
    for line in file:
        yield line


def read_n_lines(file, n):
    iterator = iter(read_file_by_line(file))
    for first in iterator:
        yield chain([first], islice(iterator, n - 1))


def species_id_from_taxon_id(taxon_id):
    id_num = ((taxon_id).split(":"))[1]
    return db.query(Species).filter(Species.sp_taxon_id == id_num).first().sp_id


def get_algorithm_by_name(name):
    return db.query(Algorithm).filter(Algorithm.alg_name == name).first()


def init_species():
    heading_size = 15
    with open(ORTHO_FILE, 'r') as f:
        for i in range(heading_size):
            discard = f.readline()
        header = f.readline()

        species = set()
        for line in read_file_by_line(f):
            data = line.split('\t')
            name = data[3]
            taxon_id = ((data[2]).split(":"))[1]
            species.add((taxon_id, name))

        print(species)
        #
        # db.bulk_save_objects([
        #     Species(sp_name=s[1], sp_taxon_id=s[0])
        #     for s in species
        # ])
        # db.commit()


def add_genes():
    heading_size = 15
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
            genes[sp[0]] = (sp[0].split(':')[0], species_id_from_taxon_id(sp[2]))
            # The second gene
            genes[sp[4]] = (sp[4].split(':')[0], species_id_from_taxon_id(sp[6]))

        db.bulk_save_objects([
            Gene(gn_ref_id=key, gn_prefix=value[0], sp_id=value[1])
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
            Algorithm(alg_name=algo)
            for algo in algos
        ])
        db.commit()


def add_ortholog_batch(batch):
    is_best_map = {
        'Yes': True,
        'No': False,
        'Yes_Adjusted': True
    }

    for line in batch:
        spl = line.split('\t')
        # get gene object of from gene and to gene
        gene1 = db.query(Gene).filter(Gene.gn_ref_id == spl[0]).first()
        gene2 = db.query(Gene).filter(Gene.gn_ref_id == spl[4]).first()

        # determine qualifiers
        is_best = spl[11].strip()
        is_best_is_adjusted = False
        if is_best == 'Yes_Adjusted':
            is_best_is_adjusted = True
        is_best = is_best_map[is_best]
        is_best_revised = is_best_map[spl[12].strip()]
        num_algo = int(spl[10].strip())

        ortholog = Ortholog(from_gene=gene1.gn_id, to_gene=gene2.gn_id,
                            ort_is_best=is_best, ort_is_best_revised=is_best_revised,
                            ort_is_best_is_adjusted=is_best_is_adjusted,
                            ort_num_possible_match_algorithms=num_algo,
                            ort_source_name="AGR")

        # add to ora_ortholog_algorithms
        # algorithms = [algorithms_dict[algo] for algo in spl[8].split('|')]
        algorithms = [get_algorithm_by_name(algo) for algo in spl[8].split('|')]
        for algorithm in algorithms:
            ortholog.algorithms.append(algorithm)
        db.add(ortholog)
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
            # add 1000 orthologs at a time unil end of file
            add_ortholog_batch(batch)
            i += 1
            if batches_to_process != -1 and i > batches_to_process:
                break

    db.close()


def add_homology():
    orthos = db.query(Ortholog)
    curr_hom_id = 0

    # format of existing_cluster_key items - gn_id:hom_id
    # used to keep track of what cluster each gene belongs to
    existing_cluster_key = {}
    # format of homologs items - hom_id:[homologs genes]
    # used to build clusters of genes with a unique hom_id
    homologs = {}
    # format of source_key items - gn_id:"hom_source_name"
    # used to store where each gene's orthologous relationship to the cluster came from
    source_key = {}
    for o in orthos:
        # check if either gene is already a member of a cluster and if true, add
        #    the corresponding gene to that cluster
        if o.from_gene in existing_cluster_key.keys():
            hom_id = existing_cluster_key[o.from_gene]
            homologs[hom_id].append(o.to_gene)
            existing_cluster_key[o.to_gene] = curr_hom_id
            source_key[o.to_gene] = o.ort_source_name
        if o.to_gene in existing_cluster_key.keys():
            hom_id = existing_cluster_key[o.to_gene]
            homologs[hom_id].append(o.from_gene)
            existing_cluster_key[o.from_gene] = curr_hom_id
            source_key[o.from_gene] = o.ort_source_name

        # check if neither gene belonds to a cluster and if true, create a new cluster
        #    with a new hom_id and add both genes to that cluster
        if o.to_gene not in existing_cluster_key.keys() and o.from_gene not in existing_cluster_key.keys():
            curr_hom_id += 1
            homologs[curr_hom_id] = [o.from_gene, o.to_gene]
            existing_cluster_key[o.to_gene] = curr_hom_id
            existing_cluster_key[o.from_gene] = curr_hom_id
            source_key[o.to_gene] = o.ort_source_name
            source_key[o.from_gene] = o.ort_source_name

    for hom_id in homologs.keys():
        # store all homolog objects for each hom_id
        homolog_objects = []
        genes = homologs[hom_id]
        # remove duplicate genes
        genes = list(set(genes))
        for g in genes:
            sp_id = (db.query(Gene).filter(Gene.gn_id == g).first()).sp_id
            hom = Homology(hom_id=hom_id, hom_source_name=source_key[g],
                            gn_id=g, sp_id=sp_id)
            homolog_objects.append(hom)
        db.bulk_save_objects(homolog_objects)
        db.commit()


if __name__ == "__main__":
    init_species()
    #add_algorithms()
    #add_genes()
    #add_orthologs(1000)
    #add_homology()
