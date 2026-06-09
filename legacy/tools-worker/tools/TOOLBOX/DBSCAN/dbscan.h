/**
 * @author Carter Ratley
 * This file has the function headers for the DBSCAN clustering algorithm
 * Date Created: 9/22/16
 * Date Last Modified: 11/11/16
 */
#ifndef DBSCAN_H
#define DBSCAN_H

#include <iostream> // Can be removed when testing finished. Printing to console for debugging
#include <vector>
#include <queue>

using namespace std;

class DBSCAN{
  private:
    /**
     * Makes a 2D vector that will hold all the genes adjacent to each gene
     * @param geneToSet the 2D vector representing the bipartite graph for genes and gene sets
     * @param numGenes the number of genes
     * @return a 2D vector that will hold the gene to gene adjacency list
     */
    static vector<vector<long> > makeGeneToGene(vector<vector<long> > const &, long const &);

    /**
     * Runs the DBSCAN clustering algorithm
     * @param geneToGene a 2D vector with all pair shortest paths for all the genes
     * @param epsilon the "radius" for genes to be considered in the same cluster
     * @param minPoints the minimum number of points for a group of points to be considered a cluster
     * @return a 2D vector containing all the clusters and the points in the cluster
     */
    static vector<vector<long> > runDBSCAN(vector<vector<long> > const &, long const &, long const &);

    /**
     * Checks all of a points neighbors to find all the points within a certain radius of that point
     * @param geneToGene a 2D vector with all pair shortest paths for all the genes
     * @param gene the gene to check all the neighbors of
     * @param epsilon the "radius" for genes to be considered a neighbor
     * @return a list of all the gene's neighbors (including itself)
     */
    static vector<long> regionQuery(vector<vector<long> > const &, long const &, long const &);

    /**
     * Expands the cluster by checking all of the neighbors of a starting polong to expand the cluster if possible
     * @param geneToGene a 2D vector with all pair shortest paths for all the genes
     * @param neighbors all the points to check to see if it can for a cluster with its neighbors
     * @param cluster the current cluster, values will be added to this cluster if applicable
     * @param epsilon the "radius" for genes to be considered in the same cluster
     * @param minPoints the minimum number of points for a group of points to be considered a cluster
     * @param allClusters a 2D vector containing all the clusters and the points in the cluster
     */
    static void expandCluster(vector<vector<long> > const &, vector<long> &, vector<long> &, long const &, long const &, vector<vector<long> > &);


    /**
     * Adds the new neighbors to the overall neighbors list if they are not already in the list
     * @param neighbors the overall neighbors
     * @param newNeighbors the neighbors to add to the overall neighbors list
     * @param currentCluster the current cluster we are looking at
     * @param allClusters the list of all clusters
     */
    static void addNeighbors(vector<long> &, vector<long> const &, vector<long> const &, vector<vector<long> > const &);

    /**
     * Checks to see if a gene is already in a cluster
     * @param allClusters the list of all the previously determined clusters
     * @param currentCluster the current cluster that is being worked on
     * @param gene the gene to check
     * @return whether or not the gene is already in a cluster
     */
    static bool isInCluster(vector<vector<long> > const &, vector<long> const &, long const &);


  public:
    /**
     * Runs all parts of the DBSCAN algorithm returning a 2D vector containing all the clusters
     * @param geneToSet the 2D vector representing the bipartite graph for genes and gene sets
     * @param epsilon the "radius" for genes to be considered in the same cluster
     * @param minPoints the minimum number of points for a group of points to be considered a cluster
     * @param numGenes the number of genes
     * @return a 2D vector containing all the clusters and the points in the cluster
     */
    static vector<vector<long> > findClustersDBSCAN(vector<vector<long> > const &, long const &, long const &, long const &);
};


#endif