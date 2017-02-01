## This Dockerfile was made based off the information and configuration files found here: 
##   https://osxdominion.wordpress.com/2015/01/25/customizing-postgres-in-docker/

## Download base image of postgres
FROM postgres

## Set environment variables, which will be passed to the setup_database.sh script.
ENV DB_NAME database
ENV DB_USER admin
ENV DB_PASS password

## The docker-entrypoint directory is a special dir provided by the default postgress container to extend additional tasks 
##   on startup. Chmod adds correct execution permissions to the script.
ADD setupRemoteConnections.sh /docker-entrypoint-initdb.d/setupRemoteConnections.sh
RUN chmod 755 /docker-entrypoint-initdb.d/setupRemoteConnections.sh 

## This uses another script to set up the initial database with correct role and privileges, using environment variables
ADD setup-database.sh /docker-entrypoint-initdb.d/
RUN chmod 755 /docker-entrypoint-initdb.d/setup-database.sh
