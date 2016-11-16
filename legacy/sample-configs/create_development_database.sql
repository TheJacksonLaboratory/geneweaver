
/* Drop backup schemas/tables */
DROP SCHEMA extsrc_bak CASCADE;
DROP SCHEMA extsrc_bak2 CASCADE;
DROP SCHEMA extsrc_20150605 CASCADE;
VACUUM (FULL);
REINDEX DATABASE geneweaver;

/* Dump the schema/data to a combined binary file */
/*
Note: You may also wish to first run some de-dupe scripts from the migration folder.

Once you're ready, from the command line call something like:
pg_dump -Fc -U odeadmin geneweaver > gw-full.bin

To restore use something like:
pg_restore -d geneweaver3 -Fc -j 8 -S odeadmin gw-full.bin

Check pg_restore --help for systemc specific options
*/