#!/usr/bin/python
# USAGE: GeneSetViewer.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt

import os

import tools.toolbase
from tools.celeryapp import celery


class GeneSetViewer(tools.toolbase.GeneWeaverToolBase):
    name = "tools.GeneSetViewer.GeneSetViewer"

    def __init__(self, *args, **kwargs):
        self.init("GeneSetViewer")
        self.urlroot = ''

    def mainexec(self):
        min_degree = self._parameters["GeneSetViewer_MinDegree"]
        suppress_disconnected = self._parameters["GeneSetViewer_SupressDisconnected"] == 'On'
        output_prefix = self._parameters["output_prefix"]  # {,_gs}{.dot,.png}
        self._results['gs_ids'] = self._gsids

        emph_gene_ids = []

        if 'EmphasisGenes' in self._parameters:
            emph_gene_ids = self._parameters['EmphasisGenes']

        genes = {}

        edges = {}
        used_gs = {}
        used_gs_real = {}
        used_genes = {}
        n_edges = 0
        max_deg = 0
        rank_sizes = [0]
        for r in self._matrix:
            gid = int(r[0])
            genes[gid] = r[1]
            deg = 0
            i = 0
            for e in r[2:]:
                if int(e):
                    if gid not in edges:
                        edges[gid] = {}
                    edges[gid][i] = 1
                    used_gs[i] = 1
                    if gid not in used_genes:
                        used_genes[gid] = {}
                    used_genes[gid][i] = 1
                    n_edges += 1
                    deg += 1
                i += 1

            while len(rank_sizes) <= deg:
                rank_sizes.append(0)
            rank_sizes[deg] += 1
            if deg > max_deg:
                max_deg = deg

        nphenos = len(used_gs)
        ngenes = len(used_genes)

        # search from high to low and find the first degree-rank
        # that has more than 25 genes and cut there
        if min_degree == 'Auto':
            dgenes = 0
            for rnk in range(max_deg, 1, -1):
                if rank_sizes[rnk] > 25 and dgenes > 4:
                    min_degree = rnk + 1
                else:
                    dgenes += rank_sizes[rnk]
            if min_degree == 'Auto':
                min_degree = 2

        min_degree = int(min_degree)

        fout = open(output_prefix + ".dot", "w")
        print("digraph G {", file=fout)
        print("  rankdir=LR;", file=fout)
        print("  splines=true;", file=fout)
        print("  epsilon=.001; maxiter=1500;", file=fout)
        print("  node [color=black, fontname=\"DejaVu Sans\", fontsize=10];", file=fout)
        # splines go around nodes cleanly, epsilon and maxiter ensure it runs fast
        fout2 = open(output_prefix + "_gs.dot", "w")
        print("digraph G {", file=fout2)
        print("  rankdir=RL;", file=fout2)
        print("  ranksep=3; ", file=fout2)

        # output nodes
        maxr = 0
        ranklist = {}
        for (gene, gslist) in used_genes.items():
            gslist2 = gslist.keys()
            cnt = len(gslist2)
            if cnt < min_degree:
                continue
            for gs in gslist2:
                used_gs_real[gs] = 1

            if gene < 0:
                g2 = "H%d" % -gene
            else:
                g2 = "%d" % gene

            # this is link to create a search for the gene within other genesets -> this will change.
            ## & symbols must be escaped (&amp;) or an XML parsing error will 
            ## be thrown when the SVG is rendered on the results page
            gene_search_url = \
                '/search/?searchbar=%s&amp;pagination_page=1&amp;searchGenes=yes' % \
                genes[gene]

            if str(gene) in emph_gene_ids:
                # print >>fout, 'Gene_%s [color=yellow, shape=ellipse, label="%s", target="_parent", URL="/index.php?action=search&searchwhat=2&q=%s"];' % (g2, genes[gene], genes[gene])
                print('Gene_%s [color=yellow, shape=ellipse, label="%s", target="_blank", URL="%s"];' % (
                    g2, genes[gene], gene_search_url), file=fout)
            else:
                # print >>fout, 'Gene_%s [color=green, shape=ellipse, label="%s", target="_parent", URL="/index.php?action=search&searchwhat=2&q=%s"];' % (g2, genes[gene], genes[gene])
                print('Gene_%s [color=green, shape=ellipse, label="%s", target="_blank", URL="%s"];' % (
                    g2, genes[gene], gene_search_url), file=fout)

            if cnt not in ranklist:
                ranklist[cnt] = {}
            ranklist[cnt][g2] = 1
            if cnt > maxr:
                maxr = cnt

        if suppress_disconnected:
            used_gs = used_gs_real

        print("{ rank=same;\n  node [shape=box, style=filled, fontsize=10];", file=fout)
        print(" node [shape=box, style=filled, fixedsize, width=0.2, height=0.2];", fout2)
        print(" edge [color=white, fontname=Courier, fontsize=10, labelangle=0, labeldistance=10.0, arrowtype=none];",
              fout2)

        colors = {}
        for (geneset, cnt) in used_gs.items():
            # TODO: Where does this `i` come from? Do we need to set it to zero?
            c = 1 + i % 10
            i += 1
            geneset_url = '/viewgenesetdetails/%s' % (self._gsids[geneset][2:])
            print('GeneSet_%s [fillcolor="/paired10/%d", label="%s", tooltip="%s", target="_blank", URL="%s"];' % (
                geneset, c, self._gsnames[geneset], self._gsdescriptions[geneset], geneset_url), file=fout)
            print('GeneSet_%s [color="/paired10/%d", label="", tooltip="%s", target="_blank", URL="%s"];' % (
                geneset, c, self._gsdescriptions[geneset], geneset_url), fout2)
            print('X%s [style=invis];' % (geneset), fout2)
            print('X%s -> GeneSet_%s:e [headlabel="%-32s", headtooltop="%s", headURL="%s"];' % (
                geneset, geneset, self._gsnames[geneset], self._gsdescriptions[geneset], geneset_url), fout2)
            colors[geneset] = c

        print("  r0 [style=invis];\n}", file=fout)
        print("}", fout2)
        fout2.close()

        hidden = 'r1 -> r2 -> r0'
        for i in range(3, maxr + 1):
            hidden += " -> r%d" % i
        print(" { node[style=invis]; edge [style=invis]; %s; }" % hidden, file=fout)

        for lvl in range(min_degree, maxr + 1):
            r = 'same'
            if lvl == min_degree:
                r = 'min'
            if lvl in ranklist and len(ranklist[lvl]) > 0:
                print(" { rank=%s; r%d; Gene_%s; }" % (r, lvl, "; Gene_".join(ranklist[lvl].keys())), file=fout)

        maxd = 0
        mind = len(used_gs)
        avgd = 0
        # output edges
        for (gene, gsArray) in edges.items():
            n = len(gsArray)
            if n < mind:
                mind = n
            if n > maxd:
                maxd = n
            avgd += n

            if len(used_genes[gene]) < min_degree:
                continue

            if gene < 0:
                g2 = "H%d" % -gene
            else:
                g2 = "%d" % gene
            for (geneset, value) in gsArray.items():
                print('GeneSet_%s->Gene_%s [color="/paired10/%d"];' % (geneset, g2, colors[geneset]), file=fout)

        # TODO: This will raise DivisionByZero exception
        avgd /= len(edges);

        print("}", file=fout)
        fout.close()

        self.update_progress("Drawing Graph...")

        gvprog = 'dot'
        gvprog = "%s/TOOLBOX/dot_wrapper.sh" % (self.TOOL_DIR,)

        os.system("%s %s.dot -Tpdf -o %s.pdf" % (gvprog, output_prefix, output_prefix));
        os.system("%s %s.dot -Tsvg -o %s.svg" % (gvprog, output_prefix, output_prefix));
        self._results['result_image'] = "%s.svg" % (output_prefix)

        self._results['stats'] = {'mind': mind, 'maxd': maxd, 'avgd': avgd, 'threshold': min_degree}

        # post-process SVG file
        svgfn = self._results['result_image']
        try:
            svgin = open("%s" % svgfn)
        except IOError:
            raise Exception('GraphViz choked')
        svgout = open("%s.tmp" % svgfn, "w")
        ln = 0
        for line in svgin:
            line = line.strip()
            if ln == 6:
                # print >> svgout, '''<svg width="100%" height="100%" zoomAndPan="disable"'''
                print('''<svg width="100%" height="100%" ''', file=svgout)
            elif line == "</svg>":
                print('<rect id="zoomhi" fill-opacity="0" width="1.0" height="1.0" />', file=svgout)
                print("</svg>", file=svgout)
            else:
                line = line.replace("font-size:10.00;", "font-size:10px;")
                print(line, file=svgout)

            if ln == 9:
                print('<script type="application/ecmascript" xlink:href="/static/js/ode_svg.js"></script>', file=svgout)

            ln += 1
        svgout.close()
        svgin.close()
        os.system("mv %s.tmp %s" % (svgfn, svgfn))


GeneSetViewer = celery.register_task(GeneSetViewer())
