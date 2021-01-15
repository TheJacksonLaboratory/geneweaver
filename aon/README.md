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
```shell script
# Use the .env.example to get started
sed '/^#/ d' < .env.example > .env
echo -e "SECRET_KEY=$(LC_ALL=C tr -dc A-Za-z0-9 </dev/urandom | head -c 50)" >> .env
# Edit the .env file for your environment
vim .env
```


## Geneweaver Ortholog Normalizer Management

### Current Development Usage
For now, database loading is achieved by calling the service.py module as a script:
```
python flask/service.py
```

Make sure to set the `ORTHO_FILE` constant to tell the module which file to load.


### Service Usage
The flask service is managed with the manage.py module. Depending on the template options you selected, some features 
may be unavailable.

It can be accessed with either:
```bash
python -m manage --help
```
or
```bash
python manage.py --help
```

```bash
usage: manage.py [-?] {run,db,start_workers,test,test_xml,shell,runserver} ...

positional arguments:
  {run,db,start_workers,test,test_xml,shell,runserver}
    run                 The main entrypoint to running the app :return: None
    celery              Start the celery worker(s)
    test                Run unit tests
    test_xml            Runs the unit tests specifically for bamboo CI/CD
    shell               Runs a Python shell inside Flask application context.
    runserver           Runs the Flask development server i.e. app.run()

optional arguments:
  -?, --help            show this help message and exit

```

-----
<sub>Created from the [micro-flask cookiecutter template](https://bitbucket.jax.org/projects/PT/repos/micro-flask/browse) 
version 0.0.4 on Wed, Dec 16 2020 at 16:16 PM</sub>

<sub>This code is maintained by alexander.berger@jax.org. The template was created by Alexander Berger <alexander.berger@jax.org></sub>
