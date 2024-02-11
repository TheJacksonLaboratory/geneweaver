# Geneweaver Ortholog Normalizer

An application to aid in normalizing homology data.

See [Aon: a service to augment Alliance Genome Resource data with additional species](https://bmcresnotes.biomedcentral.com/articles/10.1186/s13104-023-06577-8)
for more information.

Originally forked from [this code repository](https://bitbucket.org/sophie_kearney1/aon/src/master/).

### Development Setup
This repository uses [Poetry](https://python-poetry.org/) to manage dependencies and build packages.

To get started, clone the repository and install the dependencies:
```bash
git clone
cd geneweaver-ortholog-normalizer
poetry install
```

You can activate the virtual environment with:
```
poetry shell
```

#### Flask Server
The flask server can be started by running:
```bash
poetry run flask --app geneweaver.aon.app run
```


### CLI
The application has a command-line interface for running certain management commands.

- `gwaon`: /gwɑːn/ (noun) - A command-line interface for the Geneweaver Ortholog Normalizer.

### Loading The Database
You will need a postgresql database to load the ortholog data into. This has been
tested on Postgres 12, but should work on Postgres > 12.

#### Create the database schema
The database schema can be created by running the following command:
```bash
poetry run gwaon create-schema
```

#### Load the ortholog data
The ortholog data can be loaded by running the following command:
```bash
poetry run gwaon load agr
```

## Geneweaver Ortholog Normalizer Management

### Current Development Usage

The service connects to the geneweaver database to access the tables gene, species, and genedb.

Update database URLS in:
- flask/src/config.py
- flask/alembic.ini

If an agr database does not exist, create an empty database to store the agr data.

If the AGR tables have not been created, create them with alembic from the flask directory:
```
cd flask
alembic upgrade head
```

Download the most recent ORTHO_FILE from https://www.alliancegenome.org/downloads#orthology as TSV.
Make sure to set the `ORTHO_FILE` constant in flask/src/service.py to tell the module which file to load.

For now, database loading is achieved by calling the service.py module as a script. This will fill alg_algorithm,
gn_gene, hom_homology, ora_ortholog_algorithms, ort_otholog, and sp_species.
```
python flask/src/service.py
```

The agr database should be filled. The following command runs the service:
```
python flask/app.py
```

### Missing Information

If there is missing information, data can be added to the sp_species, gn_gene, and ort_ortholog
tables by running the add_missing_info.py script.

Make sure you have set the correct file paths to the flask/missing_info/missing_genes.csv and 
flask/missing_info/missing_orthologs.csv files.

Then run the following script:
```
python flask/src/add_missing_info.py
```

## Endpoint Migration Table

| **Old Endpoint**                                                                                                                    | **New Endpoint**                                                                   |
| ----------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| agr_to_geneweaver_species/{sp_id}:                                                                                                  | /species/{species_id}/geneweaver_id                                                |
| all_algorithms:                                                                                                                     | /algorithms                                                                        |
| all_genes:                                                                                                                          | /genes                                                                             |
| all_homology:                                                                                                                       | /homologs                                                                          |
| all_orthologs:                                                                                                                      | /orthologs                                                                         |
| all_species:                                                                                                                        | /species                                                                           |
| get_algorithm_by_name/{alg_name}:                                                                                                   | /algorithms?name={name}                                                            |
| get_from_gene_of_ortholog_by_id/{ort_id}:                                                                                           | /orthologs/{ortholog_id}/genes                                                     |
| get_gene_species_name/{ode_ref_id}/{ode_gene_id}:                                                                                   | _WIP_                                                                              |
| get_genes_by_ode_gene_id/{ode_ref_id}/{ode_gene_id}:                                                                                | _WIP_                                                                              |
| get_genes_by_prefix/{gn_prefix}:                                                                                                    | /genes?prefix={prefix}                                                             |
| get_genes_by_species/{sp_name}:                                                                                                     | /species/{species_id}/genes                                                        |
| get_homologous_ode_gene_ids_for_gene/{ode_ref_id}/{gdb_name}:                                                                       | _WIP_                                                                              |
| get_homology_by_gene/{gn_id}:                                                                                                       | /homologs?gene_id={gene_id}                                                        |
| get_homology_by_gene_and_source/{gn_id}/{hom_source_name}:                                                                          | /homologs?source={source}                                                          |
| get_homology_by_id/{hom_id}:                                                                                                        | /homologs/{homolog_id}                                                             |
| get_homology_by_id_and_source/{hom_id}/{hom_source_name}:                                                                           | /homologs/{homolog_id}?source={source}                                             |
| get_homology_by_id_and_species/{hom_id}/{sp_id}:                                                                                    | /homologs/{homolog_id}?species={species}                                           |
| get_homology_by_ode_gene_id/{ode_gene_id}:                                                                                          | _WIP_                                                                              |
| get_homology_by_ode_gene_ids:                                                                                                       | _WIP_                                                                              |
| get_homology_by_species/{sp_id}:                                                                                                    | /homologs?species={species}                                                        |
| get_intersect_by_homology:                                                                                                          | _WIP_                                                                              |
| get_ode_gene_by_gdb_id/{gdb_id}:                                                                                                    | _WIP_                                                                              |
| get_ode_gene_by_gene_id/{ode_gene_id}:                                                                                              | _WIP_                                                                              |
| get_ode_gene_by_species/{ode_gene_id}/{sp_name}:                                                                                    | _WIP_                                                                              |
| get_ode_genes_from_hom_id/{hom_id}/{target_gdb_id}:                                                                                 | _WIP_                                                                              |
| get_ort_id_if_gene_is_ortholog/{ode_gene_id}/{ode_ref_id}:                                                                          | _WIP_                                                                              |
| get_ortholog_by_algorithm/{alg_name}:                                                                                               | /orthologs?algorithm={algorithm}                                                   |
| get_ortholog_by_from_gene_and_gdb/{from_ode_gene_id}/{gdb_id}:                                                                      | _WIP_                                                                              |
| get_ortholog_by_from_species/{sp_name}:                                                                                             | /orthologs?from_species={species_id}                                               |
| get_ortholog_by_id/{ort_id}:                                                                                                        | /orthologs/{ortholog_id}                                                           |
| get_ortholog_by_to_and_from_species/{to_sp_name}/{from_sp_name}:                                                                    | /orthologs?to_species={species_id}&from_species={species_id}                       |
| get_ortholog_by_to_from_species_and_algorithm/{to_sp_name}/{from_sp_name}/{alg_name}:                                               | /orthologs?to_species={species_id}&from_species={species_id}&algorithm={algorithm} |
| get_ortholog_by_to_species/{sp_name}:                                                                                               | /orthologs?to_species={species_id}                                                 |
| get_orthologous_species/{ode_gene_id}/{ode_ref_id}:                                                                                 | _WIP_                                                                              |
| get_orthologs_by_from_gene/{ode_ref_id}/{ode_gene_id}:                                                                              | _WIP_                                                                              |
| get_orthologs_by_from_gene_and_best/{from_ode_ref_id}/{from_ode_gene_id}/{best}:                                                    | _WIP_                                                                              |
| get_orthologs_by_from_to_gene_and_best/{from_ode_ref_id}/{from_ode_gene_id}/{to_ode_ref_id}/{to_ode_gene_id}/{best}:                | _WIP_                                                                              |
| get_orthologs_by_from_to_gene_and_revised/{from_ode_ref_id}/{from_ode_gene_id}/{to_ode_ref_id}/{to_ode_gene_id}/{ort_best_revised}: | _WIP_                                                                              |
| get_orthologs_by_num_algorithms/{num}:                                                                                              | /orthologs?possible_match_algorithms={num_algorithms}                              |
| get_orthologs_by_symbol/{sym}/{orig_species}/{homologous_species}:                                                                  | _WIP_                                                                              |
| get_orthologs_by_to_and_from_gene/{from_ode_ref_id}/{from_ode_gene_id}/{to_ode_ref_id}/{to_ode_gene_id}:                            | _WIP_                                                                              |
| get_orthologs_by_to_gene/{ode_ref_id}/{ode_gene_id}:                                                                                | _WIP_                                                                              |
| get_sp_id_by_hom_id/{hom_id}:                                                                                                       | /homologs/{homolog_id}?species={species_id}                                        |
| get_species_by_id/{sp_id}:                                                                                                          | /species/{species_id}                                                              |
| get_species_homologs_list:                                                                                                          | /species/{species_id}/homologs                                                     |
| get_to_gene_of_ortholog_by_id/{ort_id}:                                                                                             | _WIP_                                                                              |
| id_convert_agr_to_ode/{gn_id}:                                                                                                      | /genes/{gene_id}/geneweaver_id                                                     |
| id_convert_ode_to_agr/{ode_gene_id}/{ode_ref_id}:                                                                                   | /geneweaver/genes/{geneweaver_id}/aon_id                                           |
| if_gene_has_homolog/{ode_gene_id}:                                                                                                  | _WIP_                                                                              |
| transpose_genes_by_species:                                                                                                         | _WIP_                                                                              |