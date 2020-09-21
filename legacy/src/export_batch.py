#!/usr/bin/python

"""
This file contains scripts to insert new geneests based on two files:
(1) a tab delimited file with header with geneset metadata information
(2) a tab delimited file with genes associated with geneset, using gs_id from file (1)
"""

import psycopg2
from psycopg2.pool import ThreadedConnectionPool


__author__ = 'baker'
__date__ = '2016-12-28'


def db_conn():
    # Attempt local db connection; only time this really ever fails is when the
    # postgres server isn't running.
    # TODO: This needs to be moved out of this file
    try:
        conn = psycopg2.connect(("host='ode-db4.jax.org' dbname='ODE' user='odeadmin' "
                                 "password=''"))
    except:
        print("[!] Oh noes, failed to connect to the db")

        exit()

    # Globals are bad, mmkay?
    g_cur = conn.cursor()
    g_cur.execute('SET search_path=extsrc,odestatic,production;')
    return g_cur


def get_number_tier_3(conn):
    """
    Return the number of Tier 3 genesets in order to grab 50 at a time.
    """
    conn.execute('''SELECT count(gs_id) FROM production.geneset WHERE gs_status NOT LIKE 'de%%' AND cur_id=3''')
    return conn.fetchall()[0][0] if not None else 0


def get_gs_ids(conn, offset, limit):
    """
    return a list of gs_ids based on query
    """
    gs_ids = []
    conn.execute('''SELECT gs_id FROM production.geneset
                    WHERE cur_id=3 AND gs_status NOT LIKE 'de%%'
                    LIMIT %s OFFSET %s''', (limit, offset,))
    res = conn.fetchall()
    for r in res:
        gs_ids.append(r)
    return gs_ids


def get_genedb(conn, gdb_id):
    """
    Return the gene database name given a gene db id. Must return either gene database name or
    microarray name.
    """
    prefix = ''
    if gdb_id < 0:
        gdb_id *= -1
        sql = 'SELECT gdb_name FROM genedb WHERE gdb_id=%s'
    else:
        prefix = 'microarray '
        sql = 'SELECT pf_name FROM platform WHERE pf_id=%s'
    with conn as cursor:
        cursor.execute(sql, [gdb_id])
        res = cursor.fetchall()
    return prefix + res[0][0] if res[0][0] is not None else 'Unannotated'


def get_pubmed_id(conn, gs_id):
    """
    return pubmed id if one exists, otherwise return null
    """
    with conn as cursor:
        sql = '''SELECT p.pub_pubmed FROM publication p, geneset gs WHERE gs.gs_id=%s AND gs.pub_id=p.pub_id'''
        rows_count = cursor.execute(sql, [gs_id])
    if rows_count > 0:
        res = cursor.fetchall()
        return res[0][0]
    else:
        return None


def metadata_batch(conn, gs_id):
    """
    Return information associated with metadata to make a
    compliant batch file upload
    """
    import datetime
    s = '# This metadata batch upload is created by a GeneWeaver.org export geneset batch script.\n'
    s += '# ' + str(datetime.datetime.now()) + '\n'
    s += '#\n'
    s += '# The format of this file is described online at:\n'
    s += '#    http://geneweaver.org/index.php?action=manage&cmd=batchgeneset\n'
    s += '# Which is the same page that it can be submitted to.\n'
    s += '#\n'

    # sql to return information about gs
    with conn as cursor:
        sql = '''SELECT gs.gs_abbreviation, gs.gs_name, gs.gs_description,
              gs.gs_threshold_type, gs.gs_threshold, sp.sp_name, gs.gs_gene_id_type
              FROM geneset gs, species sp
              WHERE gs.gs_id=%s AND sp.sp_id=gs.sp_id'''
        cursor.execute(sql, [gs_id])
        res = cursor.fetchall()

    # map results onto header metadata string
    s += ': ' + str(res[0][0]) + '\n'
    s += '= ' + str(res[0][1]) + '\n'
    s += '+ ' + str(res[0][2]) + '\n'
    # Publication
    p = get_pubmed_id(conn, gs_id)
    if p is not None:
        s += 'P ' + str(p) + '\n'
    s += 'A Public' + '\n'

    # map threshold types (at least I think that these map properly)
    # ! Binary
    # ! P - Value < 0.05
    # ! Q - Value < 0.05
    # ! 0.40 < Correlation < 0.90
    # ! 6.0 < Effect < 22.50
    if res[0][3] is not None:
        if res[0][3] == 1:
            s += '! P-Value < ' + str(res[0][4]) + '\n'
        elif res[0][3] == 3:
            s += '! Q-Value < ' + str(res[0][4]) + '\n'
        elif res[0][3] == 5:
            s += '! ' + str(res[0][4].split(',')[0]) + ' < Effect < ' + str(res[0][4].split(',')[0]) + '\n'
        elif res[0][3] == 4:
            s += '! ' + str(res[0][4].split(',')[0]) + ' < Correlation < ' + str(res[0][4].split(',')[0]) + '\n'
        else:
            s += '! Binary\n'

    # species
    s += '@ ' + res[0][5] + '\n'
    # gs gene id type
    s += '% ' + get_genedb(conn, res[0][6]) + '\n'
    # mandatory space added during main() join
    # s += '\n'
    return s


def geneinfo_batch(conn, gs_id):
    """
    Returns a list of genes (ode_ref_ids) associated with a geneset id in gene<tab>value list.
    """
    # Get gdb_id type. This will determine which id type to return, particularly important for microarrays
    with conn as cursor:
        cursor.execute('''SELECT gs_gene_id_type FROM geneset WHERE gs_id=%s''', (gs_id,))
        gdb_id = cursor.fetchall()[0][0]
    # Build query based on genes or microarrays (i.e. gdb_id < 0)
    s = ''
    # Genesets
    with conn as cursor:
        if gdb_id < 0:
            gdb_id *= -1
            sql = 'SELECT g.ode_ref_id, gsv.gsv_value ' \
                  'FROM geneset_value gsv, gene g, geneset gs ' \
                  'WHERE gsv.gs_id=%s AND gsv.ode_gene_id=g.ode_gene_id AND g.sp_id=gs.sp_id AND gs.gs_id=gsv.gs_id ' \
                  'AND g.gdb_id=%s'
            cursor.execute(sql, [gs_id, gdb_id])
        # Microarrays
        else:
            sql = 'SELECT prb.prb_ref_id, gsv.gsv_value ' \
                  'FROM probe prb, probe2gene p2g, geneset_value gsv ' \
                  'WHERE gsv.ode_gene_id=p2g.ode_gene_id AND p2g.prb_id=prb.prb_id AND gsv.gs_id=%s'
            cursor.execute(sql, [gs_id])
        res = cursor.fetchall()
    if res is not None:
        for r in res:
            s += str(r[0]) + '\t' + str(r[1]) + '\n'
    s += '\n'
    return s


def ontology_batch(conn, gs_id):
    """
    Returns all of the ontology information for the geneset
    """
    s = ''
    sql = '''SELECT ont.ont_ref_id FROM ontology ont, geneset_ontology gso
              WHERE gso.gs_id=%s AND ont.ont_id=gso.ont_id'''
    with conn as cursor:
        cursor.execute(sql, [gs_id])
        res = cursor.fetchall()
    if res is not None:
        for r in res:
            s += '~ ' + str(r[0]) + '\n'
    return s


def main():
    # new db connection
    conn = db_conn()

    # get the number of Tier 3 gs_ids
    gsnumber = get_number_tier_3(conn)
    print(gsnumber)

    offset = 0
    limit = 100
    counter = 't'

    while counter == 't':

        # get gs_ids for all tier 3, non-deleted genesets owned by elissa, jason, natasha, or jeremy
        gs_ids = get_gs_ids(conn, offset, limit)

        s = ''
        # loop through all gs_ids and build batch file
        for gs in gs_ids:
            # build metadata string
            metadata = metadata_batch(conn, gs)
            # Ontology batch
            ontologydata = ontology_batch(conn, gs)
            # build geneset info string
            geneinfo = geneinfo_batch(conn, gs)
            s += metadata + ontologydata + '\n' + geneinfo

        # open outfile
        if offset < gsnumber:
            fh = open('gw.batch-' + str(offset), 'w')
            fh.write(s)
            fh.close()
            print('Written to gw.batch-' + str(offset))

        # Update counters
        if gsnumber - offset < 0:
            counter = 'f'
        else:
            offset += limit

    print('Done')

if __name__ == "__main__":
    main()
