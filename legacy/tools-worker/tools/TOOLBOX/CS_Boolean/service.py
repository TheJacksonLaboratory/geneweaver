"""
Service namespace for the Boolean Algebra tool
"""
import collections

SELECT_ALL_SPECIES_SQL = '''SELECT sp_id, sp_name FROM odestatic.species WHERE sp_id != 0'''


def get_all_geneweaver_species(cursor):
    """

    :return: list of tuples sp_id, sp_name
    """
    # TODO: Use sqlalchemy for this relation
    cursor.execute(SELECT_ALL_SPECIES_SQL)
    result = cursor.fetchall()
    cursor.close()
    return result


def get_all_geneweaver_species_for_boolean(cursor):
    all_species_short = {}
    all_species_full = {}
    species = get_all_geneweaver_species(cursor)
    for species in species:
        all_species_short[species[0]] = "".join(item[0] for item in species[1].split())
        all_species_full[species[0]] = species[1]
    return all_species_short, all_species_full


GET_HOMOLOGS_SQL = '''SELECT hom.hom_source_id, g.ode_gene_id, g.ode_ref_id, g.sp_id, gv.gs_id, gs.gs_abbreviation
                            FROM gene g NATURAL JOIN geneset_value gv NATURAL
                            JOIN geneset gs LEFT JOIN
                              (SELECT ode_gene_id, hom_source_id 
                                    FROM homology 
                                    WHERE hom_source_name = 'Homologene' 
                                    AND hom_source_id IN
                                      (SELECT hom_source_id 
                                          FROM homology h, geneset_value gv2
                                          WHERE h.ode_gene_id = gv2.ode_gene_id
                                          AND gv2.gs_id IN {0}
                                          AND gv2.gsv_in_threshold
                                      )
                                    AND sp_id IN ({1})
                              ) hom
                              ON g.ode_gene_id = hom.ode_gene_id
                            WHERE gv.gs_id IN {0}
                            AND gv.gsv_in_threshold
                            AND g.gdb_id = 7 
                            AND g.ode_pref = TRUE
                              ORDER BY hom.hom_source_id, gv.gs_id'''


def get_homologs_for_geneset(cursor, geneset_ids, species_ids=None):
    """

    :param cursor:
    :param geneset_ids:
    :param species_ids:
    :return:
    """
    species_ids = species_ids or get_species_in_genesets(cursor, geneset_ids)
    sql = GET_HOMOLOGS_SQL.format(tuple(geneset_ids), ",".join(str(sid) for sid in species_ids))
    cursor.execute(sql)
    results = cursor.fetchall()
    cursor.close()
    return results


def group_homologs(homologs, species_ids):
    """
    Groups homolog records by a key determined from the homolog data and species context.

    - For multiple species, groups by homolog[0] (hom_source_id).
    - For a single species, groups by homolog[1] (ode_gene_id).
    - If homolog[0] is falsy, uses -1 * homolog[1] as the key.

    Each group contains a deduplicated list of
    [ode_gene_id, ode_ref_id, sp_id, gs_id, gs_abbreviation] lists.

    :param homologs: Iterable of homolog tuples, typically from a database query.
    :param species_ids: List of species IDs used to determine grouping logic.
    :return: Dictionary mapping group keys to deduplicated lists of homolog data.
    """

    bool_results = {}
    for homolog in homologs:
        key = homolog[0]
        if len(species_ids) == 1:
            key = homolog[1]
        elif not homolog[0]:
            key = -1 * homolog[1]
        current_val = bool_results.get(key, [])
        # Keep gs_abbreviation (homolog[5]); the result template renders it as the
        # geneset name at record index [4] (e.g. the Symmetric Difference heading).
        # A prior py2->py3 refactor sliced [1:5] and dropped it, which crashed
        # BooleanAlgebra_result.html on record[4] (GWC-50).
        current_val.append(homolog[1:6])
        bool_results[key] = current_val

    # Robust deduplication: convert to tuple, deduplicate, convert back to list
    for key in bool_results:
        group = bool_results[key]
        seen = set()
        deduped = []
        for item in group:
            t = tuple(item)
            if t not in seen:
                seen.add(t)
                deduped.append(list(t))
        bool_results[key] = deduped

    bool_results = {i[0]: i[1] for i in sorted(list(bool_results.items()), key=lambda t: len(t[1][0]))}
    return bool_results


def get_grouped_homologs_for_genesets(geneset_ids, species_ids=None, homolog_data=None):
    """

    :param geneset_ids:
    :param species_ids:
    :param homolog_data:
    :return:
    """
    species_ids = species_ids or get_species_in_genesets(cursor, geneset_ids)
    homolog_data = homolog_data or get_homologs_for_geneset(geneset_ids, species_ids)
    return group_homologs(homolog_data, species_ids)


def get_species_in_genesets(cursor, geneset_ids):
    """
    Get a unique list of species ids found in the genesets ids provided
    :param cursor:
    :param geneset_ids:
    :return:
    """
    species_ids = []
    for g_id in geneset_ids:
        cursor.execute('''SELECT DISTINCT sp_id FROM production.geneset WHERE gs_id=%s''' % g_id, )
        res = cursor.fetchall()
        for r in res:
            species_ids.append(int(r[0]))
    return list(set(species_ids))


def cluster_genes(homolog_data, species_ids):
    """
    Cluster result genes based on shared and unique genes per species
    This will be placed in a d3 graph on the site

    It will report:
    A. the number of genes unique to each species
    B. the number of genes/species/intersection
    C. the number of genes per species
    :param homolog_data:
    :param species_ids:
    :return:
    """
    genes_per_geneset = {sp: {'unique': [], 'intersection': [], 'species': []} for sp in species_ids}

    for homolog in homolog_data:
        genes_per_geneset[homolog[3]]['species'].append(homolog[0])

    gene_comparision_list_all = []
    gene_comparision_list_sp = []
    for outer_species_id in species_ids:
        for inner_species_id in species_ids:
            if outer_species_id != inner_species_id:
                gene_comparision_list_all.extend(genes_per_geneset[inner_species_id]['species'])
            else:
                gene_comparision_list_sp.extend(genes_per_geneset[inner_species_id]['species'])
        genes_per_geneset[outer_species_id]['unique'].extend(
            list(set(gene_comparision_list_sp) - set(gene_comparision_list_all)))
        del gene_comparision_list_all[:]
        del gene_comparision_list_sp[:]

    # Loop through this set to find all genes that appear in another species
    gene_intersection_list = []
    for i in range(0, len(species_ids)):
        for j in range(0, len(genes_per_geneset[species_ids[i]]['species'])):
            for k in range(0, len(species_ids)):
                if i != k:
                    if genes_per_geneset[species_ids[i]]['species'][j] in genes_per_geneset[species_ids[k]]['species']:
                        gene_intersection_list.append(genes_per_geneset[species_ids[i]]['species'][j])
        genes_per_geneset[species_ids[i]]['intersection'].extend(gene_intersection_list)
        del gene_intersection_list[:]

    return genes_per_geneset


def intersect(bool_results, at_least=2):
    """
    Filters and deduplicates groups in the input dictionary, then organizes them by intersection size.

    - Only groups with at least `at_least` elements are retained.
    - Each group's list is deduplicated based on the value of element 3 in each item (gs_id).
    - The result is a dictionary mapping intersection sizes to dictionaries of group keys and their deduplicated lists.

    :param bool_results: Dictionary mapping group keys to lists of items (each item is a list).
    :param at_least: Minimum number of elements required for a group to be included (default: 2).
    :return: Dictionary where keys are intersection sizes and values are dicts of group keys to deduplicated lists.
    """
    # Filter groups with at least the required number of elements
    intersect_results = {key: value for key, value in bool_results.items() if len(value) >= int(at_least)}

    for key in intersect_results:
        group = intersect_results[key]
        if not group:
            continue
        # Deduplicate based on (item[0], item[3])
        seen = set()
        deduped = []
        for item in group:
            uniq = item[3]
            if uniq not in seen:
                seen.add(uniq)
                deduped.append(item)
        intersect_results[key] = deduped

    intersection_sizes = collections.defaultdict(dict)
    for k, v in intersect_results.items():
        size = len(v)
        intersection_sizes[size][k] = v

    return dict(intersection_sizes)


def bool_except(bool_results):
    """

    :param bool_results:
    :param intersection_sizes:
    :return:
    """

    bool_except = collections.defaultdict(dict)
    intersects = {key: value for key, value in bool_results.items() if len(value) >= int(2)}

    # make a dict of all values in the except list
    except_results = {key: value for key, value in bool_results.items() if key not in intersects}

    # We need to re-sort this list so that genesets are
    # grouped together
    compare = collections.defaultdict(list)
    for key, value in except_results.items():
        compare[value[0][3]].append(key)

    # make the groups numbered 1 - n, this is easier than
    # the intersect case because we do not need to take
    # into account a list
    i = 0
    for key, value in compare.items():
        for j in range(0, len(value)):
            for k, v in except_results.items():
                if int(k) == int(value[j]):
                    bool_except[i][value[j]] = v
        i += 1
    return bool_except


def create_circle_code(bool_results):
    gps = collections.defaultdict(list)
    for key, value in bool_results.items():
        for k in bool_results[key]:
            gps[key].append(k[3])
    return gps
