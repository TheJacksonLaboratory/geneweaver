#!/usr/bin/python
# USAGE: PhenomeMap.py -m=input.odemat < parameters_json.txt > output_json.txt 2>status.txt

import cgi
import html
import os
import re
import subprocess
from collections import defaultdict
from functools import reduce

import numpy as np

import tools.toolbase
from tools.celeryapp import celery


class Biclique:
    # id: unique integer for this biclique
    # gs: frozenset(geneset id strings)
    # genes_dict: gene_id => gene rank
    # emphasize: True if this biclique should be highlighted in the output
    # label, tooltip, url: relevant dot output features
    def __init__(self, id, gs, genes_dict, emphasize, label, tooltip, url):
        self.id = id

        self.size = len(gs)
        self.genesets = gs

        self.num_genes = float(len(genes_dict))
        self.genes = set(genes_dict)
        self.ranks = list(genes_dict.values())

        self.displayed = True  # set to False if biclique should be hidden in output

        self.parents = {}  # parent bicliques => similarity scores (edge weights)
        self.children = {}  # child bicliques => similarity scores (edge weights)

        self.emphasize = emphasize
        self.label = label
        self.tooltip = tooltip
        self.url = url

    # hash: simply the unique id given to this biclique
    def __hash__(self):
        return self.id


################################################################################

# some helper functions

# two-sample kolmogorov-smirnov statistic
# adapted from scipy implementation
def ks_2samp(data1, data2):
    data1 = np.asarray(data1)
    data2 = np.asarray(data2)
    data1.sort()
    data2.sort()
    n1, n2 = float(data1.size), float(data2.size)
    data_all = np.concatenate([data1, data2])
    cdf1 = np.searchsorted(data1, data_all, side='right') / n1
    cdf2 = np.searchsorted(data2, data_all, side='right') / n2
    d = np.max(np.absolute(cdf1 - cdf2))  # our test statistic

    if d > np.finfo('float').eps:
        en = np.sqrt(n1 * n2 / (n1 + n2))
        prob = ksprob((en + 0.12 + 0.11 / en) * d)  # ksprob defined below
    else:  # difference too small to care
        prob = 1.0

    return d, prob


# CDF for KS statistic:
# P(sqrt(n)*Dn < x) = sqrt(2pi) / x * sum{i=(1,inf,2)}(e^-(8*(i*pi/x)^2))
# see: http://www.jstatsoft.org/v08/i18/paper
# tested against the scipy implementation; matches to >= 15 decimal places

# KS_CONST is the part of our equation not including x; it turns out this only
#     requires, like, i from 1 to 5, instead of infinity.a
KS_CONST = -(np.arange(1, 7, 2, dtype=float) * np.pi) ** 2 / 8
# x is the KS test statistic from ks_2samp (Dn)
ksprob = lambda x: 1 - np.sqrt(2 * np.pi) / x * np.sum(np.exp(KS_CONST / x ** 2))


def similarity(parent, child):
    jaccard = parent.num_genes / child.num_genes
    ks_test = ks_2samp(parent.ranks, child.ranks)[1]
    return ks_test * jaccard


set_union = lambda x, y: x | y


################################################################################

class PhenomeMap(tools.toolbase.GeneWeaverToolBase):
    name = "tools.PhenomeMap.PhenomeMap"

    def __init__(self, *args, **kwargs):
        self.init("PhenomeMap")
        self._comb_cache = {}

    def combtl(self, n, r):
        if r == 0:
            return 1
        key = "%d,%d" % (n, r)
        if key in self._comb_cache:
            return self._comb_cache[key]

        r = int(min(r, n - r))
        i = int(n) - r + int(1)
        j = int(1)
        cnr = int(1)
        while i <= n or j <= r:
            if i <= n:
                cnr *= i
                i += int(1)
            if j <= r:
                cnr /= j
                j += int(1)

        self._comb_cache[key] = cnr
        return cnr

    def mainexec(self):
        output_prefix = self._parameters["output_prefix"]  # {.el,.dot,.png}
        # output_prefix = self._parameters.get("output_prefix")
        include_homology = self._parameters['PhenomeMap_Homology'] == 'Included'
        # include_homology = self._parameters.get('PhenomeMap_Homology')=='Included'
        try:
            self._results['gs_ids'] = self._gsids
        except:
            self._results['gs_ids'] = None

        max_level = int(self._parameters["PhenomeMap_MaxLevel"])
        min_genes = int(self._parameters["PhenomeMap_MinGenes"])
        max_in_node = int(self._parameters["PhenomeMap_MaxInNode"])
        num_permutations = int(self._parameters['PhenomeMap_Permutations'])
        permutation_time_limit = int(self._parameters['PhenomeMap_PermutationTimeLimit'])
        bootstrap_disabled = self._parameters['PhenomeMap_DisableBootstrap'] == 'True'

        p_value_threshold = float(self._parameters['PhenomeMap_p-Value'])
        if p_value_threshold == 0.:
            p_value_threshold = 1.0
        useFDR = self._parameters['PhenomeMap_UseFDR'] == 'True'

        emphasis_genes = []
        do_emphasis_check = 0

        if 'EmphasisGenes' in self._parameters:
            emphasis_genes = [abs(int(g)) for g in self._parameters['EmphasisGenes']]
            do_emphasis_check = len(emphasis_genes)

        # create a dictionary from associated arrays for faster lookup
        # gs_id => gs_name
        gs_dict = dict(zip(self._gsids, self._gsnames))

        num_edges = 0

        genes = {}
        DOT_FILE = open("%s.el" % output_prefix, "w")
        print("%d\t%d\t%d" % (self._num_genes, self._num_genesets, num_edges), file=DOT_FILE)

        # r = ode_gene_id, gene symbol, [genesets for that gene]
        for r in self._matrix:
            genes[abs(int(r[0]))] = r[1]  # ode_gene_id => gene symbol
            i = 0
            for e in r[2:]:
                if int(e):
                    print("%s\t%s" % (r[0], self._gsids[i]), file=DOT_FILE)
                i += 1

        DOT_FILE.close()
        ################################################################################

        self.update_progress('Running maximal biclique enumeration algorithm ...')

        args = ("%s/TOOLBOX/biclique_tool/biclique" % self.TOOL_DIR, "%s.el" % output_prefix, "-p")
        proc = subprocess.Popen(args, stdout=subprocess.PIPE, text=True, encoding="utf-8")

        # number of genesets => list of bicliques containing that many genesets
        bicliques = defaultdict(list)

        line_num = 0
        num_bicliques = 0
        for line in proc.stdout:
            line_num += 1
            if line_num % 3 == 0:
                continue  # empty line

            line = line.strip().split('\t')
            if line_num % 3 == 1:  # list of genesets
                genesets = frozenset(line)
                continue

            num_bicliques += 1

            n_genes = 0  # count number of genes in the biclique
            emphasize = 0
            genes_str = ''

            for g in line:
                n_genes += 1
                ode_gene_id = abs(int(g))
                genes_str += ',' + str(ode_gene_id)
                if do_emphasis_check == 0 or ode_gene_id in emphasis_genes:
                    emphasize += 1
            if n_genes < min_genes:  # not enough genes in this biclique to worry about
                continue

            # get gene ranks for the genes in this biclique
            self.cur.execute("""
                                SELECT ode_gene_id, gene_rank FROM gene_info WHERE ode_gene_id=ANY(%s);
                        """, ('{' + genes_str[1:] + '}',))
            # ode_gene_id => gene rank
            genes_dict = dict((g, float(gr)) for g, gr in self.cur)

            # get names for genesets and a comma-separated list of geneset ids
            gsidstr = ''
            toplabel = ''
            shortlabel = ''
            for i, gs in enumerate(genesets):
                gsid = gs[2:]
                if gsidstr != '':
                    gsidstr += ','
                gsidstr += gsid

                gs_name = html.escape(gs_dict[gs])
                toplabel += '%s: %s;\n' % (gs, gs_name)

                # Create shorter version of toplabel
                if i < 5:
                    small_name = gs_name[:42]
                    if len(gs_name) > 42:
                        small_name += '...'
                    shortlabel += '%s: %s;\n' % (gs, small_name)
            if i >= 5:
                shortlabel += '...;\n(%i gene sets);\n' % (len(genesets),)

            # add biclique to node list
            genelabel = ''
            if n_genes <= max_in_node:
                x = 0
                for ode_gene_id in genes_dict:
                    if x != 0:
                        genelabel += ', '
                    if x % 5 == 4:
                        genelabel += '\n'
                    genelabel += genes[ode_gene_id]
                    x += 1
            else:
                genelabel = "%d genes" % (len(genes_dict))

            self.cur.execute("""
                                SELECT COUNT(DISTINCT pub_id) FROM geneset where gs_id=ANY(%s);
                        """, ('{' + gsidstr + '}',))
            n_pub = self.cur.fetchone()[0]
            publabel = '%d publication%s;\n' % (n_pub, 's' if n_pub != 1 else '')

            label = '%s;\n %s(%s)' % (toplabel, publabel, genelabel)
            # Modified EJB - I removed short labels
            # label = '%s"+"\n"++; %s(%s)' % (shortlabel,publabel,genelabel)
            tooltip = '%s\n %s(%s)' % (toplabel, publabel, genelabel)
            if len(genesets) == 1:
                url = '/viewgenesetdetails/%s' % (gsidstr)
            else:
                # This is the page for the intersection, this will change too.
                # url = '/index.php?action=analyze&cmd=intersection&gsids=%s' % (gsidstr,)
                # if include_homology:
                #    url += '&homology=Included'
                url = ''

            biclique = Biclique(num_bicliques, genesets, genes_dict, emphasize > 0, label, tooltip, url)

            bicliques[len(genesets)].append(biclique)

        # bicliques is now a list of (size,list) pairs, ordered by size ascending
        bicliques = sorted(list(bicliques.items()), key=lambda k: k[0])

        if not bicliques:
            raise Exception('No bicliques')

        ################################################################################

        new_num_bicliques = 0
        cut_depth = 0

        def find_cut_depth():
            cut_depth = 0
            if max_level == 0:
                return num_bicliques, cut_depth
            total = 0
            # find the cut-depth for the tree
            for size, bicliques_list in reversed(bicliques[1:]):
                levelcount = sum(b.displayed for b in bicliques_list)
                total += levelcount
                if levelcount > max_level:
                    cut_depth = size
                    prevnotes = ''
                    if 'notes' in self._results:
                        prevnotes = self._results['notes'] + '<br/><br/>'
                    self._results['notes'] = """%sThere are %d %d-way intersections, so we
                                                cut the tree before this level in order to keep the results
                                                manageable. (MaxLevel=%d)""" % (prevnotes, levelcount, size, max_level)
            return total, cut_depth

        new_num_bicliques, cut_depth = find_cut_depth()

        bstrap_edges = {}
        if new_num_bicliques > 100 and not bootstrap_disabled:
            self._results['notes'] = """Your original Phenome Map contained more
                                than 100 distinct intersections, so we applied a
                                Bootstrapping reduction filter to reduce the complexity.
                                Bootstrapping was done for 1000 iterations with a 75%
                                sampling rate. Displayed nodes and blue edges passed a 50%
                                cutoff threshold, and descendent nodes were added to fill out
                                the graph structure. (set DisableBootstrap=True to skip bootstrapping)
                                """
            self.update_progress("Large graph, applying bootstrapping...")
            bicfile = open("%s.bic" % output_prefix, "w")
            index_to_bicliques = {}  # index in biclique file => biclique object
            i = 0
            for size, bicliques_list in bicliques:
                for b in bicliques_list:
                    print("\t".join(genes[g] for g in b.genes), file=bicfile)
                    print("\t".join(b.genesets), file=bicfile)
                    b.displayed = False
                    index_to_bicliques[i] = b
                    i += 1
            bicfile.close()
            args = ('%s/TOOLBOX/bstrap/bstrap' % (self.TOOL_DIR,),
                    '%s.bic' % (output_prefix,), 'x', '-i', '1000 0.75', '-t', '12')
            proc = subprocess.Popen(args, stderr=subprocess.PIPE, text=True, encoding="utf-8")
            bstrap_set = True  # switch between nodes and edges; nodes=True
            for line in proc.stderr:
                e = line.strip()
                if e == '':
                    bstrap_set = not bstrap_set
                    continue

                if bstrap_set:
                    index_to_bicliques[int(e)].displayed = True
                else:
                    e = e.split("\t")
                    ids = (index_to_bicliques[int(e[0])], index_to_bicliques[int(e[1])])
                    bstrap_edges[ids] = float(e[2])
            new_num_bicliques, _ = find_cut_depth()

        ################################################################################

        # find parent/child bicliques
        self.update_progress('Determining Subset Relationships...')

        p_values = []
        n_touched = len(bicliques[0][1])
        for i in range(1, len(bicliques)):  # start at the next-to-smallest bicliques
            for biclique in bicliques[i][1]:  # for every biclique of that size
                bicliques_covered = set()  # keep track of all descendant bicliques
                for j in range(i - 1, -1, -1):
                    for b in bicliques[j][1]:
                        if b.genesets < biclique.genesets:  # is this a child biclique?
                            if b not in bicliques_covered:  # not a known descendant?
                                sim = similarity(biclique, b)
                                biclique.children[b] = sim
                                b.parents[biclique] = sim
                                bicliques_covered.add(b)  # add it as a descendant, at any rate
                                p_values.append(sim)
                            bicliques_covered |= set(b.children)  # add children as descendants
            n_touched += len(bicliques[i][1])
            self.update_progress('', n_touched * 100.0 / num_bicliques)

        # trim children based on given p-value threshold
        if p_value_threshold < 0.99999:
            # False Discovery Rate correction (Benjamini-Hochberg)
            if useFDR:
                n = len(p_values)
                p_values = np.array(p_values)
                p_values.sort()
                fdr_range = np.linspace(p_value_threshold / n, p_value_threshold, n)
                threshold = fdr_range[np.where(p_values > fdr_range)[0][0]]
                self.update_progress('FDR limit: %f' % threshold)
            else:
                threshold = p_value_threshold

            # trim children not meeting threshold
            for size, bicliques_list in bicliques[:-1]:
                for biclique in bicliques_list:
                    to_remove = []
                    for p, sim in biclique.parents.items():
                        if sim > threshold:
                            to_remove.append(p)
                    for p in to_remove:
                        del biclique.parents[p]
                        del p.children[biclique]

                    ################################################################################

        # trim unconnected nodes
        self.update_progress('Preprocessing Nodes...')

        # trim graph first by removing unwanted node sizes
        i = 0
        max_width = 0  # maximum number of bicliques for any size
        while i < len(bicliques):
            size, bicliques_list = bicliques[i]
            if size <= cut_depth:  # bicliques too small; cut them
                bicliques.pop(i)
                continue

            # remove nodes which aren't displayed or have no parents or children
            j = 0
            while j < len(bicliques_list):
                b = bicliques_list[j]
                if not b.displayed or not b.parents and not b.children:
                    bicliques_list.pop(j)
                else:
                    j += 1

            # if all bicliques of this size were removed, remove this size
            if not bicliques_list:
                bicliques.pop(i)
            else:
                if max_width < len(bicliques_list):
                    max_width = len(bicliques_list)
                i += 1

            ################################################################################

        if not bicliques:
            raise Exception('No bicliques')

        ################################################################################
        ################################################################################
        # Add method to collect all proj_id's associated with the user, and
        # highlight based on the project. MeSH/GO/MP/etc. can be seen as specieal
        # classes
        #
        #

        # only select genes which are in "root" nodes (i.e. not having parents)
        # that aren't separate from everything else (i.e. having children)
        selected_genes = reduce(set_union, (b.genes
                                            for size, bicliques_list in bicliques
                                            for b in bicliques_list if not b.parents and b.children))

        ######################################################################
        # Added by EJB
        #

        ### self.update_progress('Obtaining Project Gene Information...')

        ### #get Project Names for Genes that belong to current user
        ### self.cur.execute("""
        ###     SELECT a.gs_id, c.pj_name as project_name FROM geneset a, project2geneset b, project c
        ###     WHERE c.usr_id=%s and c.pj_id=b.pj_id and b.gs_id=a.gs_id;""",
        ###     (str(self.usr_id),))
        ### proj_terms = dict((gs_id, project_name) for gs_id, project_name in self.cur)
        ###
        ### proj_to_genes = defaultdict(set)
        ### genes_to_proj = defaultdict(set)

        ### #get gs_id, ode_gene_id, and gene_rank from projects
        ### self.cur.execute("""
        ###     SELECT gs_id, ode_gene_id, 0.0
        ###     FROM geneset_value
        ###     WHERE gs_id=ANY(%s);""",
        ###     ('{'+','.join(str(gs_id) for gs_id in proj_terms)+'}',))

        ### #add ids to genes and genes to ids
        ### for gs_id, ode_gene_id, gene_rank in self.cur:
        ###     if ode_gene_id in selected_genes:
        ###         proj_to_genes[gs_id].add(ode_gene_id)
        ###         genes_to_proj[ode_gene_id].add(gs_id)

        ### #add terms(proj names) to genes in the biclique results
        ### proj_selected_terms = set()
        ### for size, bicliques_list in bicliques:
        ###         for b in bicliques_list:
        ###                 terms = defaultdict(int)
        ###                 for g in b.genes:
        ###                         for t in genes_to_proj[g]:
        ###                                 terms[t] += 1
        ###                 for t,n in terms.iteritems():
        ###                         b.proj_terms[t] = n / b.num_genes
        ###                 proj_selected_terms.update(terms)

        #
        #
        ###########################################################################

        ### self.update_progress('Obtaining Mesh Gene Information...')
        ###
        ### # get MESH terms for genes
        ### self.cur.execute("""
        ###         SELECT gs_id, gs_name FROM geneset
        ###         WHERE gs_name LIKE '%MeSH%' AND gs_name NOT LIKE '%CTD%';""")
        ### # mesh gs_id => mesh term
        ### mesh_terms = dict((gs_id,gs_name[:gs_name.find(' MeSH')].strip("'"))
        ###                  for gs_id, gs_name in self.cur)

        ### # mesh gs_id => list(genes in any of any of our genesets)
        ### mesh_to_genes = defaultdict(set)
        ### gene_to_mesh = defaultdict(set) # gene id => list(mesh gs_id)
        ### #mesh_ranks = defaultdict(list)
        ###
        ### self.cur.execute("""
        ###         SELECT gs_id, ode_gene_id, gene_rank
        ###         FROM geneset_value JOIN gene_info USING(ode_gene_id)
        ###         WHERE gs_id=ANY(%s);""",
        ###         ('{'+','.join(str(gs_id) for gs_id in mesh_terms)+'}',))
        ###
        ### for gs_id, ode_gene_id, gene_rank in self.cur:
        ###         #mesh_ranks[gs_id].append(float(gene_rank))
        ###         if ode_gene_id in selected_genes:
        ###                 mesh_to_genes[gs_id].add(ode_gene_id)
        ###                 gene_to_mesh[ode_gene_id].add(gs_id)

        ### mesh_selected_terms = set()
        ### for size,bicliques_list in bicliques:
        ###         for b in bicliques_list:
        ###                 terms = defaultdict(int)
        ###                 for g in b.genes:
        ###                         for t in gene_to_mesh[g]:
        ###                                 terms[t] += 1
        ###                 for t,n in terms.iteritems():
        ###                         b.mesh_terms[t] = n / b.num_genes
        ###                 mesh_selected_terms.update(terms)

        ################################################################################

        #                # bicliques_list id => mesh term
        #                significant_terms = defaultdict(set)
        #                self.update_progress('Running Anderson-Darling tests...')
        #                for b,(gs,genes) in enumerate(izip(bicliques_list,genes_list)):
        #                        gene_ids = set(genes)
        #                        terms = reduce(lambda x,y: x | y, (gene_to_mesh[g] for g in gene_ids))
        #                        n_genes = len(genes)
        #                        n_terms = 0
        #                        for t in terms:
        #                                matching = mesh_to_genes[t] & gene_ids
        #                          # if more than half the genes are labeled by this term, use the term
        #                                if len(matching) == n_genes:
        #                                        n_terms += 1
        #                                        #significant_terms[b].add((t,'...'+str(len(matching))+'/'+str(n_genes)))
        #                                else: # check whether the distribution is normal around labeled genes
        #                                        A2, critical, sig = anderson(np.array(
        #                                                [min(r-genes[m] for m in matching) for r in genes.itervalues()]))
        #                                        # use a significance level of 0.01
        #                                        if A2 <= critical[-1]:
        #                                                n_terms += 1
        #                                                #significant_terms[b].add((t, '('+str(A2)+'/'+str(critical[2])+')'))
        #                        significant_terms[b] = ''#'('+str(n_terms)+'/'+str(len(terms))+')'

        ################################################################################

        self.update_progress("Building Trees...")

        # dot file
        DOT_FILE = open('%s.dot' % (output_prefix), "w")

        # graphml file
        GML_FILE = open('%s.graphml' % (output_prefix), "w")

        # json file
        JSON_FILE = open('%s.json' % output_prefix, 'w')

        # csv file
        CSV_FILE = open('%s.csv' % output_prefix, 'w')

        # output defaults for all nodes and edges
        if do_emphasis_check:
            default_color_dot = '#ccccff'
            default_color_gml = 'purple'
            default_color_json = 'purple'
        else:
            default_color_dot = '#ccffcc'
            default_color_gml = 'green'
            default_color_json = 'green'

        # dot defaults
        print("""
                digraph G {
                        rankdir=TB;
                        splines=true;
                        epsilon=.001; maxiter=1500;
                        node [shape=box, style=filled, color=black, fillcolor="%s", fontname="Helvetica, Arial, sans-serif", fontsize="10px"];
                        edge [color=black];
                        ranksep=2;
                """ % (default_color_dot,), file=DOT_FILE)

        # graphml defaults/definitions
        print("""
                <graphml>
                        <graph id="G" edgedefault="directed">
                                <key id="Nc" for="node" attr.name="color" attr.type="string">
                                        <default>%s</default>
                                </key>
                                <key id="Nl" for="node" attr.name="label" attr.type="string"/>
                                <key id="Nu" for="node" attr.name="URL" attr.type="string"/>
                                <key id="Ng" for="node" attr.name="genes" attr.type="string"/>
                                <key id="Nt" for="node" attr.name="tooltip" attr.type="string"/>
                                <key id="Nb" for="node" attr.name="borderColor" attr.type="string">
                                        <default>black</default>
                                </key>
                                <key id="Nx" for="node" attr.name="x" type="double"/>
                                <key id="Ny" for="node" attr.name="y" type="double"/>
                                <key id="Ec" for="edge" attr.name="color" attr.type="string">
                                        <default>black</default>
                                </key>
                                <key id="Eb" for="edge" attr.name="bootstrap" attr.type="float"/>
                """ % (default_color_gml,), file=GML_FILE)

        # JSON defaults? Idk
        # print >> JSON_FILE, """
        # {
        #     "nodes": [
        #         {"id": 0, "name": "flare", "children": [1], "depth": 0, "emphasis": true}
        #         {"id": 1, "name": "analytics", "children": [2, 7, 13], "depth": 1}
        #         {"id": 2, "name": "cluster", "children": [3, 4, 5, 6], "depth": 2}
        #         {"id": 3, "name": "AgglomerativeCluster", "children": [], "depth": 3}
        #     ]
        # }
        # """ % (default_color_json,)

        # output all nodes
        self.update_progress('Outputting Nodes...')

        # num_bicliques = len(bicliques)
        # counter = 1
        json_nodes = []

        # needed in order to match the species id to the name
        self.cur.execute("""
                select sp_id, sp_name from species order by sp_id
                """)
        species_dict = dict((Sid, Sname) for Sid, Sname in self.cur)

        level = 0
        # print "\n\nTRYING SOMETHING STUPID\n\n"
        # print "LEVEL = " + str(level)

        for size, bicliques_list in bicliques[::-1]:
            level += 1
            # print "SIZE = " + str(size)
            # print "LEVEL = " + str(level)
            # level = size-1
            # if counter == num_bicliques:
            print(' {rank=same;', file=DOT_FILE)
            # else
            # print >> DOT_FILE, ' {rank=min;'
            for b in bicliques_list:
                if not b.parents:
                    has_parents_dot = ', color=red'
                    has_parents_gml = '\n                                        <data key="Nb">red</data>\n'
                    has_parents_json = 'no'
                else:
                    has_parents_dot = ''
                    has_parents_gml = ''
                    has_parents_json = 'yes'

                if b.emphasize:
                    dot_emphasis = ''
                    gml_emphasis = ''
                    json_emphasis = 'no'
                else:
                    dot_emphasis = ', fillcolor="#ccffcc"'
                    gml_emphasis = '\n                                        <data key="Nc">green</data>\n'
                    json_emphasis = 'yes'

                # dot
                print("""
                                        Ph_node_%s [label="%s"%s, tooltip="%s", target="_parent", URL="%s"%s];
                                """ % (b.id, b.label, dot_emphasis, b.tooltip, b.url, has_parents_dot), file=DOT_FILE)

                # graphml
                print("""
                                        <node id="Ph_node_%s">
                                                <data key="Nl">%s</data>
                                                <data key="Nt">%s</data>
                                                <data key="Nu">%s</data>%s
                                                <data key="Ng">%s</data>%s
                                                <data key="Nx">_xy_</data>
                                                <data key="Ny">_xy_</data>
                                        </node>
                                """ % (b.id, b.label, b.tooltip, b.url, has_parents_gml,
                                       ','.join(str(g) for g in b.genes), gml_emphasis), file=GML_FILE)

                # list of children ids for the graph creation
                chld_ids = []
                for ch in b.children:
                    chld_ids.append(ch.id)

                # getting the species for the multicoloring
                gs_to_sp = dict()
                for gs in b.genesets:
                    gs_id_no_prefix = gs[2:]
                    self.cur.execute("""
                                    select gs_id, sp_id from geneset where gs_id = %s
                                    """ % gs_id_no_prefix)
                    temp = dict((Gid, species_dict[Sid]) for Gid, Sid in self.cur)
                    gs_to_sp.update(temp)

                gs_abbrevs = dict()
                for gs in b.genesets:
                    gs_id_no_prefix = gs[2:]
                    self.cur.execute("""
                                    select gs_id, gs_abbreviation from geneset where gs_id = %s
                                    """ % gs_id_no_prefix)
                    # temp = dict((Gid, species_dict[Sid]) for Gid, Sid in self.cur)
                    temp = dict((gid, gab) for gid, gab in self.cur)
                    gs_abbrevs.update(temp)

                # json_node = {str(b.id):{
                genes_string = list()
                for g in b.genes:
                    g = str(g)
                    genes_string.append(g[:len(g)])
                decremented_children = []
                for c in chld_ids:
                    decremented_children.append(c - 1)

                json_node = {
                    'id': b.id - 1,
                    # 'Genesets': ','.join(str(g) for g in b.genesets),
                    'Genesets': list(b.genesets),
                    'Abbreviations': list(gs_abbrevs.values()),
                    'species': list(gs_to_sp.values()),
                    'name': b.label,
                    'tooltip': b.tooltip,
                    'url': b.url,
                    # 'genes': ','.join(str(g) for g in b.genes),
                    'Genes': genes_string,
                    'emphasis': json_emphasis,
                    'children': decremented_children,
                    'depth': level - 1
                }

                json_nodes.append(json_node)
                # print json_node

            print('}', file=DOT_FILE)

            # counter++

        # output all edges
        self.update_progress('Outputting Edges...')

        json_links = []

        for size, bicliques_list in reversed(bicliques[1:]):
            if size <= cut_depth: break
            for b in bicliques_list:
                if not b.children or not b.displayed: continue
                for ch in b.children:
                    if ch.size <= cut_depth or not ch.displayed: continue

                    e = bstrap_edges[(b.id, ch.id)] if (b.id, ch.id) in bstrap_edges else 0

                    if e > 0:
                        dot_edge = ' [label="%s"', (e,)
                        gml_edge = '                        <data key="Eb">%s</data>\n' % (e,)
                        if e > 0.5:
                            dot_edge += ' color=blue'
                            gml_edge = '                        <data key="Ec">blue</data>\n'
                        dot_edge += '];'
                        gml_edge += '     </edge>'
                    else:
                        dot_edge = ''
                        gml_edge = '/>'

                    print("""
                                                Ph_node_%s->Ph_node_%s%s;
                                        """ % (b.id, ch.id, dot_edge), file=DOT_FILE)

                    print("""
                                                <edge id="e%s-%s" source="Ph_node_%s" target="Ph_node_%s"%s
                                        """ % (b.id, ch.id, b.id, ch.id, gml_edge), file=GML_FILE)

                    # json_link = {'source':b.id, 'target':ch.id}
                    # json_links.append(json_link)

        # close files
        print('}', file=DOT_FILE)
        DOT_FILE.close()

        print('        </graph>', file=GML_FILE)
        print('</graphml>', file=GML_FILE)
        GML_FILE.close()

        # json_graph = {'nodes': json_nodes, 'links': json_links}
        json_graph = {'nodes': json_nodes}
        # print str(JSON_FILE)
        # print json_graph
        print(json_graph, file=JSON_FILE)
        JSON_FILE.close()
        # print "RIGHT BEFORE CSV PRINTING BITCHEZZZZZZ"
        csv_data = csv_output_creation(json_graph)
        # print csv_data
        print(csv_data, file=CSV_FILE)
        CSV_FILE.close()

        self.update_progress("Graph Output Files Finished...")

        ################################################################################

        self.update_progress("Drawing Trees...")
        gvprog = "dot"

        os.system("%s %s.dot -Tsvg -o %s.svg" % (gvprog, output_prefix, output_prefix))
        os.system("%s %s.dot -Tpdf -o %s.pdf" % (gvprog, output_prefix, output_prefix))
        image_FPN = output_prefix

        proc = subprocess.Popen("%s %s.dot -Tcmap" % (gvprog, output_prefix),
                                shell=True, text=True, encoding="utf-8", stdout=subprocess.PIPE)

        self._results['result_image'] = "%s.graphml" % (image_FPN)
        self._results['result_map'] = proc.stdout.read()

        # post-process SVG file
        svgfn = "%s.svg" % (image_FPN)
        try:
            svgin = open("%s" % svgfn)
        except IOError:
            raise Exception(('There was a problem running GraphViz. Make sure '
                             'it is installed properly.'))
        svgout = open("%s.tmp" % svgfn, "w")
        ln = 0
        points = []  # for graphml, below; list of alternating x/y coordinate strings
        isNode = False
        for line in svgin:
            line = line.strip()
            # if ln==8:
            #   print >> svgout, '''<svg width="100%" height="100%"
            #                   zoomAndPan="disable" '''
            if line == "</svg>":
                print('<rect id="zoomhi" fill-opacity="0" width="1.0" height="1.0" />', file=svgout)
                print("</svg>", file=svgout)
            else:
                line = line.replace("font-size:10.00;", "font-size:10px;")

                # get x,y node coordinate data for graphml editing, below
                if line.startswith('<g id="node'):
                    isNode = True
                elif isNode:
                    index = line.find('points="')
                    if index > -1:
                        index += 8
                        points += line[index:line.find(' ', index)].split(',')
                        isNode = False

                print(line, file=svgout)

            if ln == 9:
                print('<script type="application/ecmascript" xlink:href="/ode_svg.js"></script>', file=svgout)

            ln += 1
        svgout.close()
        svgin.close()
        os.system("mv %s.tmp %s" % (svgfn, svgfn))

        # update graphml file with coordinate data
        GML_IN = open('%s.graphml' % (output_prefix), 'r')
        GML_OUT = open('%s.graphml.tmp' % (output_prefix), 'w')
        i = 0
        for line in GML_IN:
            line = line.strip()
            if i < len(points):
                index = line.find('_xy_')
                if index > -1:
                    line = line[:index] + points[i] + line[index + 4:]
                    i += 1
            print(line, file=GML_OUT)
        GML_IN.close()
        GML_OUT.close()
        os.system('mv %s.graphml.tmp %s.graphml' % (output_prefix, output_prefix))

        if num_permutations > 0:
            perms = {'N': num_permutations}

            self.update_progress("Permuting Trees...")
            args = ("%s/TOOLBOX/bicliquer/bicliquer" % (self.TOOL_DIR), '%s.odemat' % output_prefix,
                    "-n%s" % (num_permutations),
                    "-l%s" % (permutation_time_limit))

            # try:
            proc = subprocess.Popen(args, stdout=subprocess.PIPE, text=True, encoding="utf-8")

            # except OSError as e:
            #    ## Refers to an incompatible executable format. This
            #    ## tool should be recompiled for this architecture.
            #    if e.errno == errno.ENOEXEC:
            #        print e

            #    ## Corresponds to file not found
            #    if e.errno == errno.ENOENT:

            getscores = False
            cutoff_set = False
            fulltime = 0

            for line in proc.stdout:
                if line[:6] == 'score:':
                    getscores = True
                elif not getscores:
                    m = re.search(r'Time limit exceeded at n=(.*)$', line)
                    if m:
                        num_permutations = m.group(1).strip()
                        self.update_progress(
                            "  %s minute time limit exceeded. N=%s" % (permutation_time_limit, num_permutations))
                        self.update_progress("  Full results would need %s longer." % (fulltime))

                    m = re.search(r'([^ ]+) ETA: (.*)$', line)
                    if m:
                        if m.group(1) == 'cutoff':
                            cutoff_set = True
                            self.update_progress('  ETA: %s' % (m.group(2).strip()))

                        elif cutoff_set:
                            fulltime = m.group(2).strip()
                        else:
                            self.update_progress('  ETA: %s' % (m.group(2).strip()))

                elif line != '':
                    m = re.search("^([^:]*):\t(.*)\t(.*)\t(.*)$", line)
                    if m:
                        perms[m.group(1).strip()] = {}
                        perms[m.group(1).strip()]['value'] = m.group(2).strip()
                        perms[m.group(1).strip()]['pvalue_low'] = m.group(3).strip()
                        perms[m.group(1).strip()]['pvalue_high'] = m.group(4).strip()

            self._results['perms'] = perms

            testOut = open("testOut.txt", "w")
            print(self._results, file=testOut)
            print(self._parameters, file=testOut)
            testOut.close()


# outputs csv string where order is level, node,
# genesets, followed by a blank, and the genes
# NOTE: genesets string itself contains newline characters which might mess with the csv format. Might need to be changed.
def csv_output_creation(json_graph):
    csv_output = 'Level,Node,GeneSets,,Genes\n'
    json_graph_node = json_graph['nodes']

    ##needs some sorting here (radix?)

    for node in json_graph_node:
        # Note: str(node['name']) is the aspect causing the malformed csv file.
        # This code uses regex to remove commas and newlines in the "str(node['name'])" output to prevent malforming the csv file.
        # The first ".replace('; ', '')" removes a motif wherein number of publications has two semicolons and a space (this deforms the final file).
        # The trailing ".replace(';', '|')" method changes all semicolons to pipes for easier viewing.
        csv_output += str(node['depth']) + ',' + re.sub(r'[\n,]', '', str(node['name'])).replace('; ', '').replace(';', '|') + ','
        # print "1" + csv_output
        genesets = node['Genesets']
        # print "2" + csv_output
        # Note: bottom line commented out as it malforms the csv file by making GeneSets their own column.
        # As noted above, GeneSets should be in their own columns to preserve the 'GeneSet,Genes\n' motif.
        # csv_output += ','.join(str(gs) for gs in genesets)
        # This code uses the pipes to separate GeneSets for easier viewing and to avoid creating new columns for each GeneSet.
        csv_output += '|'.join(str(gs) for gs in genesets)
        # print "3" + csv_output
        # These additional commas keep the format "GeneSets follow by a blank and genes" as noted above.
        csv_output += ',,'
        # print "4" + csv_output
        genes = node['Genes']
        csv_output += ','.join(str(g) for g in genes)
        # print "5 " + csv_output
        csv_output += '\n'
    # print csv_output
    return csv_output


def NewTool(*args, **kwargs):
    return PhenomeMap(*args, **kwargs)


PhenomeMap = celery.register_task(PhenomeMap())

if __name__ == '__main__':
    PhenomeMap.mainexec()
