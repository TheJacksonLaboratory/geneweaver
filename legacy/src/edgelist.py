__author__ = 'baker'
'''
This file contains functions to export an edge list for the k-partite view
'''

from geneweaverdb import PooledCursor, dictify_cursor, get_genesets_for_project
from flask import session

def get_genes_from_proj_intersection(proj1, proj2, hom=True):
    '''
    Takes two project ids and returns a list of intersecting genes
    :param proj1:
    :param proj2:
    :return: list of genes
    '''
    genes = []
    if not hom:
        with PooledCursor as cursor:
            cursor.execute('''SELECT gv.ode_gene_id FROM geneset_value gv, project2geneset p2g
                              WHERE p2g.pj_id=%s AND p2g.gs_id=gv.gs_id
                              INTERSECT
                              SELECT gv.ode_gene_id FROM geneset_value gv, project2geneset p2g
                              WHERE p2g.pj_id=1430 and p2g.gs_id=gv.gs_id''', (proj1, proj2,))
    else:
        with PooledCursor as cursor:
            cursor.execute('''SELECT DISTINCT h1.ode_gene_id FROM geneset_value gv, project2geneset p2g, homology h1,
                              homology h2 WHERE p2g.pj_id=%s AND p2g.gs_id=gv.gs_id AND gv.ode_gene_id=h1.ode_gene_id
                              AND h1.hom_id=h2.hom_id
                              INTERSECT
                              SELECT DISTINCT h1.ode_gene_id FROM geneset_value gv, project2geneset p2g, homology h1,
                              homology h2 WHERE p2g.pj_id=%s AND p2g.gs_id=gv.gs_id AND gv.ode_gene_id=h1.ode_gene_id
                              AND h1.hom_id=h2.hom_id''', (proj1, proj2,))
    res = cursor.fetchall()
    if res is not None:
        for r in res:
            genes.append(r[0])
    return genes

def edge_gene2proj(genes, projDict1, partition):
    '''
    Takes a list of genes and a dictionary of genesets. If the a gene exists in a geneset, then an edge
    is created.
    :param genes:
    :param projDict1:
    :return: list of edges
    '''
    return

def create_kpartite_file_from_gene_intersection(taskid, proj1, proj2, homology=True):
    '''
    This function takes two project ids, finds the intersection of genes and constructs
    the a task.kel file (which stands for K-clique Edge List (kel). This is a tab-delimited
    value file with values in the columns separated by tabs, with each column representing
    a partition. The file has a \n EOF character.
    :param taskid:
    :param proj1:
    :param proj2:
    :param homology: Default = True
    :return: /results-dir/[task_id].kel
    '''
    # Set variables
    usr_id = session['user_id']
    partition3 = []
    out = ''

    # Get the intersecting set of genes between proj1 and proj2 as a list
    genes = get_genes_from_proj_intersection(proj1, proj2, homology)

    # Get all geneset and genes in a project as a dictionary
    projDict1 = get_genesets_for_project(proj1, usr_id)
    projDict2 = get_genesets_for_project(proj2, usr_id)

    # Populate the edges between the intersecting genes and projDict1, called partition1
    partition1 = edge_gene2proj(genes, projDict1, 1)

    # Populate the edges between the intersecting genes and projDict2, called partition2
    partition2 = edge_gene2proj(genes, projDict2, 2)