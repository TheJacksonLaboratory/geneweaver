#!/usr/bin/python
# USAGE: JaccardClustering.py input.odemat < parameters_json.txt > output_json.txt 2>status.txt

import os
import subprocess

import json

import tools.toolbase
from tools.celeryapp import celery


class Tree(object):
    def __init__(self):
        self.parent = None
        self.data = None
        self.jac = 0
        self.left = None
        self.right = None

    def flatten(self, treeList=[]):
        treeList.append(self.data)

        if self.left is not None:
            left_child = self.left.flatten(treeList)

        if self.right is not None:
            right_child = self.right.flatten(treeList)

        return treeList

    def to_json(self, level=0, gs_dict={}):
        hll, hlr = 0, 0

        name = str(self.data).replace('frozenset([', '{').replace('])', '}').replace('\'', '').replace('\"', '').replace('\\', '')
        json_tree = {"name": name, "level": level, "jaccard_index": self.jac}

        children = []

        if self.left is not None or self.right is not None:
            if self.left is not None:
                left_child = self.left.to_json(level=level+1, gs_dict=gs_dict)
                children.append(left_child)

            if self.right is not None:
                right_child = self.right.to_json(level=level+1, gs_dict=gs_dict)
                children.append(right_child)

            json_tree["type"] = "cluster"
            json_tree["children"] = children
            json_tree["size"] = 5


        elif gs_dict:
            id = name[2:]
            gene_symbols = gs_dict["gene_symbols"]
            gene_set_names = gs_dict["gene_set_names"]
            gene_set_abbreviations = gs_dict["gene_set_abbr"]
            species_info = gs_dict['species_info']

            max_gs = 0

            for sym_list in gene_symbols.values():
                if len(sym_list) > max_gs:
                    max_gs = len(sym_list)

            if id in gene_symbols:
                for sym in gene_symbols[id]:
                    children.append({"name": sym, "type": "gene", "size": 3})

                json_tree["name"] = gene_set_abbreviations[id]
                json_tree["id"] = id
                json_tree["info"] = name+': '+gene_set_names[id]
                json_tree["species"] = species_info[id]
                json_tree["type"] = "geneset"
                json_tree["children"] = children

                gs_size = (20/float(max_gs))*(len(gene_symbols[id]))+10

                json_tree["size"] = gs_size


        if hll != 0 or hlr != 0:
            if hll > hlr:
                level = hll
            else:
                level = hlr

        return json_tree


def to_jsonTree(lst=[], gs_dict={}, _file=None):
    json_tree = {}
    children = []

    for t in lst:
        children.append(t.to_json(gs_dict=gs_dict))

    if lst:
        json_tree = {"name": "root", "type": "root", "children": children}
    else:
        json_tree = {"name": "root", "type": "root"}

    if _file:
        print(json.dumps(json_tree), file=_file)

    return json_tree


def to_jsonMatrix(lst=[], info=[], _file=None):

    json_matrix = {}
    nodes = []
    links = []

    for i in range(0, len(lst)):
        nodes.append({"name" : info[i]})
        for j in range(0, len(lst)):
            links.append({"source" : i, "target" : j, "value" : lst[i][j]})

    json_matrix["nodes"] = nodes
    json_matrix["links"] = links

    if _file:
        print(json.dumps(json_matrix), file=_file)

    return json_matrix

def wards_cluster(self, jsc, matrix):
    # variable declaration
    genesets = list(self._gsids)
    treelist = []
    similaritymatrix = jsc
    geneids = []
    genesetspergene = []
    num_genesets = len(genesets)

    # sets up the genes and which genesets they are a part of
    for i in range(0, matrix.__len__()):
        geneids.append(matrix[i][0])
        genesetlist = []
        for j in range(2, matrix[i].__len__()):
            if matrix[i][j] == 1:
                genesetlist.append(genesets[j-2])
        genesetspergene.append(genesetlist)

    # sets up the structure of the matrix to hold true positives, false positives, and false negatives
    fundamentalnummatrix = []

    for i in range(0, num_genesets):
        fundamentalnummatrix.append([])
        for j in range(0, num_genesets):
            fundamentalnummatrix[i].append([])
            fundamentalnummatrix[i][j] = [0, 0, 0]

    # sets up the base nodes for the tree
    for y in range(0, num_genesets):
        temptree = Tree()
        temptree.data = genesets[y]
        treelist.append(temptree)

    # combines genesets until there are no more genesets that are similar in some way
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)

        # finding which two clusters are the most similar
        for i in range(0, num_genesets-1):
            for j in range(i+1, num_genesets):
                if similaritymatrix[i][j] != 1:
                    if similaritymatrix[i][j] < minval:
                        minval = similaritymatrix[i][j]
                        tocluster = (i, j)

        if minval == 1.1:
            done = True
        else:
            # creates a new node with the newly clustered genesets
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(0, treelist.__len__()):
                if genesets[tocluster[0]] == treelist[x].data:
                    child1 = treelist[x]
                    while child1.parent is not None:
                        child1 = child1.parent
                if genesets[tocluster[1]] == treelist[x].data:
                    child2 = treelist[x]
                    while child2.parent is not None:
                        child2 = child2.parent

            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1-minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree

            # combines two genesets together that we wanted to cluster to make a new geneset with all the genes
            # of the initial two genesets we decided to cluster
            for j in range(0, genesetspergene.__len__()):
                for x in genesetspergene[j]:
                    if x == genesets[tocluster[1]]:
                        if genesets[tocluster[0]] not in genesetspergene[j]:
                            genesetspergene[j].append(genesets[tocluster[0]])

            # removes the geneset that we don't need anymore since it is a part of another one
            genesets.remove(genesets[tocluster[1]])
            num_genesets -= 1

            # clears the part of the matrix that we will need to compute new values for
            for i in range(0, num_genesets):
                for j in range(0, num_genesets):
                    fundamentalnummatrix[i][j][0] = 0
                    fundamentalnummatrix[i][j][1] = 0
                    fundamentalnummatrix[i][j][2] = 0

            # recalculates all of the true positives, false positives, and false negatives
            # between all the old genesets and the new clustered one
            for i in range(0, num_genesets-1):
                geneset1 = genesets[i]

                for k in range(0, geneids.__len__()):
                    genesetlist = genesetspergene[k]

                    for j in range(i + 1, num_genesets):
                        geneset2 = genesets[j]

                        # counting
                        if geneset1 not in genesetlist:
                            if geneset2 in genesetlist:
                                # A is missing, B is set
                                fundamentalnummatrix[i][j][1] += 1
                        else:
                            if geneset2 not in genesetlist:
                                # A is set, B is missing
                                fundamentalnummatrix[i][j][2] += 1
                            else:
                                # both are set
                                fundamentalnummatrix[i][j][0] += 1
                    # if we know the values for cluster a compared to b then we also know b compared to a
                    for j in range(i+1, num_genesets):
                        fundamentalnummatrix[j][i][1] = fundamentalnummatrix[i][j][2]
                        fundamentalnummatrix[j][i][2] = fundamentalnummatrix[i][j][1]
                        fundamentalnummatrix[j][i][0] = fundamentalnummatrix[i][j][0]

            # clears the similarity matrix so we can put in new similarity values
            similaritymatrix = []
            for i in range(0, num_genesets):
                similaritymatrix.append([])
                # 1b. Traverse all columns
                for j in range(0, num_genesets):
                    # 1c. Union pairwise deletion and calculate similarity
                    union = fundamentalnummatrix[i][j][0] + fundamentalnummatrix[i][j][1] +\
                            fundamentalnummatrix[i][j][2]
                    if union == 0:
                        similarity = 0
                    else:
                        similarity = float(fundamentalnummatrix[i][j][0])/float(union)

                    # 1d. Calculate and append dissimilarity for matrix
                    similaritymatrix[i].append(1.0-similarity)

    # creates a new list and appends all the different tree roots we have so we can display the trees
    roots = []

    for n in treelist:
        if n.parent is None:
            roots.append(n)

    return roots


def complete_cluster(self, jsc):
    # variable declaration
    genesets = list(self._gsids)
    gsInCluster = []
    treelist = []
    similaritymatrix = jsc
    num_clusters = len(genesets)

    # creates the initial clusters of genesets
    for x in range(0, len(self._gsids)):
        gsInCluster.append([])
        gsInCluster[x].append(x)

    # creates the base nodes of the tree
    for y in range(0, num_clusters):
        temptree = Tree()
        temptree.data = genesets[y]
        treelist.append(temptree)

    # clusters two clusters together by comparing all the genesets in one cluster to all the genesets in another
    # and finding which two clusters have the lowest maximum value between each others genesets
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)

        # finding which two clusters have the shortest longest distance between two genesets
        for i in range(0, num_clusters-1):
            for j in range(i+1, num_clusters):
                maxval = -1
                for k in range(0, len(gsInCluster[i])):
                    for l in range(0, len(gsInCluster[j])):
                        if similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]] > maxval:
                            maxval = similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]]
                if maxval != 1:
                    if maxval < minval:
                        minval = maxval
                        tocluster = (i, j)

        if minval == 1.1:
            done = True
        else:
            # creates a new node which is the combination of the two clusters we decided previously
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(0, treelist.__len__()):
                for y in range(0, len(gsInCluster[tocluster[0]])):
                    if genesets[gsInCluster[tocluster[0]][y]] == treelist[x].data:
                        child1 = treelist[x]
                        while child1.parent is not None:
                            child1 = child1.parent
                for y in range(0, len(gsInCluster[tocluster[1]])):
                    if genesets[gsInCluster[tocluster[1]][y]] == treelist[x].data:
                        child2 = treelist[x]
                        while child2.parent is not None:
                            child2 = child2.parent
            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1-minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree

            # adds all the genesets in one cluster to the other one we decided to cluster it with
            for i in range(0, len(gsInCluster[tocluster[1]])):
                gsInCluster[tocluster[0]].append(gsInCluster[tocluster[1]][i])
            # removes the old cluster that we don't need anymore
            gsInCluster.remove(gsInCluster[tocluster[1]])
            num_clusters -= 1

    # creates a list of all the different root nodes that we ended up with
    roots = []

    for n in treelist:
        if n.parent is None:
            roots.append(n)

    return roots


def average_cluster(self, jsc):
    # variable declaration
    genesets = list(self._gsids)
    gsInCluster = []
    treelist = []
    similaritymatrix = jsc
    num_clusters = len(genesets)

    # sets up the initial clusters with one geneset each
    for x in range(0, len(self._gsids)):
        gsInCluster.append([])
        gsInCluster[x].append(x)

    # creates the base nodes of the tree with one geneset each
    for y in range(0, num_clusters):
        temptree = Tree()
        temptree.data = genesets[y]
        treelist.append(temptree)

    # combines two clusters together based on which two clusters have the smallest average of each clusters genesets
    # compared to each of the other clusters genesets
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)

        # finding which two clusters have the shortest average distance between them
        for i in range(0, num_clusters-1):
            for j in range(i+1, num_clusters):
                total = 0
                numpairs = len(gsInCluster[i]) * len(gsInCluster[j])
                for k in range(0, len(gsInCluster[i])):
                    for l in range(0, len(gsInCluster[j])):
                        total += similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]]
                average = total/numpairs
                if average != 1:
                    if average < minval:
                        minval = average
                        tocluster = (i, j)

        if minval == 1.1:
            done = True
        else:
            # creates a new node that represents the new cluster made
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(0, treelist.__len__()):
                for y in range(0, len(gsInCluster[tocluster[0]])):
                    if genesets[gsInCluster[tocluster[0]][y]] == treelist[x].data:
                        child1 = treelist[x]
                        while child1.parent is not None:
                            child1 = child1.parent
                for y in range(0, len(gsInCluster[tocluster[1]])):
                    if genesets[gsInCluster[tocluster[1]][y]] == treelist[x].data:
                        child2 = treelist[x]
                        while child2.parent is not None:
                            child2 = child2.parent
            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1-minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree

            # adds all the genesets of one cluster to the other
            for i in range(0, len(gsInCluster[tocluster[1]])):
                gsInCluster[tocluster[0]].append(gsInCluster[tocluster[1]][i])
            # gets rid of the cluster that we don't need
            gsInCluster.remove(gsInCluster[tocluster[1]])
            num_clusters -= 1

    # goes through and finds all of the root nodes that we have
    roots = []

    for n in treelist:
        if n.parent is None:
            roots.append(n)

    return roots


def single_cluster(self, jsc):
    # variable declaration
    genesets = self._gsids
    gsInCluster = []
    treelist = []
    similaritymatrix = jsc
    num_clusters = len(genesets)

    # creates initial clusters with one geneset each
    for x in range(0, len(self._gsids)):
        gsInCluster.append([])
        gsInCluster[x].append(x)

    # creates base nodes that represent one geneset each
    for y in range(0, num_clusters):
        temptree = Tree()
        temptree.data = genesets[y]
        treelist.append(temptree)

    # combines two clusters together that have the smallest dissimilarity between any of their genesets
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)
        # finding which two clusters have the shortest longest distance between two genesets
        for i in range(0, num_clusters-1):
            for j in range(i+1, num_clusters):
                for k in range(0, len(gsInCluster[i])):
                    for l in range(0, len(gsInCluster[j])):
                        if similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]] != 1:
                            if similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]] < minval:
                                minval = similaritymatrix[gsInCluster[i][k]][gsInCluster[j][l]]
                                tocluster = (i, j)

        if minval == 1.1:
            done = True
        else:
            # creates a new node that represents the combined cluster
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(0, treelist.__len__()):
                for y in range(0, len(gsInCluster[tocluster[0]])):
                    if genesets[gsInCluster[tocluster[0]][y]] == treelist[x].data:
                        child1 = treelist[x]
                        while child1.parent is not None:
                            child1 = child1.parent
                for y in range(0, len(gsInCluster[tocluster[1]])):
                    if genesets[gsInCluster[tocluster[1]][y]] == treelist[x].data:
                        child2 = treelist[x]
                        while child2.parent is not None:
                            child2 = child2.parent

            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1-minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree

            # moves all the genesets in one cluster to the other
            for i in range(0, len(gsInCluster[tocluster[1]])):
                gsInCluster[tocluster[0]].append(gsInCluster[tocluster[1]][i])
            # removes the cluster that we don't need anymore
            gsInCluster.remove(gsInCluster[tocluster[1]])
            num_clusters -= 1

    # goes through all the nodes and finds all the roots
    roots = []

    for n in treelist:
        if n.parent is None:
            roots.append(n)

    return roots


def mcquitty_cluster(self, jsc):
    # variable declaration
    genesets = list(self._gsids)
    gsInCluster = []
    treelist = []
    similaritymatrix = jsc
    num_clusters = len(genesets)

    # creates the initial clusters that contain one geneset each
    for x in range(0, len(self._gsids)):
        gsInCluster.append([])
        gsInCluster[x].append(x)

    # creates all the base nodes that represent one geneset each
    for y in range(0, num_clusters):
        temptree = Tree()
        temptree.data = genesets[y]
        treelist.append(temptree)

    # combines two clusters that have the shortest distance between them
    done = False
    while not done:
        minval = 1.1
        tocluster = (0, 0)

        # finding which two clusters have the shortest distance between them
        for i in range(0, num_clusters-1):
            for j in range(i+1, num_clusters):
                if similaritymatrix[i][j] != 1:
                    if similaritymatrix[i][j] < minval:
                        minval = similaritymatrix[i][j]
                        tocluster = (i, j)

        if minval == 1.1:
            done = True
        else:
            # creates a new node that represents the combined clusters
            newtree = Tree()
            child1 = Tree()
            child2 = Tree()
            for x in range(0, treelist.__len__()):
                for y in range(0, len(gsInCluster[tocluster[0]])):
                    if genesets[gsInCluster[tocluster[0]][y]] == treelist[x].data:
                        child1 = treelist[x]
                        while child1.parent is not None:
                            child1 = child1.parent
                for y in range(0, len(gsInCluster[tocluster[1]])):
                    if genesets[gsInCluster[tocluster[1]][y]] == treelist[x].data:
                        child2 = treelist[x]
                        while child2.parent is not None:
                            child2 = child2.parent
            newtree.data = frozenset([child1.data, child2.data])
            newtree.jac = 1-minval
            newtree.left = child1
            newtree.right = child2
            treelist.append(newtree)
            child1.parent = newtree
            child2.parent = newtree

            # recalculates the distance between all the clusters and the new one
            # based on the average of the distance between the old clusters and all the rest
            for i in range(0, len(similaritymatrix)):
                if i != tocluster[0] or i != tocluster[1]:
                    similaritymatrix[tocluster[0]][i] = (similaritymatrix[tocluster[0]][i] +
                                                         similaritymatrix[tocluster[1]][i]) / 2
            similaritymatrix.remove(similaritymatrix[tocluster[1]])
            for i in range(0, len(similaritymatrix)):
                similaritymatrix[i].remove(similaritymatrix[i][tocluster[1]])

            # moves all the genesets in one cluster to the other
            for i in range(0, len(gsInCluster[tocluster[1]])):
                gsInCluster[tocluster[0]].append(gsInCluster[tocluster[1]][i])
            # deletes that cluster that doesn't have anything in it
            gsInCluster.remove(gsInCluster[tocluster[1]])
            num_clusters -= 1

    # goes through all the nodes and finds all the roots so we can display them to the user
    roots = []

    for n in treelist:
        if n.parent is None:
            roots.append(n)

    return roots


def jaccard_heatmap(self, cluster):
    cluster_set = []
    jac_matrix = [[0]*5 for i in range(0, 5)]

    for c in cluster:
        flat_set = []

        for g in c:
            g.flatten(flat_set)

        cluster_set.append(set(flat_set))

    for i in range(0, len(cluster_set)):
        for j in range(i, len(cluster_set)):
            jac_matrix[i][j] = len(set(cluster_set[i] & cluster_set[j]))/float(len(set(cluster_set[i] | cluster_set[j])))
            jac_matrix[j][i] = jac_matrix[i][j]

    return jac_matrix


class JaccardClustering(tools.toolbase.GeneWeaverToolBase):
    name = "tools.JaccardClustering.JaccardClustering"

    def __init__(self, *args, **kwargs):
        self.init("JaccardClustering")
        self.urlroot=''


    # Main execution
    def mainexec(self):
        method = self._parameters['JaccardClustering_Method'].lower()
        output_prefix = self._parameters["output_prefix"]   # {.el,.dot,.png}
        gs_dict = self._parameters["gs_dict"]

        num_edges=0

        # 1. Compute Jaccard dissimilarities for the geneset matrix
        # NOTE: This implementation fails on test-geneset1
        self.update_progress("Computing Jaccard Dissimilarities...")
        i=0;
        JSC=[]

        # 1a. Traverse all rows
        for i in range(0, self._num_genesets):
            self.update_progress('', (i+1)*100/self._num_genesets )
            JSC.append([])

            # 1b. Traverse all columns
            for j in range(0, self._num_genesets):
                m = self._pairwisedeletion_matrix[i][j]

                # 1c. Union pairwise deletion and calculate similarity
                union = m['01'] + m['10'] + m['11']
                if union==0:
                    similarity=0
                else:
                    similarity=float(m['11'])/float(union)

                # 1d. Calculate and append dissimilarity for matrix
                JSC[ i ].append( 1.0-similarity )

        k=self._num_genesets/3;

        # 2. Compute geneset clustering
        self.update_progress("Clustering GeneSets...")

        jout = open("%s.jac" % (output_prefix), "w")

        clabels = {}
        i=0
        for gsid in self._gsids:
            clabels[i]='"%s: %s"' % (gsid, self._gsnames[i])
            print("\t%s" % clabels[i], file=jout)
            i+=1
        print('', file=jout)

        i=0
        for row in JSC:
            print(clabels[i], file=jout)
            for jac in row:
                print("\t%f" % (jac), file=jout)
            print('', file=jout)
            i+=1
        jout.close()

        gsids_only = {}
        gsnames_only = {}
        i=0
        for gs in self._gsids:
            gsids_only[i]=self._gsids[i][2:]
            gsnames_only[i]=self._gsnames[i]
            i+=1

        if method == 'heatmap':

            cluster = [wards_cluster(self, list(JSC), self._matrix), complete_cluster(self, list(JSC)),
                       average_cluster(self, list(JSC)), single_cluster(self, list(JSC)),
                       mcquitty_cluster(self, list(JSC))]
            info = ['Ward', 'Complete', 'Average', 'Single', 'McQuitty']

            test = jaccard_heatmap(self, cluster)

            out = open('%s.json' % (output_prefix), 'w')
            to_jsonMatrix(test, info, file=out)
            out.close()

            out = open('%s.hmp' % (output_prefix), 'w')
            for line in test:
                print(line, file=out)
            out.close()

        else:
            if method == 'ward':
                test = wards_cluster(self, JSC, self._matrix)

            elif method == 'complete':
                test = complete_cluster(self, JSC)

            elif method == 'average':
                test = average_cluster(self, JSC)

            elif method == 'mcquitty':
                test = mcquitty_cluster(self, JSC)

            elif method == 'single':
                test = single_cluster(self, JSC)

            # Convert to JSON
            out = open('%s.json' % (output_prefix), 'w')
            to_jsonTree(test, gs_dict=gs_dict, _file=out)
            out.close()

        self._results['result_image']="%s.png" % (output_prefix)
        self._results['result_pdf']="%s.pdf" % (output_prefix)

        self._results['edited_gs_ids']=gsids_only
        self._results['edited_gs_names']=gsnames_only
        self._results['gs_ids']=self._gsids
        self._results['gs_names']=self._gsnames
        self._results['parameters']=self._parameters
        self._results['method']= method[0].upper()+method[1:]

JaccardClustering = celery.register_task(JaccardClustering())
