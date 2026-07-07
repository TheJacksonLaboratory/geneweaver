#!/usr/bin/python2.4
#
# Small script to show PostgreSQL and Pyscopg together
#

import os
import sys
import psycopg2
import itertools
import io
from collections import OrderedDict

def get_all_species(cursor):
    try:
        cursor.execute(
            '''
            SELECT sp_id, sp_name
            FROM odestatic.species
            WHERE sp_id <> 0
            ORDER BY sp_id;''')
        return OrderedDict(cursor)
    except Exception as e:
        return str(e)

def get_all_attributions(cursor):
    try:
        cursor.execute(
            '''
            SELECT at_id, at_abbrev
            FROM odestatic.attribution
            WHERE at_abbrev IS NOT NULL AND at_id <> 5
            ORDER BY at_id;
            ''')
        return OrderedDict(cursor)
    except Exception as e:
        return str(e)

def get_all_gdb_types(cursor):
    try:
        cursor.execute(
            '''
            SELECT gdb_id, gdb_name
            FROM odestatic.genedb
            WHERE gdb_name NOT IN (
              SELECT at_abbrev
              FROM odestatic.attribution
              WHERE at_abbrev IS NOT NULL
              )
            ORDER BY gdb_id;
            ''')
        return OrderedDict(cursor)
    except Exception as e:
        return str(e)

def get_gene_id_by_gdb_type(gdb_id, speciesToInclude, cursor):
    cursor.execute(
        '''
        SELECT gi_symbol
	    FROM extsrc.gene_info
	    WHERE ode_gene_id IN (
            SELECT ode_gene_id
            FROM extsrc.gene
            WHERE gdb_id = %(gdbType)s
                  AND ode_gene_id IN (
                SELECT ode_gene_id
                FROM extsrc.geneset_value
                WHERE gs_id IN (
                    SELECT gs_id
                    FROM production.geneset
                    WHERE (cur_id <> 5 AND cur_id <> 4 AND cur_id IS NOT NULL) AND sp_id = %(speciesToBeInclude)s
            )));
        ''',
        {
            'gdbType': gdb_id,
            'speciesToBeInclude': speciesToInclude
        }
    )
    return cursor.fetchall()

def get_gene_id_by_attribute(attr_id, speciesToInclude, cursor):
    cursor.execute(
        '''
        SELECT gi_symbol
	    FROM extsrc.gene_info
	    WHERE ode_gene_id IN (
            SELECT ode_gene_id
            FROM extsrc.geneset_value
            WHERE gs_id IN (
                    SELECT gs_id
                    FROM production.geneset
                    WHERE (cur_id <> 5 AND cur_id <> 4 AND cur_id IS NOT NULL) AND gs_attribution = %(attribute)s
                      AND sp_id = %(speciesToBeInclude)s
            ));
        ''',
        {
            'attribute': attr_id,
            'speciesToBeInclude': speciesToInclude
        }
    )
    return cursor.fetchall()

try:
    # DB connection from the standard GeneWeaver env vars (same ones the
    # tools-worker receives from the geneweaver-db secret); fall back to the
    # historical values when unset.
    db = os.environ.get('DB_NAME', 'geneweaver')
    user = os.environ.get('DB_USERNAME', 'odeadmin')
    password = os.environ.get('DB_PASSWORD', 'odeadmin')
    host = os.environ.get('DB_HOST', 'crick.ecs.baylor.edu')
    port = os.environ.get('DB_PORT', '5432')

    cs = "host='%s' port='%s' dbname='%s' user='%s' password='%s'" % (host, port, db, user, password)

    conn = psycopg2.connect(cs)

    cursor = conn.cursor()

    # Output directory for the generated *BG.txt files. Env-driven so they can be
    # written to a persistent/results volume (see MSET.py GW_MSET_BG_DIR); defaults
    # to the current directory (in-image backgroundFiles/) for backward compat.
    outdir = os.environ.get('GW_MSET_BG_DIR') or (sys.argv[1] if len(sys.argv) > 1 else '.')
    if not os.path.isdir(outdir):
        os.makedirs(outdir)

    symbol_list = []

    species = get_all_species(cursor)

    spec_ids = []
    for sym in species:
        spec_ids.append(sym)

    attributes = get_all_attributions(cursor)

    gdb_types = get_all_gdb_types(cursor)

    for att in attributes:
        bg_file_base = ''

        bg_file_base += str(attributes[att])

        for id in spec_ids:
            bg_file = bg_file_base
            bg_file += str(species[id])

            bg_file = bg_file.replace(" ", "")
            bg_file += 'BG.txt'
            print(bg_file)

            raw = get_gene_id_by_attribute(att, id, cursor)

            with open(os.path.join(outdir, bg_file), "w") as file:
                i = 0
                for sym in raw:
                    file.write(str(sym[0]) + '\n')
                    i += 1
                if i > 0:
                    file.truncate(file.tell() - 1)
            file.close()

    for type in gdb_types:
        bg_file_base = ''

        bg_file_base += str(gdb_types[type])

        for id in spec_ids:
            bg_file = bg_file_base
            bg_file += str(species[id])

            bg_file = bg_file.replace(" ", "")
            bg_file += 'BG.txt'
            print(bg_file)

            raw = get_gene_id_by_gdb_type(type, id, cursor)

            with open(os.path.join(outdir, bg_file), "w") as file:
                i = 0
                for sym in raw:
                    file.write(str(sym[0]) + '\n')
                if i > 0:
                    i += 1
                    file.truncate(file.tell - 1)
            file.close()

    cursor.close()
    conn.close()

except Exception as e:
    print(str(e))
