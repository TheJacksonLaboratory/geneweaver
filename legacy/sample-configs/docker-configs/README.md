# Deploying Geneweaver with Docker

Using Docker to deploy a Geneweaver stack can significantly reduce the amount of setup required to get a working installation running.

>Docker containers wrap a piece of software in a complete filesystem that contains everything needed to run: code, runtime, system tools, system libraries – anything that can be installed on a server. This guarantees that the software will always run the same, regardless of its environment.

### Installation

Deploying with docker requires you to have docker installed on your system. 

Download and install the latest version available for your OS from the [Docker website](https://www.docker.com/products/docker), and make sure to also install [Docker compose](https://docs.docker.com/compose/install/). You will also need git, so if you haven't yet, make sure that is installed as well.

Clone the repositories into the directory you'd like to run your application in.
```sh
$ cd /somedir/geneweaver
$ git clone git@bitbucket.org:geneweaver/website-py.git
$ git clone git@bitbucket.org:geneweaver/tools.git
```

Download the database tar file, create a new container named gw-dbstore, then extract the tar file to that container:
```sh
$ wget http://somelink.tothefile.com
$ docker run -v /var/lib/postgresql/data --name gw-dbstore ubuntu /bin/bash
$ docker run --rm --volumes-from gw-dbstore -v $(pwd):/backup ubuntu bash -c "cd /dbdata && tar xvf /backup/backup.tar --strip 1"
```

Navigate to the website-py/sample-configs directory:

```sh
$ cd website-py/sample-configs
```

Edit your mail preferences to reference an smtp server.
```sh
$ vim docker-configs/geneweaver.cfg
```
```ini
[application]
host = 127.0.0.1
smtp = smtp.mycompany.com
admin_email = NoReply@geneweaver.org
```
### Initial Startup
While in the sample-configs directory, call the following command.
```sh
$ docker-compose build
```
This command can take a few seconds to several minutes, to more than 10 minutes, depending on your computer and internet connection.

The first time you start the docker stack, it is often a good idea to view the stderr/stdout of each container as it initializes. 
```sh
$ docker-compose up
```
You can use <pre>CTRL</pre>+<pre>C</pre> to bring the stack down.

To start the stack in the backgroun, use the -d flag.
```sh
$ docker-compose up -d
```
### Management
##### Container Management
Your docker stack is managed through the [docker-compose](https://docs.docker.com/compose/reference/overview/) command.
```
Define and run multi-container applications with Docker.

Usage:
  docker-compose [-f=<arg>...] [options] [COMMAND] [ARGS...]
  docker-compose -h|--help

Options:
  -f, --file FILE             Specify an alternate compose file (default: docker-compose.yml)
  -p, --project-name NAME     Specify an alternate project name (default: directory name)
  --verbose                   Show more output
  -v, --version               Print version and exit
  -H, --host HOST             Daemon socket to connect to

  --tls                       Use TLS; implied by --tlsverify
  --tlscacert CA_PATH         Trust certs signed only by this CA
  --tlscert CLIENT_CERT_PATH  Path to TLS certificate file
  --tlskey TLS_KEY_PATH       Path to TLS key file
  --tlsverify                 Use TLS and verify the remote
  --skip-hostname-check       Don't check the daemon's hostname against the name specified
                              in the client certificate (for example if your docker host
                              is an IP address)

Commands:
  build              Build or rebuild services
  config             Validate and view the compose file
  create             Create services
  down               Stop and remove containers, networks, images, and volumes
  events             Receive real time events from containers
  help               Get help on a command
  kill               Kill containers
  logs               View output from containers
  pause              Pause services
  port               Print the public port for a port binding
  ps                 List containers
  pull               Pulls service images
  restart            Restart services
  rm                 Remove stopped containers
  run                Run a one-off command
  scale              Set number of containers for a service
  start              Start services
  stop               Stop services
  unpause            Unpause services
  up                 Create and start containers
  version            Show the Docker-Compose version information
```

##### Database Management
Managing the postgresql database in the docker stack is slightly more convoluted than if you were to run a local instance of Postgres. First, on your host system call the docker exec command on your postgres container in order to access its command line. 
```sh
$ docker exec -it geneweaver-postgres /bin/bash
```
This will take you to the command line of the postgres container. You can now use the psql application to manage the postgresl database. 
```sh
root@f4ddc1cbd90c:/# psql -U postgres -h geneweaver
psql (9.6.1)
Type "help" for help.

postgres=#
```
If you cannot connect to the container, but instead recieve the following response, it's likely that your container is no longer running.
```sh
Error response from daemon: No such container: geneweaver-postgres
```
In this case, check the status of your docker processes, and restart the stack if need be. Here we can see that although our containers are initialized, they have since exited, some with non-zero exit statuses.
```sh
$ docker ps -a
CONTAINER ID        IMAGE                        COMMAND                  CREATED             STATUS            NAMES
21687550ac91        geneweaver:latest            "/usr/bin/supervisord"   3 minutes ago       Exited (0)        geneweaver-web
fd36e07d6393        leodido/sphinxsearch:2.2.9   "indexall.sh"            3 minutes ago       Exited (137)      geneweaver-sphinx
86e8fec12a98        rabbitmq:3-management        "docker-entrypoint.sh"   3 minutes ago       Exited (143)      geneweaver-rabbitmq
87ecc5d6241b        postgres:9.6                 "/docker-entrypoint.s"   3 minutes ago       Exited (137)      geneweaver-postgres
ddd5a36007d4        localhost:5000/gwdb:0.2      "/docker-entrypoint.s"   6 weeks ago         Exited (137)      gwdb-ext
```