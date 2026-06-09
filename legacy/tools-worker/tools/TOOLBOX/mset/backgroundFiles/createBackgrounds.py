#!/usr/bin/python2.4
#
# Small script to show PostgreSQL and Pyscopg together
#

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
    db = 'geneweaver'
    user = 'odeadmin'
    password = 'odeadmin'
    host = 'crick.ecs.baylor.edu'
    port = 32769

    cs = "host='%s' dbname='%s' user='%s' password='%s'" % (host, db, user, password)

    conn = psycopg2.connect(cs)

    cursor = conn.cursor()

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

            with io.FileIO(bg_file, "w") as file:
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

            with io.FileIO(bg_file, "w") as file:
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
    print(str(e.message))
