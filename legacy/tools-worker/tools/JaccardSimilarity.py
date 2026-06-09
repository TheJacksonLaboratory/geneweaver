#!/usr/bin/python
# USAGE: JaccardClustering.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt

import re
import math
import os
import subprocess
# import cairosvg
import psycopg2

import tools.toolbase
from tools.celeryapp import celery


class JaccardSimilarity(tools.toolbase.GeneWeaverToolBase):
    name = "tools.JaccardSimilarity.JaccardSimilarity"

    def __init__(self, *args, **kwargs):
        self.init("JaccardSimilarity")
        self.urlroot = ''

    #  width, height
    #
    # html:
    #   csv_url
    #   svg_url
    #   convert_url
    #   usage_message
    #   geneset_table[] = (gsID, url, text, entries)
    #      ...entries[] = (url?,text}
    #
    # venn:
    #   geneset_labels[] = (url,txA,tyA,txB,tyB,text)
    #   venn_diagrams[] = (url,tx,ty, c1x,c1y,r1,title1,desc1, c2x,c2y,r2,title2,desc2, text)
    #         ...text[] = (tx,ty,text)

    def factorial(self, n):
        if sys.version_info[0] < 3:
            # TODO: For python 2, will be deprecated.
            if n <= 1:
                return int(1)
            n = int(n)
            f = n
            while n > int(1):
                n -= int(1)
                f *= n
            return f
        else:
            # For python 3
            if n <= 1:
                return 1
            n = n
            f = n
            while n > 1:
                n -= 1
                f *= n
            return f

    #   A = number of samples in set A
    #   B = number of samples in set B
    #   C = number of samples in A x B (A intersect B)
    #   This is literally taken from the paper.
    #
    #   TODO: Rewrite gaussian distribution assumption to NULL distribution
    #   - Matt
    def jac_pvalue(self, A, B, C):
        if A == 0 and B == 0:
            return 1
        if A > B:
            tmp = A
            A = B
            B = tmp
        p_value = 0.0
        N = A + B + C
        J = float(C) / float(N)  # defined by paper: J = C/(A+B+C)
        # J="%.6f" % J

        if (self._parameters['JaccardSimilarity_Homology'] == "Included"):
            homology = True
        else:
            homology = False

        self.cur.execute(
            '''
            SELECT  * 
            FROM    extsrc.jaccard_distribution_results
            WHERE   set_size1 = %s AND 
                    set_size2 = %s AND 
                    homology = %s;
            ''', (A, B, homology))

        results = self.cur.fetchall()

        ## Jaccard frequencies for these two set sizes aren't present in
        ## the DB, so we generate them
        if not len(results):
            toolpath = os.path.join(
                self.TOOL_DIR,
                'TOOLBOX/distribution_generator/distribution_generator.o '
            )

            ## Arguments to the distribution generator are:
            ## Set 1 size, set 2 size, use homology, do prepopulation
            if homology:
                subprocess.Popen([
                    toolpath + str(A) + " " + str(B) + " True False"
                ], shell=True).wait()

            else:
                subprocess.Popen([
                    toolpath + str(A) + " " + str(B) + " False False"
                ], shell=True).wait()

            ## Now we can retrieve the frequencies and calculate p
            self.cur.execute(
                '''
                SELECT  * 
                FROM    extsrc.jaccard_distribution_results
                WHERE   set_size1 = %s AND 
                        set_size2 = %s AND 
                        homology = %s;
                ''', (A, B, homology))

            results = self.cur.fetchall()

        ## Something horrible happened...
        if not len(results):
            return 0
        else:

            ## The jaccard we calculated is our first observation.
            freq_total = 1
            eg_magnitude = 1

            ## We iterate through the results to tally up the frequency of
            ## jaccards that are greater than or equal in magnitude to our
            ## observation, then divide by all frequencies to generate a p.
            ## Same principle mentioned in distribution_generator.cpp
            for r in results:
                rj = r[3]
                rf = r[4]

                if rj >= J:
                    eg_magnitude += rf

                freq_total += rf

            p_value = float(eg_magnitude) / (freq_total)

        # if A==0 and B==0 and C!=0:
        #     return 1.0
        # if C==0:
        #     return 0.0
        # N=A+B+C
        # J=float(C)/float(N)                 # defined by paper: J = C/(A+B+C)
        # nfac=self.factorial(N)
        # pabc=math.pow(3.0,-N)
        # if pabc==0:
        #     return 0.0
        # sum=0.0

        # for c in range(0,int(C+1)):
        #     fc=self.factorial(c)
        #     for a in range(max(0,int(A-C)),int(A+C+1)):
        #         if c+a>N:
        #             break

        #         fa=self.factorial(a)
        #         for b in range(max(0,int(B-C)),int(B+C+1)):
        #             if a+b+c < N:
        #                 continue
        #             if a+b+c > N:
        #                 break
        #             if a+b+c == N:
        #                 fb=self.factorial(b)
        #                 fabc=fa*fb*fc
        #                 #print "%s / %s * %f = " % (nfac,fabc,pabc),
        #                 try:
        #                     p=float(nfac/fabc) * pabc
        #                 except OverflowError:
        #                     return 1.0
        #                 #print "%5d %5d %5d -- J=%f (p=%s)" % (a,b,c, float(c)/float(a+b+c), p)
        #                 sum+=p
        # print "Final =", p_value
        return p_value

    #####################################
    def venn_circles(self, i, ii, j, size=100):
        pi = math.acos(-1.0)
        r1 = math.sqrt(i / pi)
        r2 = math.sqrt(ii / pi)
        if r1 == 0:
            r1 = 1.0
        if r2 == 0:
            r2 = 1.0
        scale = size / 2.0 / (r1 + r2)

        if i == ii == j == 0:   # same gene
            c1x = c1y = c2x = c2y = size / 2.0
        elif (i == j or ii == j) and (ii != 0) and (i != 0):  # complete overlap
            print('overlap: ', i, j, ii)
            c1x = c1y = c2x = c2y = size / 2.0
        elif j == 0:  # no overlap
            c1x = c1y = r1 * scale
            c2x = c2y = size - (r2 * scale)
        else:
            # originally written by zuopan, rewritten a number of times
            step = .001
            beta = pi
            if r1 < r2:
                r2_ = r1
                r1_ = r2
            else:
                r1_ = r1
                r2_ = r2
            r2o1 = r2_ / r1_
            r1_2 = r1_ * r1_
            r2_2 = r2_ * r2_

            while beta > 0:
                beta -= step
                alpha = math.asin(math.sin(beta) / r1_ * r2_)
                Sj = r1_2 * alpha + r2_2 * (pi - beta) - 0.5 * (r1_2 * math.sin(2 * alpha) + r2_2 * math.sin(2 * beta));
                if Sj > j:
                    break

            oq = r1_ * math.cos(alpha) - r2_ * math.cos(beta)
            oq = (oq * scale) / 2.0

            c1x = (size / 2.0) - oq
            c2x = (size / 2.0) + oq
            c1y = c2y = size / 2.0

        r1 = r1 * scale
        r2 = r2 * scale

        return {'c1x': c1x, 'c1y': c1y, 'r1': r1, 'c2x': c2x, 'c2y': c2y, 'r2': r2}

    #####################################

    def mainexec(self):
        output_prefix = self._parameters["output_prefix"]
        include_homology = self._parameters['JaccardSimilarity_Homology'] == 'Included'
        pValue_threshold = self._parameters['JaccardSimilarity_p-Value']
        self._results['JaccardSimilarity_p_Value'] = pValue_threshold

        ## gs_ids for re-running the tool from the results page
        self._results['gs_ids'] = self._gsids

        # print "p-value threshold", pValue_threshold
        emphasize_set = {}
        do_emphasis_check = 0
        try:
            emphasis_genes = self._parameters['EmphasisGenes']
            for i in range(0, len(emphasis_genes)):
                emphasis_genes[i] = int(emphasis_genes[i])
            for r in self._matrix:
                if int(r[0]) in emphasis_genes or -int(r[0]) in emphasis_genes:
                    i = 0
                    for e in r[2:]:
                        if int(e):
                            emphasize_set[i] = 1
                        i += 1
            do_emphasis_check = len(emphasis_genes) > 0
        except:
            emphasis_genes = []
            pass

        num_edges = 0

        leftpad = 300
        rightpad = 150
        toppad = 225
        vsize = 75

        width = height = self._num_genesets * 120
        width += leftpad + rightpad
        height += toppad

        geneset_table = []
        geneset_labels = []
        venn_diagrams = []

        self.update_progress('Calculating jaccard values...')

        for i in range(0, self._num_genesets):
            percent = 100 * (float((i * i) + 1) / pow(self._num_genesets, 2))

            self.update_progress(percent=percent)

            trow = {}
            lrow = {}
            trow['url'] = "/viewgenesetdetails/%s" % (self._gsids[i][2:])
            trow['text'] = "%s: %s" % (self._gsids[i], self._gsnames[i])
            lrow['url'] = trow['url']
            lrow['text'] = trow['text']
            trow['gsID'] = self._gsids[i]
            trow['entries'] = []
            # trow['simpleEntries'] = []
            lrow['txA'] = i * 120 + 60 + leftpad
            lrow['tyA'] = toppad
            lrow['txB'] = leftpad
            lrow['tyB'] = i * 120 + 60 + toppad

            ty = lrow['tyB'] - 47.5
            for j in range(0, self._num_genesets):
                # percent = 100 * (float((i * i) + j) / pow(self._num_genesets, 2))

                self.update_progress(percent=percent)
                self.update_progress('Perfoming permutation test...', percent=percent)

                venn = {'text': []}
                dcounts = self._pairwisedeletion_matrix[i][j]
                if dcounts['11'] != 0:
                    jac = float(dcounts['11']) / (float(dcounts['10']) + float(dcounts['01']) + float(dcounts['11']))
                    pvalue = self.jac_pvalue(dcounts['10'], dcounts['01'], dcounts['11'])
                else:
                    jac = 0.0
                    pvalue = 10.0
                scoreh = re.sub(r'0+$', '0', "J = %4.4f" % (jac))
                pval = re.sub(r'0+$', '0', "p = %4.4g" % (pvalue))
                if pvalue <= 0.05:
                    scoreh += '*'
                if jac != 0.0 and pvalue >= 0.95:
                    scoreh += '**'

                if i != j:
                    venn['url'] = '0'
                    if include_homology:
                        venn['url'] = '1'
                else:
                    venn['url'] = '/viewgenesetdetails/%s' % (self._gsids[i][2:])

                self.cur.execute(
                    ''' SELECT * 
                        FROM geneset_value
                        WHERE gs_id = %s;
                    ''', (self._gsids[i][2:],)
                )

                result = self.cur.fetchall()
                if result != None:
                    geneList = [gene[1] for gene in result]

                venn['emphasis1'] = 'False'

                for em_gene in emphasis_genes:
                    if em_gene in geneList:
                        venn['emphasis1'] = 'True'

                self.cur.execute(
                    ''' SELECT * 
                        FROM geneset_value
                        WHERE gs_id = %s;
                    ''', (self._gsids[j][2:],)
                )

                result = self.cur.fetchall()
                if result != None:
                    geneList = [gene[1] for gene in result]
                venn['emphasis2'] = 'False'
                for em_gene in emphasis_genes:
                    if em_gene in geneList:
                        venn['emphasis2'] = 'True'

                self.update_progress(
                    'Constructing venn diagram...',
                    percent=percent
                )

                #################################################################
                # if i!=j:
                #     venn['url']='/viewgenesetdetails/%s' % (self._gsids[i][2:])
                # Kristen's change pending
                #################################################################

                #    venn['url']='/viewgenesetdetails/%s' % (self._gsids[i][2:])
                #     if include_homology:
                #         venn['url']='/viewgenesetdetails/%s' % (self._gsids[i][2:])
                # else:
                #     venn['url']='/viewgenesetdetails/%s' % (self._gsids[i][2:])

                venn['tx'] = j * 120 + 12.5 + leftpad
                venn['ty'] = ty
                venn['opacity'] = 0.40
                if not do_emphasis_check or i in emphasize_set:
                    venn['opacity'] += 0.25
                if not do_emphasis_check or j in emphasize_set:
                    venn['opacity'] += 0.25
                if venn['opacity'] == 0.90:
                    venn['opacity'] = 1.0
                venn['title1'] = "%s (orange) vs %s (blue)" % (self._gsnames[i], self._gsnames[j]);
                venn['desc1'] = "%s genes in common, %s genes only in orange, %s genes only in blue" % (
                dcounts['11'], dcounts['10'], dcounts['01'])

                x = int(dcounts['10'])
                y = int(dcounts['01'])
                z = int(dcounts['11'])
                cc = self.venn_circles(x + z, y + z, z, vsize)
                venn['c1x'] = cc['c1x']
                venn['c1y'] = cc['c1y']
                venn['c2x'] = cc['c2x']
                venn['c2y'] = cc['c2y']
                venn['r1'] = cc['r1']
                venn['r2'] = cc['r2']

                if z == 0:  # no intersection
                    venn['text'].append(
                        {'tx': (cc['c1x']) * (4.0 / 3.0), 'ty': (cc['c1y'] + cc['r1'] + 20) * (4.0 / 3.0),
                         'text': "(%d)" % (x)})
                    venn['text'].append(
                        {'tx': (cc['c2x']) * (4.0 / 3.0), 'ty': (cc['c2y'] - cc['r2'] - 10) * (4.0 / 3.0),
                         'text': "(%d)" % (y)})
                else:
                    m = "(%d)" % (z)
                    if x != 0:
                        m = "(%d %s" % (x, m)
                    if y != 0:
                        m = "%s %d)" % (m, y)

                    r2r1 = cc['r1']
                    if cc['r2'] > cc['r1']:
                        r2r1 = cc['r2']

                    venn['text'].append(
                        {'tx': (vsize / 2) * (4.0 / 3.0), 'ty': (vsize / 2 - (r2r1) - 5) * (4.0 / 3.0), 'text': m})
                    venn['text'].append({'tx': 50, 'ty': 100, 'text': scoreh});
                    venn['text'].append({'tx': 50, 'ty': 120, 'text': pval});

                te = {}
                # if i==j:
                #      te['background'] = 'background-color: #C7D0C7;'
                # elif j%2==0:
                #      te['background'] = 'background-color: #FFFFFF;'
                # else:
                #      te['background'] = 'background-color: #E7F0E7;'

                if jac == 0:
                    te['jval'] = scoreh
                else:
                    # heat='#666666'
                    # if jac >= 0.75:
                    #        heat='#FF0000'
                    # elif jac >= 0.50:
                    #        heat='#FF3333'
                    # elif jac >= 0.25:
                    #        heat='#33337F'

                    te['url'] = venn['url']
                    te['jval'] = scoreh
                    te['pval'] = pval
                    # te['text'] = '''%s\n
                    #                 %s''' % (scoreh, pval)

                newPValue = min(1.0 - pvalue, pvalue)
                trow['entries'].append(te)
                # trow['simpleEntries'].append(str(jac) + ':' + str(newPValue))
                # if float(pvalue) >= float(pValue_threshold):
                # print "Within pvalue if"
                venn_diagrams.append(venn)
                # else:
                #    venn = {'text': []}
                #    venn_diagrams.append(venn)

            geneset_table.append(trow)
            geneset_labels.append(lrow)

        self._results['geneset_table'] = geneset_table
        # self._results['geneset_labels']=geneset_labels
        self._results['venn_diagrams'] = venn_diagrams
        self._results['width'] = width
        self._results['height'] = height
        self._results['genesets'] = self._gsids
        self._results['p_value'] = pValue_threshold

        ## "Calculating jaccard values..." is done
        self.update_progress(percent=100)

        ###########################################################
        ############ Code to Write Files ##########################

        fout1 = open(output_prefix + ".txt", "w")
        svg_out = open("%s.svg" % output_prefix, "w")

        # This generates a text file of the table
        tempstring = "0\t"
        tempstring2 = ""
        for item in geneset_table:
            tempstring += item['gsID'] + "\t"
        print(tempstring, file=fout1)
        for item in geneset_table:
            tempstring2 += item['gsID'] + "\t"
            for jac in item['simpleEntries']:
                tempstring2 += jac + "\t"
            tempstring2 += "\n"
        print(tempstring2, file=fout1)
        fout1.close()

        # This generates an svg file
        print(
            '<svg width="%s" height="%s" viewBox="0 0 %s %s" xmlns="http://www.w3.org/2000/svg" version="1.1"\nxmlns:xlink="http://www.w3.org/1999/xlink"\n>' % (
            height, width, width, height), file=svg_out)

        for gs in range(0, len(geneset_labels)):
            print(
                '<a xlink:href="%s" target="_top"><text x="%s" y="%s" text-anchor="start" transform="rotate(-45 %s %s)">%s</text></a>' % (
                geneset_labels[gs]['url'], geneset_labels[gs]['txA'], geneset_labels[gs]['tyA'],
                geneset_labels[gs]['txA'], geneset_labels[gs]['tyA'], geneset_labels[gs]['text']), file=svg_out)
            print('<a xlink:href="%s" target="_top"><text x="%s" y="%s" text-anchor="end">%s</text></a>' % (
            geneset_labels[gs]['url'], geneset_labels[gs]['txB'], geneset_labels[gs]['tyB'],
            geneset_labels[gs]['text']), file=svg_out)

        for gs in range(0, len(venn_diagrams)):
            print(
                '<a xlink:href="%s" target="_top">\n<g transform="translate(%s %s)" opacity="%s">\n<circle cx="%s" cy="%s" r="%s" fill="#ff0000" fill-opacity="1.0" stroke="#000000" stroke-width="1px" >' % (
                venn_diagrams[gs]['url'], venn_diagrams[gs]['tx'], venn_diagrams[gs]['ty'],
                venn_diagrams[gs]['opacity'], venn_diagrams[gs]['c1x'], venn_diagrams[gs]['c1y'],
                venn_diagrams[gs]['r1']), file=svg_out)

            print('<title>%s</title><desc>%s</desc>\n</circle>' % (
            venn_diagrams[gs]['title1'], venn_diagrams[gs]['desc1']), file=svg_out)

            print(
                '<circle cx="%s" cy="%s" r="%s" fill="#0000ff" fill-opacity="0.4" stroke="#000000" stroke-width="1px" >' % (
                venn_diagrams[gs]['c2x'], venn_diagrams[gs]['c2y'], venn_diagrams[gs]['r2']), file=svg_out)
            print('</circle>', file=svg_out)

            for txt in range(0, len(venn_diagrams[gs]['text'])):
                print('<text x="%s" y="%s" text-anchor="middle" transform="scale(0.75)">%s</text>' % (
                venn_diagrams[gs]['text'][txt]['tx'], venn_diagrams[gs]['text'][txt]['ty'],
                venn_diagrams[gs]['text'][txt]['text']), file=svg_out)

            print('</g></a>', file=svg_out)

        print(
            '<g id="ToolTip" opacity="0.8" visibility="hidden" pointer-events="none">\n\t<rect id="tipbox" x="0" y="5" width="88" height="20" rx="2" ry="2" fill="white" stroke="black"/>\n\t<text id="tipText" x="5" y="20" font-family="Arial" font-size="12">\n\t\t<tspan id="tipTitle" x="5" font-weight="bold"><![CDATA[]]></tspan>\n\t\t<tspan id="tipDesc" x="5" dy="15" fill="blue"><![CDATA[]]></tspan>\n\t</text>\n</g>\n</svg>',
            file=svg_out)

        svg_out.close()
        fout1.close()

        # Converts svg file for download
        # os.system("cairosvg %s.svg -f png -o %s.png" % (output_prefix, output_prefix))
        # os.system("cairosvg %s.svg -f pdf -o %s.pdf" % (output_prefix, output_prefix))


JaccardSimilarity = celery.register_task(JaccardSimilarity())
