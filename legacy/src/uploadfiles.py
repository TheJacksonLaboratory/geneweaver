__author__ = 'baker'

'''
This file contains functions to parse and upload files from file_contents. In particular it contains functions to
create temp tables that hold upload data and map it back to geneweaver
'''

import re
from geneweaverdb import PooledCursor

def create_temp_geneset():
    '''
    creates a temp table to hold values for geneset_values
    :param gs_id:
    :return: 'True' or 'False'
    '''
    try:
        with PooledCursor() as cursor:
            cursor.execute('''CREATE TABLE IF NOT EXISTS production.temp_geneset_value (gs_id bigint, ode_gene_id bigint,
                              src_value numeric, src_id varchar)''')
            cursor.connection.commit()
        return 'True'
    except:
        return 'False'

def create_temp_geneset_from_value(gsid):
    create_temp_geneset()
    with PooledCursor() as cursor:
        cursor.execute('''DELETE FROM temp_geneset_value WHERE gs_id=%s''', (gsid,))
        cursor.execute('''INSERT INTO temp_geneset_value (SELECT gs_id, ode_gene_id, gsv_value_list[1], gsv_source_list[1]
                        FROM geneset_value WHERE gs_id=%s)''', (gsid,))
        cursor.connection.commit()
    return

def get_file_contents_by_gsid(gsid):
    '''
    Return the file contents from the file table given the gs_id if file contents exist
    :param gsid:
    :return:
    '''
    with PooledCursor() as cursor:
            cursor.execute('''SELECT file.file_contents FROM file, geneset WHERE file.file_id=geneset.file_id AND
                              geneset.gs_id=%s''', (gsid,))
            results = cursor.fetchone()
    if results[0] is None:
        return 0
    else:
        with PooledCursor() as cursor:
            cursor.execute('''SELECT f.file_contents, g.sp_id, g.gs_gene_id_type FROM file f, geneset g WHERE g.gs_id=%s
                              AND g.file_id=f.file_id''', (gsid,))
            results = cursor.fetchall()
        return results


def reparse_file_contents_simple(gs_id):
    '''
    This is a simple parser. It does not take into consideration MicroArray data. Or any funky arrangement of tabs and
    newline characters in the file_contents attribute.
    :param gs_id:
    :return: 'True' or error msg
    '''
    file_contents = get_file_contents_by_gsid(gs_id)
    if file_contents == 0:
        return 'Error: No File Contents'
    else:
        for r in file_contents:
            ## set variables
            species = r[1]
            gdb = r[2]
            newlines = r[0].split('\n')
            if len(newlines) == 1:
                newlines = r[0].split('\r')
            if gdb < 0:
                if len(newlines) < 1:
                    return 'Error: No File Contents after loading.'
                else:
                    ##
                    ## Loop through all file_content lines
                    for newline in newlines:
                        if re.match(r'#.*$', newline):
                            print '[+] First Line Ignored ...'
                        elif re.match(r'^from', newline):
                            print '[+] From batch....'
                        else:
                            ##
                            ## catching tab delimited values
                            #values = newline.split()
                            values = re.findall(r'\S+', newline)
                            gene = None
                            try:
                                gene = values[0]
                            except:
                                print 'value error: ' + newline
                                #print r[0]
                            v = 1.0
                            if len(values) == 2:
                                v = values[1]
                                try:
                                    v = float(v.strip('\n\r '))
                                except ValueError:
                                    pass
                            ##
                            ## Get ode_gene_ids
                            if gene != '' and isinstance(v, float):
                                gene = str(gene.strip('\n\r '))
                                g = gene.lower()
                                gdb = -1 * int(gdb)
                                s = None
                                with PooledCursor() as cursor:
                                    cursor.execute('SELECT ode_gene_id FROM gene WHERE LOWER(ode_ref_id) LIKE LOWER(%s) '
                                                   'AND sp_id=%s AND gdb_id=%s', (g, species, gdb,))
                                    s = cursor.fetchall()
                                if s is not None:
                                    for i in s:
                                        with PooledCursor() as cursor:
                                            cursor.execute('INSERT INTO production.temp_geneset_value '
                                                       'VALUES (%s, %s, %s, %s)' , (gs_id, i[0], v, gene,))
                                            cursor.connection.commit()
                    return 'True'

def insert_into_geneset_value_by_gsid(gsid):
    '''
    Given a gs_id, insert the rows into extsrc.geneset_value table from our temp table.
    :param gsid:
    :return: 'True' or error msg
    '''
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gs_id FROM production.temp_geneset_value WHERE gs_id=%s''', (gsid,))
        g = cursor.fetchone()
        if g is not None:
            if int(g[0]) == int(gsid):
                with PooledCursor() as cursor:
                    cursor.execute('''DELETE FROM extsrc.geneset_value WHERE gs_id=%s;''' % (gs_id,))
                    cursor.execute('''INSERT INTO extsrc.geneset_value (gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list,
                                     gsv_value_list, gsv_in_threshold, gsv_date)
                                         SELECT gs_id, ode_gene_id, avg(src_value) as gsv_value,
                                           count(ode_gene_id) as gsv_hits, array_accum(src_id) as gsv_source_list,
                                           array_accum(src_value) as gsv_value_list,'t' as gsv_in_threshold, now() as gsv_date
                                           FROM production.temp_geneset_value
                                           WHERE gs_id=%s GROUP BY gs_id,ode_gene_id ORDER BY ode_gene_id;''' % (gs_id,))
                    cursor.execute('''DELETE FROM production.temp_geneset_value WHERE gs_id=%s;''' % (gs_id,))
                    cursor.connection.commit()
        else:
            return 'Error: Temp table does not contain gs_id'




