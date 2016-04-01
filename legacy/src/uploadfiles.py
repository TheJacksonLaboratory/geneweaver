__author__ = 'baker'

'''
This file contains functions to parse and upload files from file_contents. In particular it contains functions to
create temp tables that hold upload data and map it back to geneweaver
'''

from urlparse import parse_qs, urlparse

from geneweaverdb import PooledCursor, get_geneset, get_user, get_species_id_by_name, get_gdb_id_by_name

import re
from flask import session


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
            cursor.execute('''CREATE TABLE IF NOT EXISTS production.temp_geneset_meta (gs_id bigint, sp_id int, gdb_id int)''')
            cursor.connection.commit()
        return 'True'
    except:
        return 'False'

def get_identifier_from_form(ident):
    '''
    This function returns a negative int for a gene db and a positive int for a microarray-based string
    :param identifier: gene_*** or ma_***
    :return: either positive or negative int
    '''
    tmpString = ident.split('_')
    if tmpString[0] == 'ma':
        return int(tmpString[1])
    else:
        return int(tmpString[1]) * -1

def insertPublication(pubDict):
    '''
    Insert publication data where it does not exist, or return ID where it does.
    :param pubDict: dictionary
    :return: pub_id
    '''
    pmid = False
    ## Get pub_id from publication if a pmid exists
    if pubDict['pub_pubmed'] != '':
        with PooledCursor() as cursor:
            cursor.execute('''SELECT pub_id FROM publication WHERE pub_pubmed=%s''', (pubDict['pub_pubmed'],))
            pub_id = cursor.fetchone()[0] if cursor.rowcount != 0 else None
            if pub_id is not None:
                print 'Old Pub_id: ' + str(pub_id)
                return pub_id
            else:
                pmid = True
    ## Insert new values otherwise and return id to pub_id
    if pmid or pubDict['pub_pubmed'] == '':
        with PooledCursor() as cursor:
            cursor.execute('''INSERT INTO publication (pub_authors, pub_title, pub_abstract, pub_journal, pub_volume,
                              pub_pages, pub_month, pub_year, pub_pubmed) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                              RETURNING pub_id''',
                           (pubDict['pub_authors'], pubDict['pub_title'], pubDict['pub_abstract'], pubDict['pub_journal'],
                            pubDict['pub_volume'], pubDict['pub_pages'], pubDict['pub_month'], pubDict['pub_year'],
                            pubDict['pub_pubmed'],))
            pub_id = cursor.fetchone()[0]
            cursor.connection.commit()
            print 'New Pub_id: ' + str(pub_id)
            return pub_id

def insert_new_contents_to_file(contents):
    with PooledCursor() as cursor:
        cursor.execute('''INSERT INTO file (file_contents, file_comments, file_created) VALUES (%s, %s, now())
                          RETURNING file_id''', (contents, 'uploaded from website',))
        file_id = cursor.fetchone()[0]
        cursor.connection.commit()
        print 'New File_id: ' + str(file_id)
        return file_id

def create_new_geneset(args):
    '''
    This function creates new geneset metadata with new data, including publication, and file data
    It also puts the gs_status='delayed', which can be updated later.
    :param args: this contains meta data and file_data
    :return: a results dictionary where {'error': 'None'} is success. Also, return gs_id to be used to make temp file
    '''
    urlString = '/?' + args['formData']
    formData = parse_qs(urlparse(urlString).query, keep_blank_values=True)
    user_id = session['user_id']

    ##Create publication dictionary
    ## Insert into publication and return id
    pubDict = {}
    pubDict["pub_year"] = formData['pub_year'][0]
    pubDict["pub_title"] = formData['pub_title'][0]
    pubDict["pub_pages"] = formData['pub_pages'][0]
    pubDict["pub_authors"] = formData['pub_authors'][0]
    pubDict["pub_volume"] = formData['pub_volume'][0]
    pubDict["pub_abstract"] = formData['pub_abstract'][0]
    pubDict["pub_pubmed"] = formData['pub_pubmed'][0]
    pubDict["pub_month"] = formData['pub_month'][0]
    pubDict["pub_journal"] = formData['pub_journal'][0]

    # Test to see if all values in publication are null
    if all(v == '' for v in pubDict.values()) is True:
        pub_id = None
    else:
        pub_id = insertPublication(pubDict)

    ##insert into file and return file_id
    if 'file_text' in formData:
        if formData['file_text'][0] is not None:
            form_text = formData['file_text'][0].strip('\r')
    elif args['fileData'] is not None:
        form_text = args['fileData']
    else:
        return {'error': 'File upload text is empty'}

    try:
        if form_text is not None:
            file_id = insert_new_contents_to_file(form_text)
    except:
        return {'error': 'File upload text is empty'}

    ## Set permissions and cur id
    permissions = formData['permissions'][0]
    if permissions == 'private':
        cur_id = 5
        gs_groups = '-1'
    else:
        cur_id = 4
        gs_groups = '0'

    ## get gs count
    gs_count = len(form_text.split('\n'))

    gene_identifier = get_identifier_from_form(formData['gene_identifier'][0])

    try:
        with PooledCursor() as cursor:
            cursor.execute('''INSERT INTO production.geneset (usr_id, file_id, gs_name, gs_abbreviation, pub_id, cur_id,
                              gs_description, sp_id, gs_count, gs_groups, gs_gene_id_type, gs_created, gs_status)
                              VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s) RETURNING gs_id''',
                           (user_id, file_id, formData['gs_name'][0], formData['gs_abbreviation'][0], pub_id, cur_id,
                            formData['gs_description'][0], formData['sp_id'][0], gs_count, gs_groups, gene_identifier,
                            'delayed',))
            gs_id = cursor.fetchone()[0]
            cursor.connection.commit()
            print 'Inserted gs_id: ' + str(gs_id)
    except psycopg2.Error as e:
        return {'error': e}
    return {'error': 'None', 'gs_id': gs_id}

def create_temp_geneset_from_value(gsid):
    '''
    This function creates a temp_geneset_value record for a gs_id if it exists
    :param gsid:
    :return: null
    '''
    create_temp_geneset()
    with PooledCursor() as cursor:
        cursor.execute('''SELECT gs_id FROM temp_geneset_value WHERE gs_id=%s''', (gsid,))
        is_geneset_value = cursor.rowcount
        cursor.execute('''SELECT gs_id FROM temp_geneset_meta WHERE gs_id=%s''', (gsid,))
        is_geneset_meta = cursor.rowcount
        if is_geneset_value == 0 and is_geneset_meta == 0:
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


def get_temp_geneset_gsid(gsid):
    '''
    Get geneset value from temp_geneset_meta if it exists
    :param gsid:
    :return:
    '''
    with PooledCursor() as cursor:
        cursor.execute('''SELECT sp_id, gdb_id FROM temp_geneset_meta WHERE gs_id=%s''', (gsid,))
        if cursor.rowcount != 0:
            results = cursor.fetchall()
            meta_sp = results[0][0] if results[0][0] is not None else 0
            meta_gdb = results[0][1] if results[0][1] is not None else 0
            meta = [meta_sp, meta_gdb]
        else:
            meta = [0, 0]
        return meta


def update_species_by_gsid(rargs):
    '''
    (1) convert sp_name into id, (2) insert gs_id if it doesn't exist, (3) update temp_geneset_meta table with sp_id,
    (4) rebuild temp_geneset_value table with new species
    :param rargs: user_id, gs_id, altSpecies
    :return:
    '''
    user_id = rargs['user_id']
    gs_id = rargs['gs_id']
    altSpecies = rargs['altSpecies']
    u = get_user(user_id)
    g = get_geneset(gs_id, user_id, temp=None)
    if u.is_admin or u.is_curator or g:
        create_temp_geneset()
        with PooledCursor() as cursor:
            sp_id = get_species_id_by_name(altSpecies)
            cursor.execute('''SELECT gdb_id FROM temp_geneset_meta WHERE gs_id=%s''', (gs_id,))
            gdb_id = cursor.fetchone()[0] if cursor.rowcount != 0 else None
            cursor.execute('''INSERT INTO temp_geneset_meta (gs_id) SELECT %s WHERE NOT EXISTS (SELECT gs_id FROM
                              temp_geneset_meta WHERE gs_id=%s)''', (gs_id, gs_id,))
            cursor.execute('''UPDATE temp_geneset_meta SET sp_id=%s WHERE gs_id=%s''', (sp_id, gs_id,))
            cursor.execute('''DELETE FROM temp_geneset_value WHERE gs_id=%s''', (gs_id,))
            cursor.connection.commit()
            reparse_file_contents_simple(gs_id, sp_id, gdb_id)
            cursor.connection.commit()
            return {'error': 'None'}
    else:
        return {'error': 'You do not have permission to alter this table'}


def update_identifier_by_gsid(rargs):
    '''
    (1) convert altId into id, (2) insert gs_id if it doesn't exist, (3) update temp_geneset_meta table with gdb_id,
    (4) rebuild temp_geneset_value table with new species
    :param rargs: user_id, gs_id, altSpecies
    :return:
    '''
    user_id = rargs['user_id']
    gs_id = rargs['gs_id']
    altId = rargs['altId']
    u = get_user(user_id)
    g = get_geneset(gs_id, user_id, temp=None)
    if u.is_admin or u.is_curator or g:
        create_temp_geneset()
        with PooledCursor() as cursor:
            gdb_id = get_gdb_id_by_name(altId)
            cursor.execute('''SELECT sp_id FROM temp_geneset_meta WHERE gs_id=%s''', (gs_id,))
            sp_id = cursor.fetchone()[0] if cursor.rowcount != 0 else None
            cursor.execute('''INSERT INTO temp_geneset_meta (gs_id) SELECT %s WHERE NOT EXISTS (SELECT gs_id FROM
                              temp_geneset_meta WHERE gs_id=%s)''', (gs_id, gs_id,))
            cursor.execute('''UPDATE temp_geneset_meta SET gdb_id=%s WHERE gs_id=%s''', (gdb_id, gs_id,))
            cursor.execute('''DELETE FROM temp_geneset_value WHERE gs_id=%s''', (gs_id,))
            cursor.connection.commit()
            reparse_file_contents_simple(gs_id, sp_id, gdb_id)
            cursor.connection.commit()
            return {'error': 'None'}
    else:
        return {'error': 'You do not have permission to alter this table'}


def reparse_file_contents_simple(gs_id, species=None, gdb=None):
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
            species = r[1] if species is None else species
            gdb = r[2] if gdb is None else gdb
            newlines = r[0].split('\n')
            if len(newlines) == 1:
                newlines = r[0].split('\r')
            if gdb < 0:
                gdb = -1 * int(gdb)
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
                            if gene != '' and isinstance(v, float) and gene is not None:
                                gene = str(gene.strip('\n\r '))
                                g = gene.lower()
                                with PooledCursor() as cursor:
                                    cursor.execute('SELECT ode_gene_id FROM gene WHERE LOWER(ode_ref_id) LIKE LOWER(%s) '
                                                   'AND sp_id=%s AND gdb_id=%s', (g, species, gdb,))
                                    s = cursor.fetchall()
                                if len(s) != 0:
                                    for i in s:
                                        with PooledCursor() as cursor:
                                            cursor.execute('''INSERT INTO production.temp_geneset_value
                                                              VALUES (%s, %s, %s, %s)''', (gs_id, i[0], v, gene,))
                                            cursor.connection.commit()
                    return 'True'


def make_file_content_string_from_temp_geneset(gsid):
    contents = ''
    with PooledCursor() as cursor:
        cursor.execute('''SELECT src_id, src_value FROM temp_geneset_value WHERE gs_id=%s''', (gsid,))
        results = cursor.fetchall()
        for i in results:
            contents = contents + str(i[0]) + '\t' + str(i[1]) + '\n'
        return contents


def write_file_contents_to_file(gsid, contents):
    with PooledCursor() as cursor:
        cursor.execute('''UPDATE file SET file_contents=%s FROM geneset
                          WHERE geneset.gs_id=%s AND geneset.file_id=file.file_id''', (contents, gsid,))
        cursor.connection.commit()
        return


def update_geneset_species(gsid):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM (SELECT sp_id FROM geneset WHERE gs_id=%s UNION
                          SELECT sp_id FROM temp_geneset_meta WHERE gs_id=%s) as a''', (gsid, gsid,))
        if cursor.rowcount != 1:
            cursor.execute('''UPDATE geneset gs SET sp_id=t.sp_id FROM temp_geneset_meta t
                              WHERE gs.gs_id=t.gs_id AND t.gs_id=%s''', (gsid,))
            return
        else:
            return


def update_geneset_identifier(gsid):
    with PooledCursor() as cursor:
        cursor.execute('''SELECT * FROM (SELECT gs_gene_id_type FROM geneset WHERE gs_id=%s UNION
                          SELECT gdb_id FROM temp_geneset_meta WHERE gs_id=%s) as a''', (gsid, gsid,))
        if cursor.rowcount != 1:
            cursor.execute('''UPDATE geneset gs SET gs_gene_id_type=t.gdb_id FROM temp_geneset_meta t
                              WHERE gs.gs_gene_id_type=t.gdb_id AND t.gs_id=%s''', (gsid,))
            return
        else:
            return


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
                    cursor.execute('''DELETE FROM extsrc.geneset_value WHERE gs_id=%s;''' % (gsid,))
                    cursor.execute('''INSERT INTO extsrc.geneset_value (gs_id, ode_gene_id, gsv_value, gsv_hits, gsv_source_list,
                                     gsv_value_list, gsv_in_threshold, gsv_date)
                                         SELECT gs_id, ode_gene_id, avg(src_value) as gsv_value,
                                           count(ode_gene_id) as gsv_hits, array_accum(src_id) as gsv_source_list,
                                           array_accum(src_value) as gsv_value_list,'t' as gsv_in_threshold, now() as gsv_date
                                           FROM production.temp_geneset_value
                                           WHERE gs_id=%s GROUP BY gs_id,ode_gene_id ORDER BY ode_gene_id;''' % (gsid,))
                    ## Update geneset sp_id and identifier
                    update_geneset_species(gsid)
                    update_geneset_identifier(gsid)
                    ## delete files from temp tables
                    cursor.execute('''DELETE FROM production.temp_geneset_value WHERE gs_id=%s;''' % (gsid,))
                    cursor.execute('''DELETE FROM production.temp_geneset_meta WHERE gs_id=%s;''' % (gsid,))
                    ## Write contents to file_contents for permanent storage
                    contents = make_file_content_string_from_temp_geneset(gsid)
                    write_file_contents_to_file(gsid, contents)
                    ## Update 'delayed' values to 'normal'
                    cursor.execute('''UPDATE geneset SET gs_status='normal' WHERE gs_id=%s;''', (gsid,))
                    cursor.connection.commit()
                    return {'error': 'None'}
        else:
            return {'error': 'Temp table does not contain GS' + gsid}


