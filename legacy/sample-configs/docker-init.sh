#! /bin/bash

if [ -d "../../database" ]; then
	echo "Database directory exists"
else
	git clone -b docker git@bitbucket.org:geneweaver/database.git ../../database
fi


if [ -d "../../tools" ]; then
	echo "Tools directory exists"
else
	git clone -b docker git@bitbucket.org:geneweaver/tools.git ../../tools
fi

if [ $(docker volume ls -qf dangling=true | wc -w) -gt 0 ]; then
	docker volume rm $(docker volume ls -qf dangling=true)
fi

docker-compose build
