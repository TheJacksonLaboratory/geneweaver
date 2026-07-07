#!/usr/bin/python
# USAGE: Combine.py input.odemat input.odepwd < parameters_json.txt > output_json.txt 2>status.txt

import re
import math
import json
from collections import defaultdict, OrderedDict

import tools.toolbase
from tools.celeryapp import celery


class AutoVivification(dict):
    def __getitem__(self, item):
        try:
            return dict.__getitem__(self, item)
        except KeyError:
            value = self[item] = type(self)()
            return value


class ABBA(tools.toolbase.GeneWeaverToolBase):
    name = "tools.ABBA.ABBA"

    def __init__(self, *args, **kwargs):
        self.init("ABBA")
        self.urlroot = ''

    def mainexec(self, usid=0):

        # Set default values for parameters
        output_prefix = self._parameters["output_prefix"]  # {.el,.dot,.png}
        geneset_id = self._gsids
        usr_id = 0
        tierset = []
        min_genes = -1
        restrict_option = 0
        restrict_species = []
        min_genesets = -1
        update = False
        homology = 1
        include_hom = 'Yes'
        task = re.sub('-', '', self._parameters["output_prefix"])

        #########################################################
        # Get all of the tool specifications information
        #

        if 'UserId' in self._parameters:
            user_id = self._parameters['UserId']

        if 'ABBA_MinGenes' in self._parameters:
            try:
                min_genes = int(self._parameters['ABBA_MinGenes'])
            except Exception:
                pass

        if 'ABBA_MinGenesets' in self._parameters:
            if str(self._parameters['ABBA_MinGenes']) != 'auto':
                try:
                    min_genesets = int(self._parameters['ABBA_MinGenesets'])
                except Exception:
                    pass

        if 'ABBA_Tierset' in self._parameters:
            try:
                for tier in self._parameters['ABBA_Tierset']:
                    tierset.append(int(tier))
            except Exception:
                pass

        if 'ABBA_RestrictOption' in self._parameters:
            try:
                restrict_option = int(self._parameters['ABBA_RestrictOption'])
            except Exception:
                pass

        # Only store if restrict species is set
        if restrict_option == 1:
            if 'ABBA_RestrictSpecies' in self._parameters:
                for sp in self._parameters['ABBA_RestrictSpecies']:
                    restrict_species.append(sp)

        # Ignore Homology
        if 'ABBA_IgnHom' in self._parameters:
            homology = 0
            include_hom = 'No'
        else:
            homology = 1

        input_genes = []
        if 'ABBA_InputGenes' in self._parameters:
            for gene in self._parameters['ABBA_InputGenes']:
                input_genes.append(gene.lower())

        # Get all species
        species = OrderedDict()
        cur = self.db.cursor()
        cur.execute("SELECT sp_id, sp_name FROM odestatic.species ORDER BY sp_id;")
        for row in cur:
            species[row[0]] = row[1]

        # This bit of mess is because psycopg2 does not like to use the 'IN'
        # clause. Concatenated lists are joined here as strings and appended
        # to teh sql query
        #
        # species
        if restrict_option != 1:
            sp_ids = list(species.keys())
        else:
            sp_ids = restrict_species

        sp = ' IN (' + ",".join(str(x) for x in sp_ids) + ') '

        # curation tiers
        if len(tierset) == 1:
            tierset = ' IN (' + str(tierset[0]) + ') '
        else:
            tierset = ' IN (' + ",".join(str(x) for x in tierset) + ') '
        #
        #
        #################################################################

        #################################################################
        #################################################################
        # create temp tables. Based on bitbucket notes, we need to append
        # the task (id) to the table names in order for simultaneous ABBA
        # queries to run properly
        #
        #
        # we must reset the restrict species, and curation tiers based on the
        # selection
        # sp_ids = restrict_species if restrict_species != 1 else list(species.keys())
        # cur_tiers = curation_tiers if curation_tiers != 1 else list(tiers.keys())
        #

        #
        # Need to add genes from geneset_id to the input_genes list
        if len(geneset_id) != 0:
            temp_list_ref_ids = []
            geneset_id = [int(g[2:]) for g in geneset_id]
            sql = ' IN (' + ",".join(str(x) for x in geneset_id) + ')'
            query = cur.mogrify('''SELECT DISTINCT ode_ref_id FROM extsrc.gene g, extsrc.geneset_value gsv
                            WHERE gsv.gs_id %s AND gsv.gsv_in_threshold AND gsv.ode_gene_id=g.ode_gene_id''' % (sql,))
            cur.execute(query)
            results = cur.fetchall()
            for res in results:
                temp_list_ref_ids.append(str(res[0]))
            # concatenate with the text-based list
            input_genes = list(set(input_genes + temp_list_ref_ids))

        # input genes
        if len(input_genes) == 1:
            in_genes = ' IN (\'' + str(input_genes[0].lower().replace("'", "''")) + '\') '
        else:
            in_genes = ' IN (\'' + "\',\'".join(
                str(x.lower().replace("'", "''")) for x in input_genes) + '\') '

        # Create temp table for input genes--
        temp_table_name = 'ABBA_input_genes' + task
        cur.execute('''DROP TABLE IF EXISTS %s''' % (temp_table_name,))
        if len(input_genes) > 1:
            query = cur.mogrify('''CREATE TEMP TABLE %s AS
                            SELECT * FROM extsrc.gene WHERE lower(ode_ref_id) %s
                            AND sp_id %s
                            AND gdb_id=7''' % (temp_table_name, in_genes, sp,))
        else:
            query = cur.mogrify('''CREATE TEMP TABLE %s AS
                            SELECT * FROM extsrc.gene WHERE lower(ode_ref_id) %s
                            AND sp_id %s
                            AND gdb_id=7''' % (temp_table_name, in_genes, sp,))
        print(query)
        cur.execute(query)

        #
        # Genes of Interest Table (Input Genes + Homologies)--
        temp_table_interest = 'ABBA_genes_of_interest' + task
        cur.execute('''DROP TABLE IF EXISTS %s''' % (temp_table_interest,))
        if homology == 1:
            query = cur.mogrify('''CREATE TEMP TABLE %s AS
                            (SELECT * FROM extsrc.gene
                              WHERE ode_gene_id IN
                                (SELECT ode_gene_id FROM extsrc.homology WHERE hom_id IN
                                  (SELECT hom_id FROM homology H
                                    JOIN %s IG ON H.ode_gene_id=IG.ode_gene_id))
                              AND gdb_id=7
                              AND ode_pref=true
                              AND sp_id %s)
                              UNION DISTINCT (SELECT * FROM %s)''' %
                                (temp_table_interest, temp_table_name, sp, temp_table_name))
        else:
            query = cur.mogrify('''SELECT * FROM %s''' % (temp_table_name,))
        cur.execute(query)

        # Matching Genesets table--
        temp_table_matching = 'ABBA_matching_genesets' + task
        cur.execute('''DROP TABLE IF EXISTS %s''' % (temp_table_matching,))
        query = cur.mogrify('''CREATE TEMP TABLE %s AS
                        SELECT count(ode_gene_id) AS geneMatchCount, gs.*
                          FROM extsrc.geneset_value gv JOIN production.geneset gs ON gv.gs_id=gs.gs_id
                            WHERE ode_gene_id IN
                            (SELECT ode_gene_id FROM %s)
                            AND gs_status='normal'
                            AND gv.gsv_in_threshold
                            AND (ARRAY(SELECT grp_id FROM production.usr2grp WHERE usr_id=%s)
                            ||0 @> string_to_array(gs_groups, ',')::int[]) GROUP BY gs.gs_id''' %
                            (temp_table_matching, temp_table_interest, user_id,))
        cur.execute(query)

        # Result Genes Table--
        temp_table_results = 'ABBA_result_genes' + task
        if min_genes > -1:
            min_g = min_genes
        else:
            min_g = 'least((SELECT count(DISTINCT ode_ref_id) FROM ' + str(temp_table_interest) + '),1)'

        cur.execute('''DROP TABLE IF EXISTS %s''' % (temp_table_results,))
        query = cur.mogrify('''CREATE TEMP TABLE %s AS
                        SELECT gi.*, count(gv.ode_gene_id) AS occurrences FROM extsrc.geneset_value gv 
                          JOIN extsrc.gene_info gi ON gv.ode_gene_id=gi.ode_gene_id 
                          WHERE gv.gsv_in_threshold AND gv.gs_id IN
                          (SELECT gs_id FROM %s WHERE geneMatchCount>=%s 
                            AND cur_id %s AND sp_id %s)
                          group by gi.ode_gene_id HAVING lower(gi.gi_symbol) NOT IN
                            (SELECT DISTINCT lower(ode_ref_id) FROM %s)''' %
                            (temp_table_results, temp_table_matching, min_g, tierset,
                             sp, temp_table_interest,))
        cur.execute(query)

        self.db.commit()

        #
        #
        #######################################################

        #######################################################
        #######################################################
        # sql queries for returning metadata for results
        #
        #

        # Get number of available genes--
        cur.execute('''SELECT count(*) FROM extsrc.gene WHERE gdb_id=7 AND ode_pref=TRUE;''')
        available_gene_count = cur.fetchall()[0][0]

        # Get number of available genesets for user--
        cur.execute('''SELECT count(*) FROM production.geneset WHERE cur_id %s''' % (tierset,))
        available_gs_count = cur.fetchall()[0][0]

        # Return genes of interest--
        cur.execute('''SELECT DISTINCT ON (a.ode_gene_id) a.ode_gene_id, a.ode_ref_id, b.sp_name FROM %s AS a,
                        odestatic.species AS b WHERE a.sp_id=b.sp_id ORDER BY a.ode_gene_id''' % (temp_table_interest,))
        genes_of_interest = cur.fetchall()

        # Return a unique set of species from temp table
        cur.execute('''SELECT DISTINCT(b.sp_name) FROM %s AS a,
                        odestatic.species AS b WHERE a.sp_id=b.sp_id''' % (temp_table_interest,))
        input_species = cur.fetchall()

        # Return matching genesets--
        cur.execute('''SELECT gs_id, gs_name, geneMatchCount, cur_id, sp_id, gs_attribution, gs_abbreviation, 
                          gs_description, gs_count  
                        FROM %s WHERE geneMatchCount >= %s AND cur_id %s 
                        ORDER BY geneMatchCount DESC, gs_count LIMIT 50''' % (temp_table_matching, min_genes,tierset,))

        gs_results = cur.fetchall()

        # Return result genes--
        cur.execute('''SELECT * FROM (
                        SELECT DISTINCT ON (a.ode_gene_id) a.ode_gene_id, b.ode_ref_id, c.sp_name, c.sp_id, a.occurrences
                        FROM %s as a, gene as b, species as c
                          WHERE a.ode_gene_id=b.ode_gene_id AND b.sp_id=c.sp_id AND a.occurrences >= %s)
                          AS results ORDER BY occurrences DESC LIMIT 50''' %
                    (temp_table_results, min_genesets,))
        gene_results = cur.fetchall()

        # Return a list of ode_ref_ids and sp_ids for ode_gene_ids. This should clarify the result list.
        ode_mapping = defaultdict(list)
        preferred_mapping = defaultdict(str)
        for gr in gene_results:
            cur.execute('''SELECT ode_ref_id FROM extsrc.gene WHERE ode_gene_id=%s AND gdb_id=7''' % (gr[0],))
            results = cur.fetchall()
            cur.execute(
                '''SELECT ode_ref_id FROM extsrc.gene WHERE ode_gene_id=%s AND gdb_id=7 AND ode_pref='t' ''' % (gr[0],))
            pref_results = cur.fetchall()

            for res in results:
                ode_mapping[gr[0]].append(res[0])

            for res in pref_results:
                preferred_mapping[gr[0]] = res[0]

        # Return max occurrences for bar graph
        cur.execute('''SELECT occurrences FROM %s ORDER BY occurrences DESC LIMIT 1''' % (temp_table_results,))
        max_occurrences = cur.fetchall()
        #
        #
        #######################################################

        #################################################################
        #################################################################
        #
        # Return a dictionary of dictionaries for number of
        # genesets by curation Tier
        #

        cur_counts = defaultdict(dict)
        for results in gene_results:
            cur.execute('''SELECT count(gs.gs_id) as gs_count, gs.cur_id 
                              FROM production.geneset gs, extsrc.geneset_value gsv 
                                WHERE gs.gs_id=gsv.gs_id AND gsv.ode_gene_id=%s AND gs.cur_id IS NOT NULL 
                                  AND gs.gs_status NOT LIKE 'de%%'
                                  AND gsv.gsv_in_threshold
                                GROUP BY gs.cur_id ORDER BY gs.cur_id''' % (results[0],))
            res = cur.fetchall()
            for r in res:
                cur_counts[results[0]][r[1]] = r[0]

        # replace zeros (yuck)
        for i in [1, 2, 3, 4, 5]:
            for key, value in cur_counts.items():
                if i not in value:
                    cur_counts[key][i] = 0

        # rewrite the cur_counts as a dictionary of lists (to more easily translate in the graph)
        # (we use a defaultdict() since it was used previously. I'm not sure we need it @aberger@jax.org)
        cur_counts_list = defaultdict(list, {
            key: [v for _, v in sorted(list(value.items()))]
            for key, value in cur_counts.items()
        })
        #
        #
        #################################################################

        #################################################################
        #################################################################
        #
        # Return a dictionary of dictionaries for number of
        # genesets per gene
        #

        sp_counts = defaultdict(dict)
        sp_counts_list = defaultdict(list)
        for results in gene_results:
            cur.execute('''SELECT count(gs.gs_id) as gs_count, gs.sp_id 
                              FROM production.geneset gs, extsrc.geneset_value gsv
                                WHERE gs.gs_id=gsv.gs_id AND gsv.ode_gene_id IN
                                  (SELECT h1.ode_gene_id FROM extsrc.homology h1, extsrc.homology h2
                                    WHERE h1.hom_id=h2.hom_id AND h2.ode_gene_id=%s)
                                AND gsv.gsv_in_threshold
                                AND gs.gs_status NOT LIKE 'de%%'
                                GROUP BY gs.sp_id ORDER BY gs.sp_id''' % (results[0],))
            res = cur.fetchall()
            for r in res:
                sp_counts[results[0]][r[1]] = math.log(float(r[0]))

            # replace zeros (yuck)
            for i in [1, 2, 3, 4, 5, 6, 8, 9, 10, 11]:
                for key, value in sp_counts.items():
                    if i not in value:
                        sp_counts[key][i] = 0

            # rewrite the sp_counts as a dictionary of lists (to more easily translate in the graph)
            # (we use a defaultdict() since it was used previously. I'm not sure we need it @aberger@jax.org)
            sp_counts_list = defaultdict(list, {
                key: [value for _, value in sorted(list(value.items()))]
                for key, value in sp_counts.items()
            })

        #
        #
        #################################################################

        # Save parameters
        self._results['Tiersets'] = [1, 2, 3, 4, 5]
        self._results['SelectedTierset'] = tierset
        self._results['IncludeHomology'] = include_hom

        if int(restrict_option) == 0:
            self._results['RestrictSpecies'] = 'No'
        else:
            self._results['RestrictSpecies'] = "Yes"

        self._results['AvailableGenes'] = available_gene_count
        self._results['AvailableGenesets'] = available_gs_count
        self._results['Max'] = max_occurrences
        self._results['TierCounts'] = cur_counts_list
        self._results['SpeciesCounts'] = sp_counts_list

        if min_genesets == -1:
            min_genesets = "Auto"

        self._results['InputGenes'] = input_genes
        self._results['InputSpecies'] = input_species

        self._results['MinGenesets'] = min_genesets
        self._results['MinGenes'] = self._parameters['ABBA_MinGenes']

        self._results['GenesOfInterestCount'] = len(genes_of_interest)
        self._results['GenesOfInterest'] = genes_of_interest

        self._results['GenesetResultsCount'] = len(gs_results)
        self._results['GenesetResults'] = gs_results

        self._results['GeneResultsCount'] = len(gene_results)
        self._results['GeneResults'] = gene_results

        self._results['OdeMapping'] = ode_mapping
        self._results['PrefMapping'] = preferred_mapping

        #
        #
        ###############################################################

        ###############################################################
        ###############################################################
        # dump the dictionary into a json file that will be read
        # by the template
        #

        with open(output_prefix + '.json', 'w') as fp:
            json.dump(self._results, fp)

        #
        #
        ###############################################################

    @staticmethod
    def is_numeric(var):
        try:
            float(var)
        except ValueError:
            return False
        return True


ABBA = celery.register_task(ABBA())
