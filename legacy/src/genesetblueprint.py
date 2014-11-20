import flask
import geneweaverdb
import pubmedsvc
import re

geneset_blueprint = flask.Blueprint('geneset', 'geneset')


@geneset_blueprint.route('/uploadgeneset.html')
def render_uploadgeneset():
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

    return flask.render_template(
        'uploadgeneset.html',
        gs=dict(),
        all_species=geneweaverdb.get_all_species(),
        gidts=gidts)


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
    for id_kind_tuple, success_id_set in id_kind_mapping_dict.iteritems():
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


@geneset_blueprint.route('/creategeneset.html', methods=['POST'])
def create_geneset():
    # TODO START IMPLEMENTATION NOTES (remove these once impl is complete)
    #
    # in php code this corresponds to the Manage.php::editgeneset(...) function with $cmd set to "uploadgeneset"
    # uploadTemplate followed by uploadTemplate_step2 seems to do the main work (NOTE: 'file_text' request
    # variable contains all IDs)
    #
    # END IMPLEMENTATION NOTES

    form = flask.request.form
    print form 
    sp_id = int(form['sp_id'])

    file_text = form['file_text']
    file_lines = file_text.splitlines()
    candidate_sep_regexes = ['\t', ',', ' +']

    

    for curr_toks in tokenize_lines(candidate_sep_regexes, file_lines):
        # TODO php code allows multiple IDs per line. Do we need to continue to allow this? for now expecting 1 ID per line
        curr_id = ''
        curr_val = None
        counts_by_source = dict()
        all_results = []
        if len(curr_toks) >= 1:
            curr_id = curr_toks[0]
            if len(curr_toks) >= 2:
                try:
                    curr_val = float(curr_toks[1])

                    # We'll get results from both the gene table and platform table. We'll decide later which to use
                    # based on the number of results returned.
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
                        all_results += gene_results
                        if gene_results:
                            result_sources = set()

                            for curr_result in gene_results:
                                key_tuple = (True, curr_result['source'])
                                curr_counts = None
                                try:
                                    curr_counts = counts_by_source[key_tuple]
                                except KeyError:
                                    curr_counts = [0, 0]
                                    counts_by_source[key_tuple] = curr_counts

                                # we need to make sure not to double count a source here
                                if curr_result['source'] not in result_sources:
                                    curr_counts[0] += 1
                                curr_counts[1] += 1

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
                        platform_results = list(cursor)
                        if platform_results:
                            first_result = platform_results

                    if not (gene_results or platform_results):
                        # TODO tell user we didn't find a match for curr_id
                        pass

                except ValueError:
                    # TODO error reporting here
                    pass

    return flask.render_template(
        'uploadgeneset.html',
        gs=dict(),
        all_species=geneweaverdb.get_all_species())


@geneset_blueprint.route('/viewgeneset-<int:geneset_id>.html')
def view_geneset(geneset_id):
    user_id = flask.g.user.user_id if 'user' in flask.g else None
    geneset = geneweaverdb.get_geneset(geneset_id, user_id)

    return flask.render_template('viewgeneset.html', geneset=geneset)


@geneset_blueprint.route('/qproject-<int:project_id>-genesets.json')
def project_genesets(project_id):
    pass
