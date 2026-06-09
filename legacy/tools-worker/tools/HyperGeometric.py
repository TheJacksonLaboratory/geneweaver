#!/usr/bin/python
# USAGE: HyperGeometric_SVG.py input.odemat input.odepwd < parameters_json.txt > output_json.txt 2>status.txt

import sys
import re
import math

import tools.toolbase


class HyperGeometric(tools.toolbase.GeneWeaverToolBase):
    def __init__(self, *args, **kwargs):
        self.init("HyperGeometric")
        self.urlroot = ''
        self._comb_cache = {}

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
    def combtl(self, n, r):
        if r == 0:
            return 1
        key = "%d,%d" % (n, r)
        if key in self._comb_cache:
            return self._comb_cache[key]

        if sys.version_info[0] < 3:
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
        else:
            r = min(r, n - r)
            i = n - r + 1
            j = 1
            cnr = 1
            while i <= n or j <= r:
                if i <= n:
                    cnr *= i
                    i += 1
                if j <= r:
                    cnr /= j
                    j += 1

        self._comb_cache[key] = cnr
        return cnr

    def fisher(self, f00, f01, f10, f11):
        f00 = float(f00)
        f01 = float(f01)
        f10 = float(f10)
        f11 = float(f11)
        ret = {'or': (f00 * f11)}
        if f01 != 0 and f10 != 0:
            ret['or'] /= (f01 * f10)
        else:
            ret['or'] = 'Inf'

        f0 = f00 + f01
        f1 = f10 + f11
        g0 = f00 + f10
        g1 = f01 + f11
        ft = f00 + f01 + f10 + f11

        C = self.combtl(ft, f0)
        prob = (self.combtl(g0, f00) * self.combtl(g1, f01)) / C
        pval = prob
        for i in ('ut', 'lt', 'tt'):
            a_max = min(f0, g0)
            a_start = 0
            a_end = a_max
            if i == 'lt':
                a_end = f00 - 1
            elif i == 'ut':
                a_start = f00 + 1

            for a in range(int(a_start), int(a_end) + 1):
                if a == f00:
                    continue
                b = f0 - a
                c = g0 - a
                d = g1 - b
                if d < 0:
                    continue
                p = (self.combtl(a + c, a) * self.combtl(b + d, b)) / C
                if p < prob:
                    pval += p
            if pval > 1:
                pval = 1.0
            ret[i] = pval
        return ret

    #####################################
    def venn_circles(self, i, ii, j, size=100.0):
        pi = math.acos(-1.0)
        r1 = math.sqrt(i / pi)
        r2 = math.sqrt(ii / pi)
        if r1 == 0:
            r1 = 1.0
        if r2 == 0:
            r2 = 1.0
        scale = size / 2.0 / (r1 + r2)

        if i == j or ii == j:  # complete overlap
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
                Sj = r1_2 * alpha + r2_2 * (pi - beta) - 0.5 * r1_2 * math.sin(2 * alpha) + 0.5 * r2_2 * math.sin(
                    2 * beta)
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
        include_homology = self._parameters['HyperGeometric_Homology'] == 'Included'
        num_edges = 0
        emphasize_set = {}
        do_emphasis_check = 0
        try:
            emphasis_genes = self._parameters['emphasis_genes']
            for i in range(0, len(emphasis_genes)):
                emphasis_genes[i] = int(emphasis_genes[i]);
            for r in self._matrix:
                if int(r[0]) in emphasis_genes or -int(r[0]) in emphasis_genes:
                    i = 0
                    for e in r[2:]:
                        if int(e):
                            emphasize_set[i] = 1
                        i += 1
            do_emphasis_check = len(emphasis_genes) > 0
        except:
            pass

        leftpad = 300
        rightpad = 150
        toppad = 225
        vsize = 75.0

        width = self._num_genesets * 120
        height = self._num_genesets * 160
        width += leftpad + rightpad
        height += toppad

        laborder = ['or', 'ut', 'lt', 'tt', 'hg']
        legend = ["or: odds ratio", "ut: upper tail p-value", "lt: lower tail p-value", "tt: two-tailed p-value",
                  "hg: one-tail hypergeometric"]
        tx = leftpad / 4
        ty = toppad - 18 * len(legend)
        legend_text = [{'tx': tx - 18, 'ty': ty - 18, 'style': 'font-weight:bold;', 'text': 'Legend:'}]
        for leg in legend:
            legend_text.append({'tx': tx, 'ty': ty, 'text': leg})
            ty += 18

        self.update_progress("Computing Fisher's Exact scores...")
        geneset_table = []
        geneset_labels = []
        venn_diagrams = []
        for i in range(0, self._num_genesets):
            trow = {}
            lrow = {}
            trow['url'] = "index.php?action=manage&cmd=viewGeneSet&gsID=%s" % (self._gsids[i][2:])
            trow['text'] = "%s: %s" % (self._gsids[i], self._gsnames[i])
            lrow['url'] = trow['url']
            lrow['text'] = trow['text']
            trow['gsID'] = self._gsids[i]
            trow['entries'] = []
            lrow['txA'] = i * 120 + 60 + leftpad
            lrow['tyA'] = toppad
            lrow['txB'] = leftpad
            lrow['tyB'] = i * 160 + 60 + toppad

            ty = lrow['tyB'] - 47.5
            for j in range(0, self._num_genesets):
                self.update_progress('',
                                     ((i * self._num_genesets) + j) * 100 / (self._num_genesets * self._num_genesets))
                venn = {'text': []}
                dcounts = self._pairwisedeletion_matrix[i][j]
                hyp = self.fisher(int(dcounts['00']), int(dcounts['01']), int(dcounts['10']), int(dcounts['11']))
                if hyp['or'] == 'Inf' or hyp['or'] > 1.0:
                    del (hyp['lt'])
                    hyp['hg'] = 1.0 - hyp['ut']
                else:
                    del (hyp['ut'])
                    hyp['hg'] = 1.0 - hyp['lt']
                hyph = {}
                for (t, v) in hyp.items():
                    if v != 'Inf':
                        hyph[t] = re.sub(r'0+$', '0', "%4.4f" % (v))
                    else:
                        hyph[t] = 'Inf'

                if i != j:
                    venn['url'] = '?action=analyze&amp;cmd=intersection&amp;gsids=%s,%s&amp;refpop=%s,%s,%s' % (
                    self._gsids[i][2:], self._gsids[j][2:], dcounts['10'], dcounts['01'], dcounts['11'])
                    if include_homology:
                        venn['url'] += "&amp;homology=Included"
                else:
                    venn['url'] = '?action=manage&amp;cmd=viewGeneSet&amp;gsID=%s' % (self._gsids[i][2:])

                venn['tx'] = j * 120 + 12.5 + leftpad
                venn['ty'] = ty
                venn['opacity'] = 0.30
                if not do_emphasis_check or i in emphasize_set:
                    venn['opacity'] += 0.25
                if not do_emphasis_check or j in emphasize_set:
                    venn['opacity'] += 0.25
                if venn['opacity'] == 0.80:
                    venn['opacity'] = 1.0
                venn['title1'] = "%s (red) vs %s (blue)" % (self._gsnames[i], self._gsnames[j]);
                venn['desc1'] = "%s genes in common, %s genes only in red, %s genes only in blue" % (
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

                ty2 = 120
                for t in laborder:
                    if t not in hyph:
                        continue
                    venn['text'].append({'tx': 50, 'ty': ty2, 'text': "%s: %s" % (t, hyph[t])})
                    ty2 += 18

                te = {}
                if i == j:
                    te['background'] = 'background-color: #C7D0C7;'
                elif j % 2 == 0:
                    te['background'] = 'background-color: #FFFFFF;'
                else:
                    te['background'] = 'background-color: #E7F0E7;'

                score = hyp['tt']
                heat = '#666666'
                if score <= 0.05:
                    heat = '#FF0000'
                elif score <= 0.10:
                    heat = '#FF3333'
                elif score <= 0.25:
                    heat = '#33337F'

                te['url'] = venn['url']
                te['text'] = ''

                for t in laborder:
                    if t not in hyph:
                        continue

                    if t == 'ut' or t == 'lt':
                        cl = "hyperval hyper_st"
                    else:
                        cl = "hyperval hyper_%s" % (t)

                    te['text'] += '<div class="%s"><b style="color: %s;">%s: %s</b></div>' % (cl, heat, t, hyph[t])

                trow['entries'].append(te)
                venn_diagrams.append(venn)

            geneset_table.append(trow)
            geneset_labels.append(lrow)

        self._results['geneset_table'] = geneset_table
        self._results['geneset_labels'] = geneset_labels
        self._results['venn_diagrams'] = venn_diagrams

        self._results['geneset_labels'] = geneset_labels
        self._results['geneset_labels'] = geneset_labels

        self._results['width'] = width
        self._results['height'] = height
