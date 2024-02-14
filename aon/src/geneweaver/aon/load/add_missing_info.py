from csv import reader

from geneweaver.aon.core.database import SessionLocal
from geneweaver.aon.models import Gene, Ortholog, Species

db = SessionLocal()

gene_file_path = "missing_info/missing_genes.csv"
ortholog_file_path = "missing_info/missing_orthologs.csv"


def add_missing_species():
    """:description: adds three missing species to sp_species table."""
    species_dict = {
        "Gallus gallus": 9031,
        "Canis familiaris": 9615,
        "Macaca mulatta": 9544,
    }
    i = 8
    for s in species_dict.keys():
        species = Species(sp_id=i, sp_name=s, sp_taxon_id=species_dict[s])
        db.add(species)
        i += 1
    db.commit()


def add_missing_genes(file_path):
    """:param: file_path - file path to file missing_genes.csv that contains all missing genes
            to be added to the database
    :description: adds genes of the three missing species to the gn_gene table
    """
    with open(file_path, "r") as f:
        csv_reader = reader(f)
        next(csv_reader)
        gene_file_list = list(csv_reader)

    gene_objects = []
    for g in gene_file_list:
        gene = Gene(gn_id=int(g[0]), gn_ref_id=g[1], gn_prefix=g[2], sp_id=int(g[3]))
        gene_objects.append(gene)
    db.bulk_save_objects(gene_objects)
    db.commit()


def add_missing_orthologs(file_path):
    """:param: file_path - file path to file missing_orthologs.csv that contains all missing
            orthologs to be added to the database
    :description: adds orthologs of the three missing species to the gn_gene table
    """
    with open(file_path, "r") as f:
        csv_reader = reader(f)
        next(csv_reader)
        ortholog_file_list = list(csv_reader)

    ortholog_objects = []

    for o in ortholog_file_list:
        ortholog = Ortholog(
            ort_id=int(o[0]),
            from_gene=int(o[1]),
            to_gene=int(o[2]),
            ort_is_best=bool(o[3]),
            ort_is_best_revised=bool(o[4]),
            ort_is_best_is_adjusted=bool(o[5]),
            ort_num_possible_match_algorithms=int(o[6]),
            ort_source_name=o[7],
        )
        ortholog_objects.append(ortholog)

    db.bulk_save_objects(ortholog_objects)
    db.commit()


if __name__ == "__main__":
    add_missing_species()
    add_missing_genes(gene_file_path)
    add_missing_orthologs(ortholog_file_path)
