import re
import batch
import json
import sys
import urllib
import flask

import geneweaverdb
import pubmedsvc
import annotator as ann
from decorators import login_required, create_guest
import curation_assignments


geneset_blueprint = flask.Blueprint('geneset', 'geneset')

# gets species and gene identifiers for uploadgeneset page
@geneset_blueprint.route('/uploadgeneset', methods=['POST', 'GET'])
@geneset_blueprint.route('/uploadgeneset/<genes>', methods=['POST', 'GET'])
@login_required()
def render_uploadgeneset(genes=None):
    gidts = []

    user_id = flask.session['user_id'] if 'user_id' in flask.session else 0

    my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)

    for gene_id_type_record in geneweaverdb.get_gene_id_types():
        gidts.append((
            'gene_{0}'.format(gene_id_type_record['gdb_id']),
            gene_id_type_record['gdb_name']))

    microarray_id_sources = []
    for microarray_id_type_record in geneweaverdb.get_microarray_types():
        microarray_id_sources.append((
            'ma_{0}'.format(microarray_id_type_record['pf_id']),
            microarray_id_type_record['pf_name']))
    gidts.append(('MicroArrays', microarray_id_sources))

    if genes:
        return flask.render_template(
            'uploadgeneset.html',
            gs=dict(),
            all_species=geneweaverdb.get_all_species(),
            gidts=gidts,
            genes=genes)
    elif flask.request.form and flask.request.form['tool']:
        return flask.render_template(
            'uploadgeneset.html',
            gs=dict(),
            all_species=geneweaverdb.get_all_species(),
            gidts=gidts,
            genes=genes,
            myGroups=my_groups,
            tool_data=json.dumps(flask.request.form)
            )
    else:
        return flask.render_template(
            'uploadgeneset.html',
            gs=dict(),
            all_species=geneweaverdb.get_all_species(),
            gidts=gidts,
            user_id=user_id,
            myGroups=my_groups)


@geneset_blueprint.route('/batchupload')
@login_required()
def render_batchupload(genes=None):
    gidts = []
    for gene_id_type_record in geneweaverdb.get_gene_id_types():
        gidts.append((
            'gene_{0}'.format(gene_id_type_record['gdb_id']),
            gene_id_type_record['gdb_name']))

    microarray_id_sources = []
    for microarray_id_type_record in geneweaverdb.get_microarray_types():
        microarray_id_sources.append((
            'ma_{0}'.format(microarray_id_type_record['pf_id']),
            microarray_id_type_record['pf_name']))
    gidts.append(('MicroArrays', microarray_id_sources))

    all_species = geneweaverdb.get_all_species()
    user_id = flask.g.user.user_id
    my_groups = geneweaverdb.get_all_owned_groups(user_id) + geneweaverdb.get_all_member_groups(user_id)

    return flask.render_template('batchupload.html', gs=dict(), all_species=all_species, gidts=gidts, groups=my_groups)

@geneset_blueprint.route('/createBatchGeneset', methods=['POST'])
@login_required(json=True)
def create_batch_geneset():
    """
    Attempts to parse a batch file and create a temporary GeneSet for review.
    """
    if not flask.request.form:
        return flask.jsonify({'error': "Can't access upload form."})

    batch_file = flask.request.form.get('batchFile')
    if not batch_file:
        return flask.jsonify({'error': 'No batch file was provided.'})

    curation_group = flask.request.form.get('curation_group')
    if not curation_group:
        return flask.jsonify({'error': 'No curation group selected'})
    else:
        curation_group = json.loads(curation_group)

    batch_file = flask.request.form['batchFile']

    ## The data sent to us should be URL encoded
    batch_file = urllib.parse.unquote(batch_file)
    batch_file = batch_file.split('\n')

    user = flask.g.user
    user_id = user.user_id

    batch_reader = batch.BatchReader(batch_file, user_id)

    ## Required later on when inserting OmicsSoft specific metadata
    is_omicssoft = False

    ## Needs to be redone
    #if batch.is_omicssoft(batch_file):
    #    batch_file = batch.parse_omicssoft(batch_file, user_id)
    #    batch_file = (batch_file, [], [])
    #    is_omicssoft = True

    #else:
        ## List of gene set objects 
    genesets = batch_reader.parse_batch_file()

    ## Bad things happened during parsing...
    if not genesets:
        return flask.jsonify({'error': batch_reader.errors})

    ## Publication info for gene sets that have PMIDs
    batch_reader.get_geneset_pubmeds()

    ## Now try inserting everything into the DB. We bypass normal gene set
    ## insertion (the create_geneset stored procedure) so we can report 
    ## errors to the user and process any custom fields like ontology
    ## annotations
    new_ids = batch_reader.insert_genesets()

    ## This will need to be redone
    if is_omicssoft:
        for gs in batch_file[0]:
            project = gs['project'] if 'project' in gs else ''
            source = gs['source'] if 'source' in gs else ''
            tag = gs['tag'] if 'tag' in gs else ''
            otype = gs['type'] if 'type' in gs else ''

            geneweaverdb.insert_omicssoft_metadata(
                gs['gs_id'], project, source, tag, otype
            )

    curation_note = "Geneset created in batch by {} {}".format(user.first_name, user.last_name)
    for gs_id in new_ids:
            curation_assignments.submit_geneset_for_curation(gs_id, curation_group, curation_note)

    return flask.jsonify({
        'genesets': new_ids, 
        'warn': batch_reader.warns,
        'error': batch_reader.errors
    })


def tokenize_lines(candidate_sep_regexes, lines):
    """
    This function will tokenize all of the following lines and in doing so will attempt to infer which
    among the given candidate_sep_regexes is used as a token separator.
    """

    detected_sep_regex = None
    for line_num, curr_line in enumerate(lines):
        curr_line = curr_line.strip()

        # if the line is empty or just whitespace we're not going to skip it
        if curr_line:
            tokenized_line = None

            # if we haven't yet detected a separator try now
            if not detected_sep_regex:
                for candidate_regex in candidate_sep_regexes:
                    tokenized_line = re.split(candidate_regex, curr_line)
                    if len(tokenized_line) >= 2:
                        detected_sep_regex = candidate_regex
                        break
            else:
                tokenized_line = re.split(detected_sep_regex, curr_line)

            tokenized_line = [tok.strip() for tok in tokenized_line]
            yield tokenized_line


@geneset_blueprint.route('/pubmed_info/<pubmed_id>.json')
def pubmed_info_json(pubmed_id):
    pubmed_info = pubmedsvc.get_pubmed_info(pubmed_id)
    return flask.jsonify(pubmed_info)


@geneset_blueprint.route('/inferidkind.json', methods=['POST'])
def infer_id_kind():
    gene_table_sql = \
        '''
        SELECT gdb_id AS source, sp_id
        FROM gene
        WHERE LOWER(ode_ref_id)=%s
        GROUP BY source, sp_id;
        '''
    probe_table_sql = \
        '''
        SELECT m.pf_id AS source, m.sp_id
        FROM platform m, probe p
        WHERE p.pf_id=m.pf_id AND LOWER(prb_ref_id)=%s
        GROUP BY source, m.sp_id;
        '''

    form = flask.request.form
    file_text = form['file_text']
    file_lines = file_text.splitlines()
    candidate_sep_regexes = ['\t', ',', ' +']
    id_kind_mapping_dict = dict()
    input_id_list = []

    with geneweaverdb.PooledCursor() as cursor:
        def add_counts(curr_id, use_gene_table):
            cursor.execute(gene_table_sql if use_gene_table else probe_table_sql, (curr_id.lower(),))
            for source_id, sp_id in cursor:
                key_tuple = (use_gene_table, source_id, sp_id)
                if key_tuple in id_kind_mapping_dict:
                    id_kind_mapping_dict[key_tuple].add(curr_id)
                else:
                    id_kind_mapping_dict[key_tuple] = set([curr_id])

        for curr_toks in tokenize_lines(candidate_sep_regexes, file_lines):
            if curr_toks:
                input_id_list.append(curr_toks[0])
                add_counts(curr_toks[0], True)
                add_counts(curr_toks[0], False)

    # find which ID kinds worked best and return those
    max_success_count = 1
    most_successfull_id_kinds = []
    for id_kind_tuple, success_id_set in id_kind_mapping_dict.items():
        (is_gene_result, source_id, sp_id) = id_kind_tuple

        def item_as_dict():
            return {
                'is_gene_result': is_gene_result,
                'source_id': 'gene_{0}'.format(source_id) if is_gene_result else 'ma_{0}'.format(source_id),
                'species_id': sp_id,
                'id_failures': [x for x in input_id_list if x not in success_id_set]
            }

        curr_success_count = len(success_id_set)
        if curr_success_count == max_success_count:
            most_successfull_id_kinds.append(item_as_dict())
        elif curr_success_count > max_success_count:
            max_success_count = len(success_id_set)
            most_successfull_id_kinds = [item_as_dict()]

    return flask.jsonify(
        most_successfull_id_kinds=most_successfull_id_kinds,
        total_id_count=len(set(input_id_list)))


def derive_score_type(min_val, max_val):
    """Derive ``(gs_threshold_type, gs_threshold)`` for a tool-created geneset from
    its observed value range.

    ``gs_threshold`` is a bare string (e.g. ``'0.5'``, ``'0,1'``, ``'0.2'``) with no
    embedded quotes: the caller supplies SQL quoting via a bound parameter, and
    ``recompute_geneset_value_thresholds`` parses it with ``float()`` / ``split(',')``.
    The previous inline version wrapped the type-1 and type-5 thresholds in literal
    single quotes, which the old ``'%s'``-interpolated UPDATE then double-quoted into
    malformed SQL.

    The ``0.25 <= max <= 0.5`` band previously matched no branch and left the score
    type ``None``, so ``process_thresholds`` / ``recompute_geneset_value_thresholds``
    flagged nothing and the whole set read out-of-threshold. It is now folded into the
    P-Value branch (threshold = max), continuous with the ``max < 0.25`` case and
    leaving every value in-threshold. (G3-809)
    """
    if min_val >= -1 and max_val <= 1:
        if min_val >= 0 and max_val <= 1:
            if min_val == max_val and max_val == 1:
                return 3, '0.5'                 # Binary
            elif max_val > 0.5:
                return 4, '0,1'                 # Correlation
            else:                               # max_val <= 0.5 (closes the old None gap)
                return 1, str(max_val)          # P-Value
        else:
            return 4, '0,1'                     # Correlation (min < 0)
    else:
        return 5, str(min_val) + ',' + str(max_val)   # Effect


def _store_tool_geneset_values(gs_id, unique_gene_ids, all_results):
    """Store the ``geneset_value`` rows for a tool-created geneset, derive its score
    type + threshold, set ``gs_count``, and compute ``gsv_in_threshold`` through the
    one shared implementation the batch and score-type-edit paths use
    (``geneweaverdb.recompute_geneset_value_thresholds``).

    Extracted from two byte-identical inline blocks in ``create_temp_geneset``
    (``/createtempgeneset``) and ``create_geneset`` (``/creategeneset.html``). Those
    blocks flagged ``gsv_in_threshold`` from a hardcoded ``avg in [-1, 1]`` rule that
    matched no score type and ran *before* ``gs_threshold_type`` was known, and never
    called ``process_thresholds`` or ``recompute_geneset_value_thresholds`` -- so
    tool-created genesets carried membership that disagreed with every other create
    path, and migration 117 / the Python threshold fixes never reached them. (G3-809)
    """
    min_val = False
    max_val = False
    for ode_gene_id in unique_gene_ids:
        values = []
        sources = []
        for res in all_results:
            if res['ode_gene_id'] == ode_gene_id:
                sources.append(res['ref_id'])
                values.append(res['value'] if res['value'] else 1)

        avg = 0
        for val in values:
            # `== False` (not `is False`) is preserved from the original inline
            # blocks: it feeds only the score-type heuristic below, and changing the
            # sentinel would shift derived score types for sets containing a 0. That
            # is a separate pre-existing quirk, out of scope for the membership fix.
            if min_val == False or val < min_val:  # noqa: E712
                min_val = val
            if max_val == False or val > max_val:  # noqa: E712
                max_val = val
            avg += val
        avg /= len(values)

        # Membership is computed below by recompute_geneset_value_thresholds once the
        # score type is known; store a False placeholder here.
        #
        # Fully parameterised: psycopg2 adapts the Python lists to PostgreSQL arrays
        # itself. Hand-building the array literals here (joining `sources` with '","')
        # broke on any stored reference identifier containing a quote or backslash --
        # a malformed array literal, or worse -- and interpolating a query string is
        # exactly what the repo guardrail forbids on a line being touched.
        gs_value_sql = (
            "INSERT INTO extsrc.geneset_value"
            "(gs_id, ode_gene_id, gsv_value, gsv_source_list, gsv_value_list, gsv_hits, gsv_in_threshold) "
            "VALUES (%s,%s,%s,%s,%s,%s,%s);"
        )
        with geneweaverdb.PooledCursor() as cursor:
            cursor.execute(gs_value_sql,
                           (gs_id, ode_gene_id, avg, sources, values, 0, False))
            cursor.connection.commit()

    gs_threshold_type, gs_threshold = derive_score_type(min_val, max_val)

    # gs_count: count the rows actually inserted (one per distinct ode_gene_id). The
    # previous formula counted gene *identifier rows* (geneset_value NATURAL JOIN gene
    # WHERE ode_pref), which roughly doubled the count since genes carry more than one
    # preferred identifier, and returned no row at all for an empty set. Search and My
    # Genesets render gs_count while the geneset page runs its own count(*)
    # (get_genecount_in_geneset), so drift here surfaces as the two disagreeing
    # (GWC-34 / G3-782).
    with geneweaverdb.PooledCursor() as cursor:
        cursor.execute('SELECT count(*) FROM extsrc.geneset_value WHERE gs_id=%s;',
                       (gs_id,))
        gs_count = cursor.fetchone()[0]

        # Parameterized UPDATE (the old form interpolated gs_threshold into a '%s'
        # literal, which double-quoted the quoted type-1/5 strings). Then compute
        # membership through the shared helper now that the score type is known.
        cursor.execute(
            'UPDATE production.geneset SET gs_count=%s, gs_threshold=%s, '
            'gs_threshold_type=%s WHERE gs_id=%s;',
            (gs_count, gs_threshold, gs_threshold_type, gs_id))
        geneweaverdb.recompute_geneset_value_thresholds(
            cursor, gs_id, gs_threshold_type, gs_threshold)
        cursor.connection.commit()


@geneset_blueprint.route('/createtempgeneset', methods=['POST'])
def create_temp_geneset():
    #Try to load the form, catching errors, etc.
    try:
        form = flask.request.form
        gs_name = form['gs_name']
        gs_abbreviation = form['gs_abbreviation']
        gs_description = form['gs_description']
        public_private = form['permissions']
        sp_id = form['species']
        gene_identifier = form['gene_identifier']

        user_id = flask.g.user.user_id if 'user' in flask.g else None
        if user_id == None:
            return {"Error": "You must be signed in to upload a GeneSet."}


        if sp_id == 0 or sp_id == "0":
            return {"Error": "Select a species."}

        file_text = ""
        file_lines = ""
        if 'file_text' in form:
            file_text = form['file_text']
            file_lines = file_text.splitlines()
        else:
            return "File currently not implemented."
        # get lines from the file here

        candidate_sep_regexes = ['\t', ',', ' +']

        all_results = []
        invalid_genes = []
        unique_gene_ids = []

        for curr_toks in tokenize_lines(candidate_sep_regexes, file_lines):
            curr_id = ''
            curr_val = None

            if len(curr_toks) >= 1:
                curr_id = curr_toks[0]
                if len(curr_toks) >= 2:
                    curr_val = float(curr_toks[1])
                try:
                    # getting gene table results
                    gene_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, gdb_id AS source, ode_ref_id AS ref_id
                            FROM gene
                            WHERE sp_id=%s AND LOWER(ode_ref_id)=%s;
                            ''',
                            (sp_id, curr_id.lower())
                        )
                        gene_results = list(geneweaverdb.dictify_cursor(cursor))
                        # if there are gene results, add to list of all results and put ode_gene_id into unique gene_id list
                        if gene_results:
                            gene_results[0].update({'value': curr_val})

                            # adds to geneID list if unique
                            if gene_results[0]['ode_gene_id'] not in unique_gene_ids:
                                unique_gene_ids.append(gene_results[0]['ode_gene_id'])

                            all_results += gene_results

                            # getting platform results
                    platform_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, m.pf_id AS source, prb_ref_id AS ref_id, pf_set
                            FROM platform m,probe p,probe2gene p2g
                            WHERE p.pf_id=m.pf_id AND p2g.prb_id=p.prb_id AND m.sp_id=%s AND LOWER(prb_ref_id)=%s
                            GROUP BY ode_gene_id, m.pf_id, prb_ref_id, m.pf_set;
                            ''',
                            (sp_id, curr_id.lower())
                        )
                        platform_results = list(geneweaverdb.dictify_cursor(cursor))

                        # if there are platform genes, add to list of all results and put ode_gene_id into unique gene_id list
                        if platform_results:
                            platform_results[0].update({'value': curr_val})

                            # adds to geneID list if unique
                            if platform_results[0]['ode_gene_id'] not in unique_gene_ids:
                                unique_gene_ids.append(platform_results[0]['ode_gene_id'])

                            all_results += platform_results

                    if not (gene_results or platform_results):
                        invalid_genes.append(curr_id)
                        pass

                except Exception as e:
                    return str(e)
                    pass



        # if any genes in the list were not found it will tell the user which were not found
        if len(invalid_genes) > 0:
            return "Unable to find these Genes for specified species:\n" + ', '.join(
                invalid_genes) + "\n\nEither remove them and resubmit the GeneSet or contact GeneWeaver to have them added."
        if len(all_results) < 1:
            return "No genes found to enter"

        pub_id = None
        if form['pub_pubmed'] != None and form['pub_pubmed'] != "":
            exists = True
            with geneweaverdb.PooledCursor() as cursor:
                pubcheck = None
                cursor.execute('''SELECT pub_id FROM production.publication where pub_pubmed=%s;''',
                               (form['pub_pubmed'],))
                try:
                    pubcheck = cursor.fetchone()[0]
                except Exception:
                    pubcheck = None

                if pubcheck:
                    pub_id = pubcheck
                else:
                    exists = False
            if exists == False:
                cols = dict()
                reg = re.compile('pub_*')
                for item in form.keys():
                    if re.match(reg, item):
                        if form[item]:
                            cols.update({item: form[item]})
                if len(cols) > 0:
                    values = []
                    keys = []
                    for item in cols.keys():
                        values.append(cols[item])
                        keys.append(item)
                    with geneweaverdb.PooledCursor() as cursor:
                        pub_sql = '''INSERT INTO production.publication(%s) VALUES ('%s') RETURNING pub_id;''' % (
                        ','.join(keys), '\',\''.join(values),)
                        cursor.execute(pub_sql)
                        cursor.connection.commit()
                        pub_id = cursor.fetchone()[0]
                        print(pub_sql)

        file_id = None
        with geneweaverdb.PooledCursor() as cursor:
            file_sql = '''INSERT INTO production.file(file_size, file_contents) VALUES (%s, '%s') RETURNING file_id;''' % (
            len(file_text), file_text,)
            cursor.execute(file_sql)
            cursor.connection.commit()
            file_id = cursor.fetchone()[0]
            print(file_sql)

        if file_id == None:
            return "Error: Cannot create file"

        cur_id = None
        if public_private == "public":
            cur_id = 4
        else:
            cur_id = 5

        gs_id = "None";
        with geneweaverdb.PooledCursor() as cursor:
            GS_sql = '''INSERT INTO production.geneset(gs_name, gs_description, gs_abbreviation, sp_id, usr_id, gs_created, cur_id, file_id, gs_status, gs_count) VALUES ('%s','%s','%s','%s',%s,now(),%s,%s,'%s',%s) RETURNING gs_id;''' % (
            gs_name, gs_description, gs_abbreviation, sp_id, user_id, cur_id, file_id, "normal", 0)
            cursor.execute(GS_sql)
            cursor.connection.commit()
            gs_id = cursor.fetchone()[0]
            print(GS_sql)
            if gs_id == None:
                return "Error: Unable to get GeneSet ID."

            if pub_id:
                pub_sql = '''UPDATE production.geneset SET pub_id=%s WHERE gs_id=%s;''' % (pub_id, gs_id)
                cursor.execute(pub_sql)
                cursor.connection.commit()
                print(pub_sql)



        _store_tool_geneset_values(gs_id, unique_gene_ids, all_results)

        return "GeneSet Created"
    except Exception as e:
        return str(e)

@geneset_blueprint.route('/creategeneset.html', methods=['POST'])
def create_geneset():
    try:
        form = flask.request.form
        print(form)

        gs_name = form['gs_name']
        gs_abbreviation = form['gs_abbreviation']
        gs_description = form['gs_description']
        public_private = form['permissions']
        sp_id = form['species']
        gene_identifier = form['gene_identifier']

        user_id = flask.g.user.user_id if 'user' in flask.g else None
        if user_id == None:
            return "You must be signed in to upload a GeneSet."

        if sp_id == 0 or sp_id == "0":
            return "Select a species."

        file_text = ""
        file_lines = ""
        if 'file_text' in form:
            file_text = form['file_text']
            file_lines = file_text.splitlines()
        else:
            return "File currently not implemented."
        # get lines from the file here

        candidate_sep_regexes = ['\t', ',', ' +']

        all_results = []
        invalid_genes = []
        unique_gene_ids = []

        for curr_toks in tokenize_lines(candidate_sep_regexes, file_lines):
            curr_id = ''
            curr_val = None

            if len(curr_toks) >= 1:
                curr_id = curr_toks[0]
                if len(curr_toks) >= 2:
                    curr_val = float(curr_toks[1])
                try:
                    # getting gene table results
                    gene_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, gdb_id AS source, ode_ref_id AS ref_id
                            FROM gene
                            WHERE sp_id=%s AND LOWER(ode_ref_id)=%s;
                            ''',
                            (sp_id, curr_id.lower())
                        )
                        gene_results = list(geneweaverdb.dictify_cursor(cursor))
                        # if there are gene results, add to list of all results and
                        # put ode_gene_id into unique gene_id list
                        if gene_results:
                            gene_results[0].update({'value': curr_val})

                            # adds to geneID list if unique
                            if gene_results[0]['ode_gene_id'] not in unique_gene_ids:
                                unique_gene_ids.append(gene_results[0]['ode_gene_id'])

                            all_results += gene_results

                            # getting platform results
                    platform_results = None
                    with geneweaverdb.PooledCursor() as cursor:
                        cursor.execute(
                            '''
                            SELECT ode_gene_id, m.pf_id AS source, prb_ref_id AS ref_id, pf_set
                            FROM platform m,probe p,probe2gene p2g
                            WHERE p.pf_id=m.pf_id AND p2g.prb_id=p.prb_id AND m.sp_id=%s AND LOWER(prb_ref_id)=%s
                            GROUP BY ode_gene_id, m.pf_id, prb_ref_id, m.pf_set;
                            ''',
                            (sp_id, curr_id.lower())
                        )
                        platform_results = list(geneweaverdb.dictify_cursor(cursor))

                        # if there are platform genes, add to list of all results and put ode_gene_id into unique gene_id list
                        if platform_results:
                            platform_results[0].update({'value': curr_val})

                            # adds to geneID list if unique
                            if platform_results[0]['ode_gene_id'] not in unique_gene_ids:
                                unique_gene_ids.append(platform_results[0]['ode_gene_id'])

                            all_results += platform_results

                    if not (gene_results or platform_results):
                        invalid_genes.append(curr_id)
                        pass

                except Exception as e:
                    return str(e)
                    pass



        # if any genes in the list were not found it will tell the user which were not found
        if len(invalid_genes) > 0:
            return "Unable to find these Genes for specified species:\n" + ', '.join(
                invalid_genes) + "\n\nEither remove them and resubmit the GeneSet or contact GeneWeaver to have them added."
        if len(all_results) < 1:
            return "No genes found to enter"

        pub_id = None
        if form['pub_pubmed'] != None and form['pub_pubmed'] != "":
            exists = True
            with geneweaverdb.PooledCursor() as cursor:
                pubcheck = None
                cursor.execute('''SELECT pub_id FROM production.publication where pub_pubmed=%s;''',
                               (form['pub_pubmed'],))
                try:
                    pubcheck = cursor.fetchone()[0]
                except Exception:
                    pubcheck = None

                if pubcheck:
                    pub_id = pubcheck
                else:
                    exists = False
            if exists == False:
                cols = dict()
                reg = re.compile('pub_*')
                for item in form.keys():
                    if re.match(reg, item):
                        if form[item]:
                            cols.update({item: form[item]})
                if len(cols) > 0:
                    values = []
                    keys = []
                    for item in cols.keys():
                        values.append(cols[item])
                        keys.append(item)
                    with geneweaverdb.PooledCursor() as cursor:
                        pub_sql = '''INSERT INTO production.publication(%s) VALUES ('%s') RETURNING pub_id;''' % (
                        ','.join(keys), '\',\''.join(values),)
                        cursor.execute(pub_sql)
                        cursor.connection.commit()
                        pub_id = cursor.fetchone()[0]
                        print(pub_sql)

        file_id = None
        with geneweaverdb.PooledCursor() as cursor:
            file_sql = '''INSERT INTO production.file(file_size, file_contents) VALUES (%s, '%s') RETURNING file_id;''' % (
            len(file_text), file_text,)
            cursor.execute(file_sql)
            cursor.connection.commit()
            file_id = cursor.fetchone()[0]
            print(file_sql)

        if file_id == None:
            return "Error: Cannot create file"

        cur_id = None
        if public_private == "public":
            cur_id = 4
        else:
            cur_id = 5

        gs_id = "None";
        with geneweaverdb.PooledCursor() as cursor:
            GS_sql = '''INSERT INTO production.geneset(gs_name, gs_description, gs_abbreviation, sp_id, usr_id, gs_created, cur_id, file_id, gs_status, gs_count) VALUES ('%s','%s','%s','%s',%s,now(),%s,%s,'%s',%s) RETURNING gs_id;''' % (
            gs_name, gs_description, gs_abbreviation, sp_id, user_id, cur_id, file_id, "normal", 0)
            cursor.execute(GS_sql)
            cursor.connection.commit()
            gs_id = cursor.fetchone()[0]
            print(GS_sql)
            if gs_id == None:
                return "Error: Unable to get GeneSet ID."

            if pub_id:
                pub_sql = '''UPDATE production.geneset SET pub_id=%s WHERE gs_id=%s;''' % (pub_id, gs_id)
                cursor.execute(pub_sql)
                cursor.connection.commit()
                print(pub_sql)



        _store_tool_geneset_values(gs_id, unique_gene_ids, all_results)

        return "GeneSet Created"
    except Exception as e:
        return str(e)


@geneset_blueprint.route('/viewgeneset-<int:geneset_id>.html')
def view_geneset(geneset_id):
    user_id = flask.g.user.user_id if 'user' in flask.g else None
    geneset = geneweaverdb.get_geneset(geneset_id, user_id)

    return flask.render_template('viewgeneset.html', geneset=geneset)


@geneset_blueprint.route('/qproject-<int:project_id>-genesets.json')
def project_genesets(project_id):
    pass

