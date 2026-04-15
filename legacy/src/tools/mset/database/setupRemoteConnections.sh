#!/bin/bash

##### This script was found on the github: https://github.com/macadmins/postgres/blob/master/setupRemoteConnections.sh ##### 
##### This script is used to set up remote connections to the docker container.                                        #####

## This line of code modifies a preexisting file for postgres to allow for the 172.17.0.1/16 range to be included in a list
## of trusted access locations that are allowed to make database updates. Thos range is for the Docker IP addresses.
sed -i '/host    all             all             127.0.0.1\/32            trust/a host    all             all             172.17.0.1\/16            trust' /var/lib/postgresql/data/pg_hba.conf
