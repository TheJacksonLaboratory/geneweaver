"""Functions used to load the database."""
from itertools import chain, islice

from geneweaver.core import enum
from geneweaver.aon.models import Algorithm, Gene, Homology, Ortholog, Species
from sqlalchemy.sql import text
from sqlalchemy.orm import Session

TAXON_ID_MAP = {
    enum.Species.RATTUS_NORVEGICUS: 10116,
    enum.Species.DANIO_RERIO: 7955,
    enum.Species.GALLUS_GALLUS: 9031,
    enum.Species.MUS_MUSCULUS: 10090,
    enum.Species.DROSOPHILA_MELANOGASTER: 7227,
    enum.Species.CANIS_FAMILIARIS: 9615,
    enum.Species.HOMO_SAPIENS: 9606,
    enum.Species.CAENORHABDITIS_ELEGANS: 6239,
    enum.Species.SACCHAROMYCES_CEREVISIAE: 559292,
    enum.Species.MACACA_MULATTA: 9544,
}


def read_file_by_line(file) -> str:
    """Read a file line by line.

    :param file: file to read
    :return: generator of lines
    """
    for line in file:
        yield line


def read_n_lines(file, n: int) -> chain:
    """Read n lines from a file.

    :param file: file to read
    :param n: number of lines to read
    :return: generator of n lines
    """
    iterator = iter(read_file_by_line(file))
    for first in iterator:
        yield chain([first], islice(iterator, n - 1))


def species_id_from_taxon_id(db: Session, taxon_id):
    """Get the species id from the taxon id.

    :param db: database session
    :param taxon_id: taxon id
    :return: species id
    """
    id_num = int(((taxon_id).split(":"))[1])
    return db.query(Species).filter(Species.sp_taxon_id == id_num).first().sp_id


def get_species_to_taxon_id_map(db: Session) -> dict:
    """Get the species to taxon id map.

    :param db: database session
    :return: species to taxon id map
    """
    species = db.query(Species).all()
    return {s.sp_taxon_id: s.sp_id for s in species}


def get_algorithm_by_name(db: Session, name: str):
    """Get the algorithm by name.

    :param db: database session
    :param name: name of the algorithm
    """
    return db.query(Algorithm).filter(Algorithm.alg_name == name).first()


def get_algorithm_name_map(db: Session) -> dict:
    """Get the algorithm name map.

    :param db: database session
    :return: algorithm name map
    """
    algorithms = db.query(Algorithm).all()
    return {a.alg_name: a for a in algorithms}


def get_gene_gn_ref_id_map(db: Session) -> dict:
    """Get the gene gn ref id map.

    :param db: database session
    :return: gene gn ref id map
    """
    genes = db.query(Gene).all()
    return {g.gn_ref_id: g for g in genes}


def get_gene_gn_id_sp_id_map(db: Session) -> dict:
    """Get the gene gn id map.

    :param db: database session
    :return: gene gn id map
    """
    genes = db.query(Gene).all()
    return {g.gn_id: g.sp_id for g in genes}


def init_species(db: Session, ortho_file: str, schema_name: str) -> None:
    """Initialize the species table.

    :param db: database session
    :param ortho_file: file to read
    """
    # Add geneweaver species
    for species in enum.Species:
        if species != enum.Species.ALL:
            sp = Species(
                sp_id=int(species),
                sp_name=str(species).title(),
                sp_taxon_id=TAXON_ID_MAP[species],
            )
            db.add(sp)

    max_id = max([int(species) for species in enum.Species])
    db.execute(
        text(
            f"ALTER SEQUENCE {schema_name}.sp_species_sp_id_seq RESTART WITH {max_id + 1}"
        )
    )
    db.commit()

    heading_size = 15
    with open(ortho_file, "r") as f:
        for _i in range(heading_size):
            f.readline()
        f.readline()

        non_gw_species = set()
        for line in read_file_by_line(f):
            data = line.split("\t")
            name = data[3].title()
            taxon_id = ((data[2]).split(":"))[1]

            try:
                _ = enum.Species(name)
            except ValueError:
                try:
                    _ = enum.Species(name.capitalize())
                except ValueError:
                    non_gw_species.add((name, int(taxon_id)))

        db.bulk_save_objects(
            [
                Species(sp_name=name, sp_taxon_id=taxon_id)
                for name, taxon_id in non_gw_species
            ]
        )
        db.commit()


def add_genes(db: Session, ortho_file: str) -> None:
    """Add genes to the database.

    :param db: database session
    :param ortho_file: file to read
    """
    heading_size = 15
    with open(ortho_file, "r") as f:
        for _i in range(heading_size):
            f.readline()
        f.readline()

        genes = {}
        species_taxon_map = get_species_to_taxon_id_map(db)
        for line in read_file_by_line(f):
            sp = line.split("\t")
            # The first gene
            # key: reference_id, value: (reference_prefix, species_id)
            genes[sp[0]] = (
                sp[0].split(":")[0],
                species_taxon_map[int(sp[2].split(":")[1])],
            )

            # The second gene
            genes[sp[4]] = (
                sp[4].split(":")[0],
                species_taxon_map[int(sp[6].split(":")[1])],
            )

        db.bulk_save_objects(
            [
                Gene(gn_ref_id=key, gn_prefix=value[0], sp_id=value[1])
                for key, value in genes.items()
            ]
        )
        db.commit()

    db.close()


def add_algorithms(db: Session, ortho_file: str):
    """Add algorithms to the database.

    :param db: database session
    :param ortho_file: file to read
    """
    heading_size = 15
    with open(ortho_file, "r") as f:
        for _i in range(heading_size):
            f.readline()
        f.readline()

        algos = set()
        for line in read_file_by_line(f):
            sp = line.split("\t")
            for algo in sp[8].split("|"):
                algos.add(algo)

        db.bulk_save_objects([Algorithm(alg_name=algo) for algo in algos])
        db.commit()


def add_ortholog_batch(db: Session, batch):
    """Add a batch of orthologs to the database.

    :param db: database session
    :param batch: batch of orthologs to add
    """
    is_best_map = {"Yes": True, "No": False, "Yes_Adjusted": True}

    orthologs = []
    algorithm_name_map = get_algorithm_name_map(db)
    gn_ref_id_map = get_gene_gn_ref_id_map(db)

    for line in batch:
        spl = line.split("\t")
        # get gene object of from gene and to gene

        gene1 = gn_ref_id_map[spl[0]]
        gene2 = gn_ref_id_map[spl[4]]

        # determine qualifiers
        is_best = spl[11].strip()
        is_best_is_adjusted = False
        if is_best == "Yes_Adjusted":
            is_best_is_adjusted = True
        is_best = is_best_map[is_best]
        is_best_revised = is_best_map[spl[12].strip()]
        num_algo = int(spl[10].strip())

        ortholog = Ortholog(
            from_gene=gene1.gn_id,
            to_gene=gene2.gn_id,
            ort_is_best=is_best,
            ort_is_best_revised=is_best_revised,
            ort_is_best_is_adjusted=is_best_is_adjusted,
            ort_num_possible_match_algorithms=num_algo,
            ort_source_name="AGR",
        )

        # add to ora_ortholog_algorithms
        algorithms = [algorithm_name_map[algo] for algo in spl[8].split("|")]
        for algorithm in algorithms:
            ortholog.algorithms.append(algorithm)

        orthologs.append(ortholog)
    db.add_all(orthologs)
    db.commit()


def add_orthologs(db: Session, ortho_file, batch_size, batches_to_process=-1) -> None:
    """Add orthologs to the database.

    :param db: database session
    :param ortho_file: file to read
    :param batch_size: size of the batch
    :param batches_to_process: number of batches to process
    """
    heading_size = 15

    with open(ortho_file, "r") as f:
        for i in range(heading_size):
            f.readline()
        f.readline()

        i = 1
        for batch in read_n_lines(f, batch_size):
            # add 1000 orthologs at a time unil end of file
            add_ortholog_batch(db, batch)
            i += 1
            if batches_to_process != -1 and i > batches_to_process:
                break


def get_ortholog_batches(ortho_file, batch_size, batches_to_process=-1):
    """Add orthologs to the database.

    :param db: database session
    :param ortho_file: file to read
    :param batch_size: size of the batch
    :param batches_to_process: number of batches to process
    """
    heading_size = 15

    with open(ortho_file, "r") as f:
        for i in range(heading_size):
            f.readline()
        f.readline()

        i = 1
        for batch in read_n_lines(f, batch_size):
            # add 1000 orthologs at a time unil end of file
            yield batch
            i += 1
            if batches_to_process != -1 and i > batches_to_process:
                break


def add_homology(db: Session) -> None:
    """Add homology to the database.

    :param db: database session
    """
    orthos = db.query(Ortholog)
    gene_gn_id_sp_id_map = get_gene_gn_id_sp_id_map(db)
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

        # check if neither gene belongs to a cluster and if true, create a new cluster
        #    with a new hom_id and add both genes to that cluster
        if (
            o.to_gene not in existing_cluster_key.keys()
            and o.from_gene not in existing_cluster_key.keys()
        ):
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
            sp_id = gene_gn_id_sp_id_map[g]
            hom = Homology(
                hom_id=hom_id, hom_source_name=source_key[g], gn_id=g, sp_id=sp_id
            )
            homolog_objects.append(hom)
        db.bulk_save_objects(homolog_objects)
        db.commit()
