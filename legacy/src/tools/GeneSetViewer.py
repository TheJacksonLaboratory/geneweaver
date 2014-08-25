#!/usr/bin/python
# USAGE: GeneSetViewer.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt

import os
import subprocess

import toolbase

class GeneSetViewer(toolbase.GeneWeaverToolBase):
    def __init__(self, *args, **kwargs):
        self.init("GeneSetViewer")
        self.urlroot=''

    def mainexec(self):
        minDegree = self._parameters["GeneSetViewer_MinDegree"]
        suppressDisconnected = self._parameters["GeneSetViewer_SupressDisconnected"]=='On'
        output_prefix = self._parameters["output_prefix"]   # {,_gs}{.dot,.png}

        genes = {}

        edges={}
        usedGS={}
        usedGSreal={}
        usedGenes={}
        nedges=0
        maxdeg=0
        ranksizes = [0]
        for r in self._matrix:
            gid=int(r[0])
            genes[ gid ] = r[1]
            deg=0
            i=0
            for e in r[2:]:
                if int(e):
                    if gid not in edges:
                        edges[ gid ]={}
                    edges[ gid ][ i ]=1
                    usedGS[ i ]=1
                    if gid not in usedGenes:
                        usedGenes[ gid ]={}
                    usedGenes[ gid ][ i ]=1
                    nedges+=1
                    deg+=1
                i+=1

            while len(ranksizes)<=deg:
                ranksizes.append(0)
            ranksizes[deg]+=1
            if deg>maxdeg:
                maxdeg=deg

        nphenos=len(usedGS)
        ngenes=len(usedGenes)

        # search from high to low and find the first degree-rank
        # that has more than 25 genes and cut there
        if minDegree=='Auto':
            dgenes=0
            for rnk in range(maxdeg, 1, -1):
                if ranksizes[rnk]>25 and dgenes>4:
                    minDegree=rnk+1
                else:
                    dgenes+=ranksizes[rnk]
            if minDegree=='Auto':
                minDegree=2

        minDegree=int(minDegree)

        fout = open(output_prefix+".dot", "w")
        fout2 = open(output_prefix+"_gs.dot", "w")
        print >> fout, "digraph G {"
        print >> fout2, "digraph G {"
        # splines go around nodes cleanly, epsilon and maxiter ensure it runs fast
        print >> fout, "  rankdir=LR;"
        print >> fout, "  splines=true;"
        print >> fout, "  epsilon=.001; maxiter=1500;"
        print >> fout, "  node [color=black, fontname=\"DejaVu Sans\", fontsize=10];"
        print >> fout2, "  rankdir=RL;"
        print >> fout2, "  ranksep=3; "

        # output nodes
        maxr=0
        ranklist={}
        for (gene,gslist) in usedGenes.items():
            gslist2 = gslist.keys()
            cnt = len(gslist2)
            if cnt<minDegree:
                continue
            for gs in gslist2:
                usedGSreal[gs]=1

            if gene<0:
                g2="H%d" % -gene
            else:
                g2="%d" % gene
            print >>fout, 'Gene_%s [color=green, shape=ellipse, label="%s", target="_parent", URL="/index.php?action=search&searchwhat=2&q=%s"];' % (g2, genes[gene], genes[gene])
            if cnt not in ranklist:
                ranklist[cnt]={}
            ranklist[cnt][g2]=1
            if cnt>maxr:
                maxr=cnt

        if suppressDisconnected:
            usedGS=usedGSreal

        print >> fout, "{ rank=same;\n  node [shape=box, style=filled, fontsize=10];"
        print >> fout2, " node [shape=box, style=filled, fixedsize, width=0.2, height=0.2];"
        print >> fout2, " edge [color=white, fontname=Courier, fontsize=10, labelangle=0, labeldistance=10.0, arrowtype=none];"

        colors={}
        for (geneset,cnt) in usedGS.items():
            c=1 + i%10
            i+=1
            geneset_url='/index.php?action=manage&cmd=viewgeneset&gs_id=%s' % (self._gsids[geneset][2:])
            print >> fout, 'GeneSet_%s [fillcolor="/paired10/%d", label="%s", tooltip="%s", target="_parent", URL="%s"];' % (geneset, c, self._gsnames[geneset], self._gsdescriptions[geneset], geneset_url)
            print >> fout2, 'GeneSet_%s [color="/paired10/%d", label="", tooltip="%s", target="_parent", URL="%s"];' % (geneset, c, self._gsdescriptions[geneset], geneset_url)
            print >> fout2, 'X%s [style=invis];' % (geneset)
            print >> fout2, 'X%s -> GeneSet_%s:e [headlabel="%-32s", headtooltop="%s", headURL="%s"];' % (geneset, geneset, self._gsnames[geneset], self._gsdescriptions[geneset], geneset_url)
            colors[geneset]=c

        print >> fout, "  r0 [style=invis];\n}"
        print >> fout2, "}"
        fout2.close()

        hidden='r1 -> r2 -> r0'
        for i in range(3,maxr+1):
            hidden+=" -> r%d" % (i)
        print >> fout, " { node[style=invis]; edge [style=invis]; %s; }" % (hidden)

        for lvl in range(minDegree, maxr+1):
            r='same'
            if lvl==minDegree:
                r='min'
            if lvl in ranklist and len(ranklist[lvl])>0:
                print >> fout, " { rank=%s; r%d; Gene_%s; }" % (r,lvl, "; Gene_".join(ranklist[lvl].keys()))

        maxd=0
        mind=len(usedGS)
        avgd=0
        # output edges
        for (gene,gsArray) in edges.items():
            n=len(gsArray)
            if n<mind:
                mind=n
            if n>maxd:
                maxd=n
            avgd+=n

            if len(usedGenes[gene])<minDegree:
                continue

            if gene<0:
                g2="H%d" % -gene
            else:
                g2="%d" % gene
            for (geneset,value) in gsArray.items():
                print >> fout, 'GeneSet_%s->Gene_%s [color="/paired10/%d"];' % (geneset,g2,colors[geneset])

        avgd/=len(edges);

        print >> fout, "}"
        fout.close()

        self.update_progress("Drawing Graph...")

        gvprog='dot'
        gvprog="%s/TOOLBOX/dot_wrapper.sh" % (self.TOOL_DIR,)

        os.system("%s %s.dot -Tpdf -o %s.pdf" % (gvprog, output_prefix, output_prefix) );
        os.system("%s %s.dot -Tsvg -o %s.svg" % (gvprog, output_prefix, output_prefix) );
        self._results['result_image']="%s.svg" % (output_prefix)

        self._results['stats'] = { 'mind': mind, 'maxd': maxd, 'avgd': avgd, 'threshold': minDegree }

        # post-process SVG file
        svgfn = self._results['result_image']
        try:
            svgin = open("%s" % svgfn)
        except IOError:
            raise Exception('GraphViz choked')
        svgout = open("%s.tmp" % svgfn,"w")
        ln=0
        for line in svgin:
            line=line.strip()
            if ln==8:
                print >> svgout, '''<svg width="100%" height="100%"
                        zoomAndPan="disable" '''
            elif line=="</svg>":
                print >> svgout, '<rect id="zoomhi" fill-opacity="0" width="1.0" height="1.0" />'
                print >> svgout, "</svg>";
            else:
                line=line.replace("font-size:10.00;", "font-size:10px;")
                print >> svgout, line

            if ln==9:
                print >> svgout, '<script type="application/ecmascript" xlink:href="/ode_svg.js"></script>'

            ln+=1
        svgout.close()
        svgin.close()
        os.system("mv %s.tmp %s" % (svgfn,svgfn))
