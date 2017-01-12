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