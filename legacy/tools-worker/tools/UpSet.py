#!/usr/bin/python
# USAGE: UpSet.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt
# TODO: Should be deprecated with python2
from __future__ import print_function

import json
import math

from pandas import DataFrame

import tools.toolbase
import tools.UpSetOriginal as uso


class UpSet(tools.toolbase.GeneWeaverToolBase):
    def __init__(self, *args, **kwargs):
        self.init("UpSet")
        self.urlroot=''

    def mainexec(self):
        output_prefix = self._parameters["output_prefix"]
        include_homology = self._parameters['UpSet_Homology'] == 'Included'
        include_zeros = self._parameters['UpSet_Zero-sizeIntersections'] == 'Included'

        ## gs_ids for re-running the tool from the results page
        self._results['gs_ids'] = self._gsids

        emphasize_set = {}
        do_emphasis_check = 0
        try:
            emphasis_genes = self._parameters['EmphasisGenes']
            for i in range(0,len(emphasis_genes)):
                emphasis_genes[i] = int(emphasis_genes[i])
            for r in self._matrix:
                if int(r[0]) in emphasis_genes or -int(r[0]) in emphasis_genes:
                    i=0
                    for e in r[2:]:
                        if int(e):
                            emphasize_set[i] = 1
                        i += 1
            do_emphasis_check = len(emphasis_genes) > 0
        except:
            pass

        num_edges=0

        leftpad  = 300
        rightpad = 150
        toppad   = 225
        vsize    = 75

        width=height=self._num_genesets*120
        width+=leftpad+rightpad
        height+=toppad

        geneset_table = []

        self.update_progress('Calculating intersection values...')

        gene_set_dict = {}
        gene_name_dict = {}
        set_diagrams = []
        set_sizes = {}
        gene_hom_id = {}
        genes_sets = {}

        for i in range(0, self._num_genesets):

            gene_name_dict[self._gsids[i]] = self._gsnames[i]
            gene_set_size = {}
            genes_in_set = []

            percent = 100 * (float((i * i) + 1) / pow(self._num_genesets, 2))

            self.update_progress(percent=percent)

            id_index = 1

            """
                Queries the DB for gene ids in each selected gene set
                If homologies are included, the genes are associated with a homology id if they have one,
                otherwise, the gene_id is used to assess intersection. Hom_id is negated to avoid potential
                overlap with gene_ids that are not homologous but happen to have the same gene-id as another
                relevant hom_id
            """
            if include_homology:
                self.cur.execute(
                    ''' SELECT DISTINCT hom_id, g.ode_gene_id as gene_id,
                          CASE WHEN hom_id is NULL THEN g.ode_gene_id ELSE hom_id*-1 END AS hom
                        FROM geneset_value g LEFT OUTER JOIN homology h
                        ON (g.ode_gene_id=h.ode_gene_id)
                        WHERE gs_id = %s;
                    ''', (self._gsids[i][2:],))
                id_index = 2
            else:
                self.cur.execute(
                ''' SELECT *
                    FROM geneset_value
                    WHERE gs_id = %s;
                ''', (self._gsids[i][2:],))

            result = self.cur.fetchall()

            if result is not None:
                # Keep a list of the genes in each set
                gene_list = [gene[id_index] for gene in result]
                for g in result:
                    # Create a map of all the gene_ids - gene_names and their frequencies
                    self.cur.execute(
                        ''' SELECT DISTINCT gi_name, gene_freq, sp_name
                            FROM gene_info g LEFT OUTER JOIN homology h
                            ON (g.ode_gene_id=h.ode_gene_id) JOIN species s
                            ON (g.sp_id=s.sp_id)
                            WHERE g.ode_gene_id =  %s;
                        ''', (g[1],))
                    r = self.cur.fetchall()
                    if r is not None:
                        for row in r:
                            genes_sets[g[1]] = row
                            genes_in_set.append(row[0])
                    # Populate a homology_id - gene_id map
                    if id_index == 2:
                        if g[0] is not None:
                            gene_hom_id[g[0]] = g[1]

                df = DataFrame.from_dict({'geneId': gene_list})
                gene_set_dict[self._gsids[i][2:]] = df
                gene_set_size['desc1'] = "%s genes in set" % len(gene_list)
                gene_set_size['name'] = self._gsnames[i]
                gene_set_size['set_id'] = self._gsids[i]
                gene_set_size['size'] = len(gene_list)
                gene_set_size['genes'] = genes_in_set
                set_sizes[self._gsids[i]] = len(gene_list)
                set_diagrams.append(gene_set_size)

        # Use original UpSet python code to generate results
        ordered_data_frames, ordered_df_names, ordered_included_sets, ordered_excluded_sets, ordered_intersect_size, \
            ordered_intersects_genes = uso.plot(gene_set_dict)

        dfses = []
        self._results['genesets'] = self._gsids
        count = 0

        ordered_intersects_list = ordered_intersect_size.tolist()

        # Create JSON for each set for intersection diagrams
        for s in ordered_included_sets:
            if ordered_intersect_size[count] > 0 or include_zeros:
                dfs = {}
                sets = ""
                emphasis = []
                sets_arr = []
                genes = []
                gene_ic = []
                set_ic = []
                size = 0

                # Track which gene sets are included in the intersection
                for inset in s:
                    sets_arr.append(inset)
                    if "" is sets:
                        sets = "%s" % gene_name_dict['GS%s' % inset]
                    else:
                        sets = "%s vs. %s" % (sets, gene_name_dict['GS%s' % inset])

                    if inset in emphasis_genes:
                        emphasis.append(inset)
                    size = size + set_sizes['GS%s' % inset]

                # Calculate the genes in each intersection and the Entropy of each,
                #  * Set Entropy is the sum of all individual gene entropies
                for gene_intersects in ordered_intersects_genes[count]:
                    if gene_intersects < 0:
                        gene_intersects = gene_hom_id[(gene_intersects*-1)]

                    gene_sp = [genes_sets[gene_intersects][0], genes_sets[gene_intersects][2]]

                    if genes_sets[gene_intersects][1] > 0:
                        entropy = genes_sets[gene_intersects][1] * -1 * math.log(genes_sets[gene_intersects][1], 2)
                        gene_sp.append(entropy)
                        set_ic.append(entropy)
                    else:
                        gene_sp.append(None)
                    genes.append(gene_sp)

                dfs['sets'] = sets_arr
                dfs['desc1'] = "%d genes in intersection" % ordered_intersect_size[count]
                dfs['name1'] = sets
                dfs['intersection'] = ordered_intersects_list[count]
                dfs['emphasis'] = emphasis
                dfs['len'] = len(s)
                dfs['genes'] = genes
                dfs['set_entropy'] = sum(set_ic)

                # If the intersection is between a pair of sets, calculate the Jaccard similarity score
                if len(sets_arr) == 2:
                    dfs['jaccard_score'] = ordered_intersect_size[count] * 1.0 / (size - ((len(s) - 1) * ordered_intersects_list[count]))

                dfses.append(dfs)
                count += 1

        self._results['set_diagrams'] = set_diagrams
        self._results['intersection_diagrams'] = dfses

        ## "Calculating set intersection values..." is done
        self.update_progress(percent=100)

    ###########################################################
    ############ Code to Write Files ##########################

        fout1 = open(output_prefix+".txt", "w")
        svg_out = open("%s.svg" % output_prefix, "w")

        # This generates a text file of the table
        tempstring = "0\t"
        tempstring2 = ""
        for item in geneset_table:
            tempstring += item['gsID'] + "\t"
        print(tempstring, file=fout1)
        for item in geneset_table:
            tempstring2 += item['gsID'] + "\t"
            for upset in item['simpleEntries']:
                tempstring2 += upset + "\t"
            tempstring2 += "\n"
        print(tempstring2, file=fout1)
        fout1.close()

        # This generates an svg file
        print('<svg width="%s" height="%s" viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" version="1.1"\nxmlns:xlink="http://www.w3.org/1999/xlink"\n>' % (height, width, width, height), file=svg_out)

        for data_frame in range(0, len(dfses)):
            print('<a xlink:href="%s" target="_top"><text gene_sets="%s" text-anchor="start">%s</text></a>' % (data_frame['url'],data_frame['name1'],data_frame['desc1']), file=svg_out)
            print('<a xlink:href="%s" target="_top">\n<g transform="translate(%s %s)" opacity="%s">\n<bar r="%s" fill="#ff0000" fill-opacity="1.0" stroke="#000000" stroke-width="1px" >' % (data_frame['url'],  data_frame['opacity'], data_frame['intersection']), file=svg_out)

         #   print('<title>%s</title><desc>%s</desc>\n</circle>' % (data_frame['name1'],  data_frame['desc1'])
        #    print('<circle cx="%s" cy="%s" r="%s" fill="#0000ff" fill-opacity="0.4" stroke="#000000" stroke-width="1px" >' % (
         #   data_frame['c2x'], venn_diagrams[gs]['c2y'], venn_diagrams[gs]['r2'])
          #  print('</circle>'

         #   for txt in range(0, len(bar_graph[gs]['text'])):
          #      print('<text x="%s" y="%s" text-anchor="middle" transform="scale(0.75)">%s</text>' % (bar_graph[gs]['text'][txt]['tx'], bar_graph[gs]['text'][txt]['ty'], venn_diagrams[gs]['text'][txt]['text'])

            print('</g></a>', file=svg_out)

        print('<g id="ToolTip" opacity="0.8" visibility="hidden" pointer-events="none">\n\t<rect id="tipbox" x="0" y="5" width="88" height="20" rx="2" ry="2" fill="white" stroke="black"/>\n\t<text id="tipText" x="5" y="20" font-family="Arial" font-size="12">\n\t\t<tspan id="tipTitle" x="5" font-weight="bold"><![CDATA[]]></tspan>\n\t\t<tspan id="tipDesc" x="5" dy="15" fill="blue"><![CDATA[]]></tspan>\n\t</text>\n</g>\n</svg>', file=svg_out)

        svg_out.close()
        fout1.close()

    # Converts svg file for download
    # os.system("cairosvg %s.svg -f png -o %s.png" % (output_prefix, output_prefix))
    # os.system("cairosvg %s.svg -f pdf -o %s.pdf" % (output_prefix, output_prefix))
