# Geneweaver Ortholog Normalizer

An application to aid in normalizing homology data.

### Setup
If you elected to have cookiecutter create your virtual environment for you, all you need to run is:
```
source <name_of_virtual_environemtn>/bin/activate
```
Otherwise, you should first create a virtual environment:
```
python3 -m venv venv.gon
source venv.gon/bin/activate
pip install -r requirements.txt
pip freeze > requirements.txt
```

#### Config
For local development, create and edit an `.env` file:
```
# Use the .env.example to get started
sed '/^#/ d' < .env.example > .env
echo -e "SECRET_KEY=$(LC_ALL=C tr -dc A-Za-z0-9 </dev/urandom | head -c 50)" >> .env
# Edit the .env file for your environment
vim .env
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


-----
<sub>Created from the [micro-flask cookiecutter template](https://bitbucket.jax.org/projects/PT/repos/micro-flask/browse) 
version 0.0.4 on Wed, Dec 16 2020 at 16:16 PM</sub>

<sub>This code is maintained by alexander.berger@jax.org. The template was created by Alexander Berger <alexander.berger@jax.org></sub>
