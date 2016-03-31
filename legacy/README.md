This is an early version of the README and likely contains several mistakes.
Please feel free to modify this document with your fixes, clarifications and
additional information as you see fit.

# Running the application

Prerequisites to running:

* python 2.7.* along with the following python modules which can be installed
  using pip or easy_install:
  * Flask
  * psycopg2
  * celery
* RabbitMQ
* GeneWeaver tools
* mod_wsgi (for running on a production server)

## Configuring and Running a Development Instance on localhost

This section describes how to create a development instance where all the
components except the database are running on localhost. These instructions
are based on running GeneWeaver on OS X so there may be some changes required
to run on Linux or Windows

GeneWeaver runs celery on top of RabbitMQ in order to submit tool jobs to a
pool of python processes. This is important because tools tend to be
long-running jobs and would otherwise block the web application from
responding to requests. After you have installed and configured an instance of
RabbitMQ you can start the RabbitMQ service with a command like:

    rabbitmqctl start

Before we start up celery we need to make sure that it points to our RabbitMQ
instance. For my development instance this meant editing `tools/celeryapp.py` with
the following values:

    BROKER_URL = 'amqp://guest@localhost//'
    CELERY_RESULT_BACKEND = 'db+sqlite:////Users/kss/projects/GeneWeaver/results.db'
    CELERY_INCLUDES = [
        #'tools.PhenomeMap',
        'tools.GeneSetViewer',
        #'tools.Combine',
        #'tools.HyperGeometric',
        #'tools.JaccardSimilarity',
        #'tools.JaccardClustering',
    ]
    
    celery = Celery(
        'geneweaver.tools',
        broker=BROKER_URL,
        backend=CELERY_RESULT_BACKEND,
        include=CELERY_INCLUDES,
    )

... and likewise `website-py/src/tools/toolcommon.py` must use the same values

    BROKER_URL = 'amqp://guest@localhost//'
    CELERY_RESULT_BACKEND = 'db+sqlite:////Users/kss/projects/GeneWeaver/results.db'

NOTE: this duplication is a result of the fact that our celery tools and
web applications live in different source trees. This is different from
celery examples that you will see on the web where code from web front ends and
celery tasks are in the same folder.

Now start celery which will spawn the tool workers. From the parent directory
of the tools repository you can run:

    celery -A tools.celery worker --loglevel=info

If you get a connection refused message this indicates that celery is unable
to connect to your RabbitMQ service which may be due to a configuration problem.

Finally, you can start the web application from the website-py folder with a
command like:

    python src/application.py

You should see the server start up with no error messages like:

    * Running on http://127.0.0.1:5000/
    * Restarting with reloader

You can now visit the main page of the test server by going to
<http://localhost:5000/index.html>
This is Felix's
