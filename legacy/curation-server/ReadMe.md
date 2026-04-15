# GeneWeaver Development Notes

last update: 8/05/2016

---

## Useful and/or Necessary Tools

The following is a list tools that are necessary to have installed:
* python -  https://www.python.org/downloads/ * pycharm (or other IDE)  - https://www.jetbrains.com/pycharm/ * Git - https://git-scm.com/downloads/ * Postgres - https://www.postgresql.org/download/ * virtualenv - http://docs.python-guide.org/en/latest/dev/virtualenvs/ 
* pgAdmin3 (optional) - https://www.pgadmin.org/download/ ## Virtualenv - Basic Use
To install:
    $ pip install virtualenvTo create a virtual environment for the project:    $ cd <proj-directory>    $ virtualenv  envTo start a virtual environment session:    $ source env/bin/activateInstall tools for environment:    $ pip install <tool>To see what is installed:    $ pip listSave and restore list of installed packages:    $ pip freeze > packages.txt    $ pip install –r packages.txtTo end the virtualenv session:    $ deactivate


## Source Control
The source for the new version of the GeneWeaver server can be found here:* https://bitbucket.org/geneweaver/website-pyThe source for the curation server can be found here:
* https://bitbucket.org/geneweaver/curation-server
To create a local copy of the repository:    $ git clone https://bitbucket.org/geneweaver/website-py
    $ git clone https://bitbucket.org/geneweaver/curation-server


## ServersThe following is a list of the servers:
* ode.jax.org - hosts the current GeneWeaver platform and the running instance of the curation server* ode2.jax.org - currently runs the beta version of GW2* ode-db1.jax.org - unused* ode-db2.jax.org - unused* ode-db3.jax.org - hosts the production database* ode-db4.jax.org - hosts the development database – missing some schema/tables needed by the curation server.

## Postgres
The relational database management system, Postgres, can be downloaded from: https://www.postgresql.org/download/On a Mac download the Postgres.app application and copy it to the Applications directory.Add the Postgres bin directory to the PATH by adding the following to your ~/.bash_profile file:    # Add Postgres to the PATH    $ export PATH=/Applications/Postgres.app/Contents/Versions/latest/bin:$PATH


## PIP Install Packages
The following packages will need to be installed in the development environment:
    $ pip install psycopg2    $ pip install flask
    $ pip install Flask-Admin
    $ pip install Flask-RESTFul
    $ pip install requests
    $ pip install urllib3    $ pip install Celery


## RabbitMQ
The Messaging Queue manager RabbitMQ can be downloaded from: https://www.rabbitmq.com/download.html

Download and copy the application to an appropriate applications directory and add it to the PATH.  For example:

    # Add RabbitMQ to the PATH
    export PATH=/Applications/rabbitmq_server-3.6.5/sbin:$PATH


## Sphinx API
The Python client for the Sphinx Search is needed.

* http://sphinxsearch.com/ - Sphinx Search
* https://github.com/jsocol/sphinxapi - Python client

The Sphinx API can be installed with the following:

    $ git clone https://github.com/jsocol/sphinxapi.git
    $ cd sphinxapi
    $ python setup.py install

    

## Dumping/Restoring the Postgres DatabaseTo dump the database:    $ pg_dump -U odeadmin -Fc -Cs ODE  > schema.custom    $ pg_dump -U odeadmin -Fc -a -T extsrc.geneset_jaccard -T production.result ODE > data.custom
To restore the database:
    # start postgres if not already running    $ dropdb ODE    $ createdb ODE    $ pg_restore --no-owner -Fc -s schema.custom | psql -U postgres -d  ODE    $ pg_restore --no-owner -a -d ODE -Fc --disable-triggers -j6 -S postgres -U postgres data.custom 

Note: the restore of the data may take several hours with no feedback.  A log of a restore session can be found here: [RestoreLog.txt](./RestoreLog.txt)


## Copying and Replacing the Postgres Database
For development it may be useful to create a backup copy of the Postgres database to ensure a consistent environment for testing.  The location of the Postgres database may vary depending on installation, however it may be found here:

> _**~/Library/Application Support/Postgres**_

All ownership, permissions and links must be maintained in the copy.  The following command will do so:

    cd ~/Library/Application Support/Postgres
    sudo cp -a var-9.5 backup
    
Replace the database directory name and path for your installation.  The copy time for a 100GB database may take two minutes or so.  The permissions and links are only set at the end of the copy.


## Running the Servers

The configuration file _**settings. py**_ must be edited for the instance of the database.  The following is an example of this file:

    DEBUG = True
    TESTING = True
    LOG_DIR = 'logs'
    DB_CONNECT_STRING = 'dbname=ODE user=postgres host=localhost'
    SECRET_KEY = 'whatever'

To start the curation server:

    $ # start postgress prior to the following command
    $ source env/bin/activate
    $ export GENEWEAVER_CONFIG=settings.py
    $ python curation-server/curation_server.py
    * Running on http://0.0.0.0:5005/ (Press CTRL+C to quit)
    * Restarting with stat
    * Debugger is active!
    * Debugger pin code: 253-544-485

To connect to the curation server (running locally), direct your browser to: [http://localhost:5005/curation](http://localhost:5005/curation/)

To start the GeneWeaver server:

    $ # start postgress prior to the following command
    $ source env/bin/activate
    $ export GENEWEAVER_CONFIG=settings.py
    $ python website-py/src/application.py
    * Running on http://0.0.0.0:5000/ (Press CTRL+C to quit)
    * Restarting with stat
    * Debugger is active!
    * Debugger pin code: 253-544-485

To connect to the server (running locally), direct your browser to: [http://localhost:5000/](http://localhost:5000/)



