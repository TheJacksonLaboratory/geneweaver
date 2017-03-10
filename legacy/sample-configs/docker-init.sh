#! /bin/bash

if [ -d "../../database" ]; then
	echo "Database directory exists"
else
	git clone git@bitbucket.org:geneweaver/database.git ../../database
	cd ../../database
	git fetch && git checkout docker
	cd ../website-py/sample-configs
fi


if [ -d "../../tools" ]; then
	echo "Tools directory exists"
else
	git clone git@bitbucket.org:geneweaver/tools.git ../../tools
	cd ../../tools
	git fetch && git checkout docker
	cd ../website-py/sample-configs
fi

docker volume rm $(docker volume ls -qf dangling=true)
docker-compose build