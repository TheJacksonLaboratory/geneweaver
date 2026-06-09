/**
 * @author Carter Ratley
 * This file implements the DBSCAN clustering algorithm
 * Date Created: 9/22/16
 * Date Last Modified: 11/11/16
 */
#include "dbscan.h"

/**
 * Runs all parts of the DBSCAN algorithm returning a 2D vector containing all the clusters
 * @param geneToSet the 2D vector representing the bipartite graph for genes and gene sets
 * @param epsilon the "radius" for genes to be considered in the same cluster
 * @param minPoints the minimum number of points for a group of points to be considered a cluster
 * @param numGenes the number of genes
 * @return a 2D vector containing all the clusters and the points in the cluster
 */
vector<vector<long>> DBSCAN::findClustersDBSCAN(vector<vector<long>> const &geneToSet, long const &epsilon, long const &minPts, long const& numGenes){
    // Makes the initial gene to gene graph (adjacency list)
    vector<vector<long > > geneToGene = makeGeneToGene(geneToSet, numGenes);

    // Runs DBSCAN
    vector<vector<long> > clusters = runDBSCAN(geneToGene, epsilon, minPts);

    return clusters;
}

/**
 * Makes a 2D vector that will hold all the genes adjacent to each gene
 * @param geneToSet the 2D vector representing the bipartite graph for genes and gene sets
 * @param numGenes the number of genes
 * @return a 2D vector that will hold the gene to gene adjacency list
 */
vector<vector<long> > DBSCAN::makeGeneToGene(vector<vector<long> > const &geneToSet, long const &numGenes){
    vector<vector<long> > adjacencyList(numGenes, vector<long>());

    for(int i = 0; i < geneToSet.size(); i++){
        // Before entering this loop, makes sure at least 2 genes are in the same gene set
        if(geneToSet[i].size() >= 2){
            // Adds each gene in the list to each other's adjacency list
            for(long x = 0; x < geneToSet[i].size() - 1; x++){
                for(long y = x + 1; y < geneToSet[i].size(); y++){
                    adjacencyList[geneToSet[i][x]].push_back(geneToSet[i][y]);
                    adjacencyList[geneToSet[i][y]].push_back(geneToSet[i][x]);
                }
            }
        }
    }

    return adjacencyList;
}

/**
 * Runs the DBSCAN clustering algorithm
 * @param geneToGene a 2D vector with all pair shortest paths for all the genes
 * @param epsilon the "radius" for genes to be considered in the same cluster
 * @param minPoints the minimum number of points for a group of points to be considered a cluster
 * @return a 2D vector containing all the clusters and the points in the cluster
 */
vector<vector<long> > DBSCAN::runDBSCAN(vector<vector<long> > const &geneToGene , long const &epsilon , long const &minPoints){
    vector<vector<long> > allClusters; // The 2D array of all clusters

    // Cluster C = 0
    vector<long> cluster;

     // For each gene in geneToGene
    for(long i = 0; i < geneToGene.size(); i++){
        // Checks to make sure gene is not already in cluster
        if(!isInCluster(allClusters, cluster, i)){

            // Neighbors = regionQuery(Gene, Epsilon)
            vector<long> neighbors = regionQuery(geneToGene, i, epsilon);

            // if(sizeof(Neighbors) >= minPoints
            if(neighbors.size() >= minPoints){
                 // Expands the cluster
                expandCluster(geneToGene, neighbors, cluster, epsilon, minPoints, allClusters);

                // Adds the cluster to the list of clusters
                allClusters.push_back(cluster);

            }

            // Clear the vector
            cluster.clear();
        }

    }

    return allClusters;
}

/**
 * Checks all of a points neighbors to find all the points within a certain radius of that point
 * @param geneToGene a 2D vector with all pair shortest paths for all the genes
 * @param gene the gene to check all the neighbors of
 * @param epsilon the "radius" for genes to be considered a neighbor
 * @return a list of all the gene's neighbors (including itself)
 */
vector<long> DBSCAN::regionQuery(vector<vector<long> > const & geneToGene, long const &gene, long const &epsilon){

    vector<long> neighbors; // A list of all the neighbors
    queue<long> neighborQueue; // The queue for traversing the neighbors
    long distance = 1; // The current distance we are from the original gene
    bool neighborsArr[geneToGene.size()]; // An array that says if a gene is already in the list
    fill_n(neighborsArr, geneToGene.size(), false);

    // Adds the gene passed in to the neighbor list
    neighbors.push_back(gene);

    // Adds all the original gene's neighbors
    for(int i = 0; i < geneToGene[gene].size(); i++){
        neighborQueue.push(geneToGene[gene][i]);
        neighborsArr[geneToGene[gene][i]] = true;
    }

    // While we have not gotten epsilon - 1 away and there are items in the queue
    while(neighborQueue.size() > 0 && distance < epsilon){

        // Pop the front of the queue and get the element
        long element = neighborQueue.front();
        neighborQueue.pop();

        // If the item was -1, increment the distance
        if(element == -1){
            distance++;
            neighborQueue.push(-1);
        }
        else{
            // Adds all the elements to the queue and the found array if they are not already in the found array
            for(int i = 0; i < geneToGene[element].size(); i++){

                if(!neighborsArr[geneToGene[element][i]]){
                    neighborQueue.push(geneToGene[element][i]);
                    neighborsArr[geneToGene[element][i]] = true;
                }
            }
        }
    }

    // Puts the rest of the neighbors in the queue on the list if they are not in the list already
    while(neighborQueue.size() > 0){
        // Makes sure we don't add the -1 values to the queue
        if(neighborQueue.front() != -1){
            neighborsArr[neighborQueue.front()] = true;
        }


        // Remove from the queue
        neighborQueue.pop();

    }

    // Builds the vector based on the neighbors that were found
    for(int i = 0; i < geneToGene.size(); i++){
        if(neighborsArr[i]){
            neighbors.push_back(i);
        }
    }

    return neighbors;
}

/**
 * Expands the cluster by checking all of the neighbors of a starting polong to expand the cluster if possible
 * @param geneToGene a 2D vector with all pair shortest paths for all the genes
 * @param neighbors all the points to check to see if it can for a cluster with its neighbors
 * @param cluster the current cluster, values will be added to this cluster if applicable
 * @param epsilon the "radius" for genes to be considered in the same cluster
 * @param minPoints the minimum number of points for a group of points to be considered a cluster
 * @param allClusters a 2D vector containing all the clusters and the points in the cluster
 */
void DBSCAN::expandCluster(vector<vector<long> > const &geneToGene, vector<long> &neighbors, vector<long> &cluster, long const &epsilon, long const &minPoints, vector<vector<long> > &allClusters){

    // Adds the initial gene to the cluster
    if(!isInCluster(allClusters, cluster, neighbors[0])){
        cluster.push_back(neighbors[0]);
    }

    // For each gene in neighborPts
    for(long i = 1; i < neighbors.size(); i++){
        if(!isInCluster(allClusters, cluster, neighbors[i])){
             // Finds all of that genes neighbors
            vector<long> newNeighbors = regionQuery(geneToGene, neighbors[i], epsilon);

            // if(sizeof(NewNeighbors) >= minPoints
            if(newNeighbors.size() >= minPoints){
                // Neighbors = NewNeighbors + Neighbors
                addNeighbors(neighbors, newNeighbors, cluster, allClusters);
            }

            // Add gene to C
            cluster.push_back(neighbors[i]);
        }
    }
}

/**
 * Adds the new neighbors to the overall neighbors list if they are not already in the list
 * @param neighbors the overall neighbors
 * @param newNeighbors the neighbors to add to the overall neighbors list
 * @param currentCluster the current cluster we are looking at
 * @param allClusters the list of all clusters
 */
void DBSCAN::addNeighbors(vector<long> &neighbors, vector<long> const &newNeighbors, vector<long> const &currentCluster, vector<vector<long> > const &allClusters){

    for(long i = 0; i < newNeighbors.size(); i++){
        // Only add genes that are not in a cluster or in this list
        if(!isInCluster(allClusters, currentCluster, newNeighbors[i])){
            // Checks to see if it already in the neighbors list
            bool found = false;
            for(long j = 0; j < neighbors.size() && !found; j++){
                if(newNeighbors[i] == neighbors[j]){
                    found = true;
                }
            }
            // Adds to the list if the gene isn't in a cluster and isn't in the neighbors list
            if(!found){
                neighbors.push_back(newNeighbors[i]);
            }

        }
    }
}

/**
 * Checks to see if a gene is already in a cluster
 * @param allClusters the list of all the previously determined clusters
 * @param currentCluster the current cluster that is being worked on
 * @param gene the gene to check
 * @return whether or not the gene is already in a cluster
 */
bool DBSCAN::isInCluster(vector<vector<long> > const &allClusters, vector<long> const &currentCluster, long const &gene){
    // Loops through all the clusters, seeing if the gene is already in a cluster
    if(allClusters.size() > 0){
        for(long i = 0; i < allClusters.size(); i++){
            if(allClusters[i].size() > 0){
                for(long j = 0; j < allClusters[i].size(); j++){
                    if(gene == allClusters[i][j]){
                        return true;
                    }
                }
            }
        }
    }

    // Checks the current cluster for the gene
    if(currentCluster.size() > 0){
        for(long i = 0; i < currentCluster.size(); i++){
            if(currentCluster[i] == gene){
                return true;
            }
        }
    }

    return false;
}