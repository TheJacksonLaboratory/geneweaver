GeneWeaver 2.0 Setup and Deployment
===================================

Documentation for setting up and deploying the GeneWeaver application.

## System Requirements

GeneWeaver is designed to run on Linux and requires a relatively recent
release. It has been tested on CentOS 6/7 and Red Hat distributions but should
run on other distributions with minimal changes. 

To begin, you'll need the following application dependencies:

    $ sudo yum install boost boost-devel cairo cairo-devel git graphviz libffi libffi-devel postgresql-server postgresql-devel python2 rabbitmq-server sphinx

Ensure that the following applications meet these version requirements:

* python == __2.7.*__
* PostgreSQL >= __9.2__
* Graphviz >= __2.3__
* RabbitMQ >= __3.3.*__
* Sphinx >= __2.1.*__


## Configuring PostgreSQL

*This will eventually change to support installing and setting up a skeleton
DB*

In most cases, installing the Postgres server will automatically create a new
postgres user to own and administer the server. If this user does not already
exist, create it:

    $ useradd -d /var/lib/pgsql postgres

Switch to the postgres user account:

    $ sudo su - postgres

Initialize a database cluster to store the database(s):

    $ initdb -D /var/lib/pgsql/data

Start the server:
    
    $ pg_ctl start -D /var/lib/pgsql/data -l logfile

Add a role for future connections. We typically use 'odeadmin':

	$ createuser -s odeadmin

Create a new database. We typically use 'geneweaver':

	$ createdb geneweaver 

You can now log out of the postgres user account.

### Dumping the Database

If you already have a copy of the DB, you can skip this section. Dumping a
current instance of the GWDB is done in two parts. First, a copy of the schema
is saved:

    $ pg_dump -U odeadmin -Fc -Cs geneweaver > gw-schema.custom

Next, the data is stored separately. To speed up the restore process, we
exclude two large tables, geneset_jaccard and result: 

    $ pg_dump -U odeadmin -Fc -a -T extsrc.geneset_jaccard -T production.result geneweaver > gw-data.custom

### Restoring from a DB Dump

First restore the schema:
	
	$ pg_restore --no-owner -d geneweaver -U postgres -s gw-schema.custom

Next, restore the data. The -j option specifies the number of cores to use
during the restore process. The --disable-triggers option must be used
otherwise the restore will fail. This will take several hours.

	$ pg_restore -a -d geneweaver -Fc --disable-triggers -j 6 -S odeadmin -U odeadmin gw-data.custom


## Running RabbitMQ

RabbitMQ is the message broker used by Celery to distribute GW tool runs. It
can be run in the background:

	$ rabbitmq-server start &

Or it can be configured to start on boot and daemonized:

	$ chkconfig rabbitmq-server on
	$ /sbin/service rabbitmq-server start

Or daemonization using systemctl: 

	$ systemctl start rabbitmq-server.service


## Configuring Sphinx

A sample sphinx config can be found in the `sample-configs/` directory.
The following example stores the Sphinx config and indices under `/var/lib`. 
Create a folder to hold the Sphinx config file and indices:

	$ sudo mkdir /var/lib/sphinx/geneweaver
	$ sudo cp geneweaver-configs/sphinx/sphinx.conf geneweaver-configs/sphinx/stopwords.txt /var/lib/sphinx/geneweaver

You'll have to make several edits to the sphinx configuration. First, edit the
`source base` section to point to the newly set up Postgres DB.

Both `source geneset_src` and `source geneset_delta_src` sections contain an 
`sql_query` variable that should be edited to support any species that are 
currently found in the database. You'll have to associate the sp_id with a 
common species name.

Under the `index geneset` section, specify the full path of the geneset index
using the `path` variable. This path can be anywhere on the system--we
typically use the sphinx folder. Set the `stopwords` variable to the full
path containing the list of stop words we copied into the sphinx folder above.
Make the same changes under the `index geneset_delta` section too.

Create a 'log' directory; 'chown [sphinxuser]'.

Under the `searchd` section, change the `log`, `query_log`, and
`pid_file` variables to point to full paths for each of those files.

Installing Sphinx will usually create a user to own the search server. If a
sphinx user does not exist, create one:

	$ useradd -d /var/lib/sphinx sphinx

Generate the search indices:

	$ sudo -usphinx indexer --all --config /var/lib/sphinx/geneweaver/sphinx.conf

Start the server as the sphinx user:

	$ sudo -usphinx searchd --config /var/lib/sphinx/geneweaver/sphinx.conf


## Configuring the Python Environment

Python 2.7 should automatically come installed with pip. If it is missing from
your system, bootstrap the installation by downloading and executing the pip
installer:

	$ wget https://bootstrap.pypa.io/get-pip.py && python get-pip.py

### Configuring virtualenv (optional)

Installing virtualenv is optional but it creates an easy to use, stand-alone
environment in which to install python packages and set up the application.
Installation may require sudo privileges. Use pip to install:

	$ pip install virtualenv

Create the GeneWeaver virtual environment. In this example the GeneWeaver
application will reside under `/srv`:

	$ mkdir /srv/geneweaver && cd /srv/geneweaver
	$ virtualenv venv

Activate the environment:

	$ source venv/bin/activate

You can now install any python packages without contaminating the global python
environment. To deactivate the environment use:

	$ deactivate

### Installing Packages

GeneWeaver requires the following python packages:

* cairosvg
* celery
* flask
* flask-admin
* flask-restful
* numpy
* psycopg2
* requests
* urllib3

These can be installed individually using pip (which should also install their
dependencies) or using our requirements.txt which also includes all
dependendent packages. The requirements file can be found in the
`sample-configs` directory.

	$ pip install -r requirements.txt

GeneWeaver also utilizes Sphinx's python API. The python package can no longer
be found in any of the PyPi repos but we have a custom package that can be
retrieved and installed: 

	$ wget http://geneweaver.org/sphinxapi.tar.gz
	$ pip install sphinxapi.tar.gz


## Deploying GeneWeaver

Retrieve the GeneWeaver web application and toolset from the BitBucket repo.
Create a new project folder if you haven't already:

	$ mkdir /srv/geneweaver && cd /srv/geneweaver
	$ git clone https://YOUR_USERNAME@bitbucket.org/geneweaver/website-py.git
	$ git clone https://YOUR_USERNAME@bitbucket.org/geneweaver/tools.git

### Configuring the Web Application

Provided all previous installations were successful, the web application should
be ready to start. First, edit `src/config.py` and change the `CONFIG_PATH`
variable to point to a location to store the GeneWeaver config file.

The config file doesn't need to exist, GeneWeaver will generate one for you to
edit at the path you provide. Run the application once to generate the config
file:

	$ cd website-py
	$ python src/application.py

Edit the newly generated configuration file with the proper application,
celery, database, and sphinx information. In most cases, the default celery
configuration is appropriate.

Create a results directory with 777 permissions. The path will be placed in the config file.

### Configuring the Toolset

Like the web application, edit `tools/config.py` change the `CONFIG_PATH`
variable to point to a location to store the tool config file. From the tools
parent directory, you can run the tools once to generate a default config.
If you installed virtualenv, be user to run the tools from that environment.

	$ celery -A tools.celeryapp worker --loglevel=info

Edit the config with the appropriate information.

#### NOTE: The tool table may be incompatible with the celeryapp.py tool list. You may drop the tool table data and reload with ODE-data-only-tool.dump to correct.

#### Compiling the Graph Tools

We use several highly optimized software implementations written in C/C++.
This suite of tools can be found in the `TOOLBOX/` directory and should be
compiled prior to running the toolset written in Python. 

Ensure gcc and other development tools exist on your system. If they are
missing, install them:

	$ sudo yum install gcc g++ make

These tools can be compiled using the "master" makefile located in TOOLBOX.

	$ cd tools/TOOLBOX && make && cd ../..

### Running the Application

GeneWeaver should now be ready to run. Start the tools application from the
parent directory of the tools:

	$ celery -A tools.celeryapp worker --loglevel=info

Start the web application from the website-py directory:

	$ cd website-py
	$ python src/application.py

By default the web app runs on port 5000. You can point your browser to the
host you assigned and you should see the GeneWeaver home page. They application
may require sudo privileges to establish a connection on the given port.

### Managing GeneWeaver with Supervisor (optional)

Supervisor is a system management utility that can be used to control the
GeneWeaver application. Start by installing it:

	$ sudo yum install supervisor

Copy the sample supervisord config from the `sample-configs` directory to a 
directory of your choosing. Here we use the geneweaver application directory:

	$ cp sample-configs/supervisord.conf /srv/geneweaver

Create a folder to store the supervisord logs, or store them in any directory
you wish:

	$ mkdir /srv/geneweaver/supervisord

Now edit the `supervisord.conf` file to match your installation and log
directories. After editing, you can start the supervisor:

	$ sudo supervisord -c /srv/geneweaver/supervisord.conf

To manage your applications use:

	$ sudo supervisorctl -c /srv/geneweaver/supervisord.conf