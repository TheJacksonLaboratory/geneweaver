# AGR-Normalizer Summary

Alliance Genome Resource provides open-source gene ontology data for model organisms and humans that is routinely updated and is a widely known source for orthology mappings.
This service uses data from AGR's combined orthologs data found at https://www.alliancegenome.org/downloads#orthology

###AGR-normalizer database structure
- alg_algorithm: list of algorithms used in database with corresponding key
  - alg_id - primary key used in other tables to map back to alg_algorithm
  - alg_name - common name of algorithm
- gn_gene: contains information of all genes available in the service as well as links between gn_gene table and other tables
  - gn_id - local primary key used to map information in other tables back to a gene
  - gn_ref_id - identifier used in other databases outside this service
  - gn_prefix - short prefix to show what database the gene originated from (ex: WB = WormBase)
  - sp_id - id used in sp_species, shows the gene's species
- ora_ortholog_algorithms: maps the ort_ortholog table and the alg_algorithm table by the corresponding ids
  - ora_id - primary key unique for each relationship in table
  - alg_id - from alg_algorithm table
  - ort_id - from ort_ortholog table
- ort_ortholog: ortholog data mapping two genes together. Each row has a from_gene and a to_gene, and these 2 genes have an orthologous relationship.
  - ort_id - primary key for each orthologous relationship
  - from_gene - gn_id taken from gn_gene table, shows the from gene of each ortholog
  - to_gene - gn_id taken from gn_gene table, shows the to gene of each ortholog
  - ort_is_best - qualifier for if ortholog is best
  - ort_is_best_revised - qualifier for if ortholog is best revised
  - ort_is_best_is_adjusted - qualifier for if ortholog is best adjusted
  - ort_num_possible_match_algorithms - number of possible algorithms for that ortholog
  - ort_source_name - source of ortholog, either 'AGR' or 'Homologene'
- sp_species: available species in service
  - sp_id - primary key for each species, used for relationships between tables
  - sp_name - scientific name of species
  - sp_taxon_id - taxon id of species
- hom_homology: homolog clusters of ort_ortholog data
  - hom_id - label for each cluster, any row with the same hom_id is in one cluster of homologs
  - gn_id - foreign key to gn_gene table, labels gene for homolog row
  - sp_id - foreign key to sp_species table, labels species for homolog row
  - hom_source_name - source of homolog, either 'AGR' or 'Homologene'

###What is GeneWeaver?
website: https://www.geneweaver.org/
GeneWeaver is a web application to provide tools to anaylze functional genomics data from several different sources. 
GeneWeaver allows users to find relationships between genes across species and other factors. 
It also helps users discover conserved biological mechanisms as well as learn more about their biological function species to species.

###Connecting GeneWeaver database vs using GeneWeaver schema
This API requires information from 3 tables in the GeneWeaver database (gene, genedb, and species), which can be access two ways:
- Direct access to GeneWeaver database - two engines for each database are configured so the service can reach both.
- Creation of a separate GeneWeaver schema - the required tables are created and filled within the agr database.

###GeneWeaver Required tables:
- gene: all genes available in the GeneWeaver database
  - ode_gene_id - gene id, can be repeated
  - ode_ref_id - reference id to specific database the gene came from
  - gdb_id - gdb_id from genedb, shows database source of gene
  - sp_id - sp_id from species, shows species of gene
  - ode_pref - 
  - ode_data - date added
  - old_ode_gene_ids -
- genedb: gene database information, each gene is linked here so more information about its database can be found
  - gdb_id - primary key, used for relationships between tables
  - gdb_name - name of database
  - sp_id - foreign key to sp_species table, 0 if not related to specific species
  - gdb_shortname - short name or prefix for database
  - gdb_date - 
  - gdb_precision - measure of how precise gene database is
  - gdb_linkout_url -
- species: species data
  - sp_id - primary key, used for relationships between tables
  - sp_name - scientific name of species
  - sp_taxid - taxon id of species
  - sp_ref_gdb_id - gdb_id of species
  - sp_date - 
  - sp_biomart_info - 
  - sp_source_info - more information about source of species

###Installing packages
Ensure that you have activated your virtual environment for this service. To install all the required packages, run the following code from the base directory:
```
pip install -r requirements.txt
```

###Creating the agr database
Note: Before running any of the following code, ensure that your current directory is the base directory of agr-normalizer.
Additionally, all required packages should be installed in your virtual environment.

1.  **Creating the Database:** The database, tables, columns, and corresponding constraints can be created automatically if one does not exist already.
   If the alembic commands have already been run, running them again will not change any of the database structure.
```
cd flask
alembic upgrade head
```
2. **AGR Ortholog Data:** Download the most recent ORTHO_FILE from https://www.alliancegenome.org/downloads#orthology as TSV.
   Add this file to your agr-normalizer directory. Update the `ORTHO_FILE` constant in flask/src/service.py to tell the module which file to load.
3. **Loading the Data:** The agr database is filled using the flask/src/service.py module. Once this is run, the alg_algorithm, gn_gene, ora_ortholog_algorithms, ort_ortholog, and sp_species tables will be filled.
```
python flask/src/service.py
```

###Running the service
Running the service locally will connect to the database created above to query and nomalize information. The following command runs the service:
```
python flask/app.py
```

###Species 
The AGR Ortholog data provides ortholog information for the species Mus musculus, Rattus norvegicus, Saccharomyces cerevisiae, Caenorhabditis elegans, Drosophila melanogaster, Danio rerio, and Homo sapiens.

###Adding Missing Data
If there is missing information, data can be added to the sp_species, gn_gene, and ort_ortholog
tables by running the add_missing_info.py script.

Make sure you have set the correct file paths to the flask/missing_info/missing_genes.csv and 
flask/missing_info/missing_orthologs.csv files.

Then run the following script:
```
python flask/src/add_missing_info.py
```

###Endpoints
All current endpoints use ode_gene_id and ode_ref_id to reference genes.
- Whole table queries - the following endpoints return all the information in each table
  - all_algorithms = returns all algorithm object information
  - all_orthologs = returns all ortholog object information
  - all_genes = returns all gene object information
  - all_species = returns all species object information
  - all_homology = returns all homology object information
- Query by id - each table has a unique primary key that can be used to find a specific row's infomration
  - get_ortholog_by_id = returns orthologs with ort_id
  - get_species_by_id = returns species with sp_id
  - get_ode_gene_by_gene_id = returns orthologs with ode_gene_id
  - get_homology_by_id = = returns homologs with hom_id
- Query by One Parameter - these endpoints can query by one column or one parameter of the table through related tables
  - get_orthologs_by_from_gene = returns orthologs from a specified gene
  - get_orthologs_by_to_gene = returns orthologs to a specified gene
  - get_genes_by_prefix = return all genes with specified gn_prefix
  - get_genes_by_species = returns ode_gene_ids for genes of a certain sp_name
  - get_orthologs_by_num_algoritms = return all orthologs with specified ort_num_possible_match_algorithms
  - get_ortholog_by_algorithm = return all orthologs that use a specified algorithm (alg_name)
  - get_ortholog_by_from_species = return all orthologs from given species (sp_name)
  - get_ortholog_by_to_species = return all orthologs to given species (sp_name)
  - get_homology_by_gene = returns all homology rows with given gn_id
  - get_homology_by_species = returns all homology rows with given sp_id
  - get_ode_gene_by_gdb_id = return all ode_genes with the specified gdb_id
  - get_ode_gene_by_gene_id = return all ode_genes with the same ode_gene_id
  - get_algorithm_by_name = returns algorithm object with specified name
- Query by Multiple Parameters - these endpoints can query by multiple columns or multiple parameters of the table through related tables
  - get_orthologs_by_to_and_from_gene = returns all orthologs to and from the specified genes (from_gene and to_gene)
  - get_orthologs_by_from_gene_and_best = returns all orthologs from the specified gene filtered by is_best (from_gene, is_best)
  - get_orthologs_by_from_to_gene_and_best = returns all orthologs to and from the specified genes filtered by is_best (to_gene, from_gene, is_best)
  - get_orthologs_by_from_to_gene_and_revised = returns all orthologs to and from the specified genes filtered by is_best_revised (to_gene, from_gene, is_best_revised)
  - get_ortholog_by_to_and_from_species = return all orthologs to and from given species (sp_name)
  - get_ortholog_by_to_from_species_and_algorithm = return all orthologs to and from given species using the given algorithm
  - get_homology_by_id_and_species = returns all homology rows with given hom_id and sp_id
  - get_homology_by_id_abnd_source = returns all homology rows with given hom_id and hom_source_name
  - get_homology_by_gene_and_source = returns all homology rows with given gn_id and hom_source_name
  - get_ode_gene_by_species = return all genes with matching ode_gene_id and species (ode_gene_id, sp_name)
  - get_genes_by_ode_gene_id = return gene with specified ode_ref_id and ode_gene_id
- Return one parameter of selected row
  - get_from_gene_of_ortholog_by_id = return from_gene object of an ortholog
  - get_to_gene_of_ortholog_by_id = return to_gene object of an ortholog
  - get_gene_species_name = returns the species name of a specified gene
- Converter endpoints
  - agr_to_geneweaver_species = translate an AGR species id to the corresponding species id in the geneweaver database
  - id_convert_agr_to_ode = converts an agr gene id to the corresponding ode_gene_id
  - id_convert_ode_to_agr = converts an ode gene id to the corresponding agr gene id
- AGR-GW Integration Endpoints
  - get_id_by_from_gene = returns the ortholog id filtering by the ortholog from gene, including the gdb_id
  - get_ortholog_by_from_gene_and_gdb = returns to gene ode_gene_id and ode_ref_id of any ortholog with the from gene matching the given ode_gene_id and to gene matching the gdb_id
  - if_ode_gene_has_ortholog = check if ode gene is an ortholog
  - get_intersect_by_orthology = finds the genes that intersect between two genesets using the orthology table
  - transpose_genes_by_homology = finds the homologous genes of one geneset and returns any homolog genes that are of the given species