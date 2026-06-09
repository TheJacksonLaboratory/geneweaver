/* API for Bit-Based Adjacency Matrix for undirected graphs */
/* Implement functions defined in graph.h */
/* Graph Theory Team, Computer Science Department */
/* University of Tennessee, Knoxville */
/* Yun Zhang, yzhang@cs.utk.edu, December 12, 2004 */

/* Modified April 2014 by Charles Phillips */
/* to perform maximal k-partite-clique enumeration on */
/* k-partite graphs, by adding all possible edges */
/* within each partite set */

#include <string>
#include <vector>
#include <fstream>
#include <iostream>
#include <map>

#include <string.h>
#include <search.h>
#include "graph.h"

extern int REMOVEINTRA;

//=======================================================================
// splits a null terminated character array s into a vector of strings
// c is the character to split on                 
//=======================================================================
void split(std::vector<std::string>& v, const char* s, char c)
{                
  v.clear();
  while (true) 
  {        
    const char* begin = s;

    while (*s != c && *s) { ++s; }

    v.push_back(std::string(begin, s));

    if (!*s) break;

    if (!*++s) break;
  }

  if (*--s == c)                            //if last character is c, append another empty string
    v.push_back("");
}

/* Malloc and initialize a graph, returns a pointer to it */
Graph *graph_make(unsigned int num_vertices)
{
  Graph *G;
  unsigned int i;
  int num_ints = bit_num_ints(num_vertices);
  
  G = (Graph *) malloc(sizeof(Graph));
  if (G == NULL) { perror("malloc"); exit(-1); }
  G->_num_vertices = num_vertices;
  G->_num_active_vertices = num_vertices;
  G->_num_edges = 0;
  G->_num_bytes = num_ints * sizeof(int);

  G->_label = (char **) malloc(num_vertices * sizeof(char *));
  if (G->_label == NULL) { perror("graph_make : malloc label"); exit(-1); }
  
  G->_neighbor = (unsigned int **) malloc(num_vertices * sizeof(unsigned int *));
  if (G->_neighbor == NULL) { perror("malloc"); exit(-1); }
  G->_neighbor[0] = (unsigned int *) malloc(G->_num_bytes * num_vertices);
  if (G->_neighbor[0] == NULL) { perror("malloc"); exit(-1); }
  for (i = 0; i < num_vertices; i++) {
    G->_neighbor[i] = G->_neighbor[0] + i * num_ints;
  }
  
  G->_active = (unsigned int *) malloc(G->_num_bytes);
  if (G->_active == NULL) { perror("malloc"); exit(-1); }
  
  G->_degree = (unsigned short *) malloc(num_vertices * sizeof(unsigned short));
  if (G->_degree == NULL) { perror("malloc"); exit(-1); }
  
  memset(G->_neighbor[0], 0, G->_num_bytes * num_vertices);
  memset(G->_active, 0xffff, G->_num_bytes);
  memset(G->_degree, 0, num_vertices * sizeof(unsigned short));
  
  return G;
}


/* Free the memory of a graph */
void graph_free(Graph *G)
{
  unsigned int i;
  if (G != NULL) {
    if (G->_neighbor) {
      if (G->_neighbor[0]) free(G->_neighbor[0]);
      free(G->_neighbor);
    }
    if (G->_active) free(G->_active);
    if (G->_degree) free(G->_degree);
	for (i=0; i<G->_num_vertices; i++) free(G->_label[i]);
    free(G);
  }
}

/** I/O functions for Graph **/

/* Read in an unweighted edge-list file, return a pointer to the graph */
Graph * UW_EdgeList_in(FILE *fp)
{
  unsigned int u, v, n, e, i, x;
  Graph *G;
  x = fscanf(fp, "%d %d", &n, &e);
  G = graph_make(n);
  for (i = 0; i < e; i++) {
    x = fscanf(fp, "%d", &u);
    x = fscanf(fp, "%d", &v);
    add_edge(G, u, v);
  }
  return G;
}

Graph* read_graph(char* filename)
{
  unsigned int num_vertices=0, num_edges, i, j, k, m, n, size, neighbor;
  int endpoint[2];
  std::vector <int> partiteSum;
  Graph* G;
  std::vector <std::string> line;
  std::vector <int> partiteSizes;
  std::string str;
  std::fstream f;
  bool hasCommonNeighbor;
  int num_skipped = 0;

  f.open(filename);
  if (!f) { std::cerr << "Error opening graph file '" << filename << "'\n"; exit(1); }

  getline(f, str);  //read the first line    //read first line in graph file
  split(line, str.c_str(), '\t');

  for (i=0; i < line.size()-1; i++)          //find the total number of vertices
  {
    partiteSum.push_back(num_vertices);
    num_vertices += atoi(line[i].c_str());
    partiteSizes.push_back(atoi(line[i].c_str()));
  }

  G = graph_make(num_vertices);              //allocate the graph
  G->vertexLabels.resize(num_vertices);
  G->numPartiteSets = line.size()-1;
  G->vertexLabelsMap.resize(line.size()-1);
  G->cliquesize.resize(line.size()-1);
  G->maxEdgeCliqueSize = 0;
  G->maxVertexCliqueSize = 0;

  num_edges = atoi(line[line.size()-1].c_str());

//  for (i=0; i<line.size()-1; i++)            //set size of each partite set
//    G->partiteSizes.push_back(atoi(line[i].c_str()));
  G->partiteSizes = partiteSizes;
  G->partiteSum = partiteSum;
  G->mask = (1 << G->partiteSizes.size()) - 1;  //partite set mask

  for (i=0; i < num_edges; i++)              //read each edge from the graph file
  {
    getline(f, str);
    split(line, str.c_str(), '\t');

    k = 0;
    for (j=0; j<line.size(); j++)
    {
      if (line[j] != "")
      {               //if vertex label has not been read yet, add it
//        std::cout << line[j] << std::endl;
        if (G->vertexLabelsMap[j].count(line[j]) == 0)
        {
          size = G->vertexLabelsMap[j].size();
//          std::cout << "sum: " << partiteSum[j] << std::endl;
//          std::cout << "size: " << size << std::endl;
          G->vertexLabels[partiteSum[j] + size] = line[j];  //unnecessary
          G->_label[partiteSum[j] + size] = strdup(line[j].c_str());

          G->vertexLabelsMap[j][line[j]] = size;
        }
 
        endpoint[k] = partiteSum[j] + G->vertexLabelsMap[j][line[j]]; //get each endpoint
        k++;
      }
    }
//    std::cout << endpoint[0] << "\t" << endpoint[1] << std::endl;
    add_edge(G, endpoint[0], endpoint[1]);
  }
  f.close();

  //add all possible edges within each partite set
  for (i=0; i < partiteSizes.size(); i++)
  {
    for (j=0; j < partiteSizes[i]; j++)
    {
      G->whichPartiteSet.push_back(i);          //set up whichPartiteSet array
      for (k=j+1; k < partiteSizes[i]; k++)
      {
        endpoint[0] = partiteSum[i] + j;
        endpoint[1] = partiteSum[i] + k;


        if (!REMOVEINTRA)
        {
          add_edge(G, endpoint[0], endpoint[1]);
        }
        else
        {
          hasCommonNeighbor = false;
          for (m=0; m < partiteSizes.size(); m++)   //only add edges with a common
          {                                         //neighbor in another partite set
            if (m == i) continue;
            for (n=0; n < partiteSizes[m]; n++)
            {
              neighbor = partiteSum[m] + n;
              //std::cout << endpoint[0] << "\t" << endpoint[1] << "\t" << neighbor << "\n";
              if (edge_exists(G, endpoint[0], neighbor) && edge_exists(G, endpoint[1], neighbor))
              {
                hasCommonNeighbor = true;
                break;
              }
            }
            if(hasCommonNeighbor) break;
          }
          if (hasCommonNeighbor)
          {
            add_edge(G, endpoint[0], endpoint[1]);
          }
          else
            num_skipped++;
        }
      }
    }
  }

  if (REMOVEINTRA)
    printf("removed %d intra-partite edges\n", num_skipped);

  return G;
}

/* read a graph */
Graph * graph_edgelist_in(FILE *fp)
{
  unsigned int n, e;
  int u, v;
  unsigned int k=0, edges=0, r;
  char word1[100], word2[100];
  Graph *G;
  int *id, *ids;
  ENTRY item;
  ENTRY *found_item;

  if (fscanf(fp, "%d %d", &n, &e) != 2) {
	fprintf(stderr, "Bad file format : n e incorrect\n");
	exit(-1);
  }

  G = graph_make(n);

  /* create a hash table */
  (void) hcreate(n);
  ids = (int *) malloc(n * sizeof(int));
  
  while ((r = fscanf(fp, "%s\t%s", word1, word2)) != EOF) {
	if (r != 2) {
	  fprintf(stderr, "Bad file format : label1 label2 incorrect\n");
	  exit(-1);
	}

	item.key = word1;
	if ((found_item = hsearch(item, FIND)) != NULL) {
	  id = (int *) (found_item->data);
	  u = *id;
	}
	else {
	  u = k;
	  G->_label[k++] = strdup(word1);
	  item.key = G->_label[u];
	  ids[u] = u;
	  item.data = (void *) (ids+u);
	  (void) hsearch(item, ENTER);
	}
	
	item.key = word2;
	if ((found_item = hsearch(item, FIND)) != NULL) {
	  id = (int *) (found_item->data);
	  v = *id;
	}
	else {
	  v = k;
	  G->_label[k++] = strdup(word2);
	  item.key = G->_label[v];
	  ids[v] = v;
	  item.data = (void *) (ids+v);
	  (void) hsearch(item, ENTER);
	}
	
	if (k > n) {
	  fprintf(stderr, "Bad file format : too many labels\n");
	  exit(-1);
	}
	
	add_edge(G, u, v);
	edges++;

//	printf("%s (%d)\t%s (%d)\n", word1, u, word2, v);

  }
  
  if (edges != e) { 
	fprintf(stderr, "edgelist_in : # of edges incorrect\n");
	fprintf(stderr, "edgelist_in : %d vertices, %d edges\n", k, edges);
  }
  if (k != n) {
	fprintf(stderr, "edgelist_in : # of vertices incorrect\n");
	fprintf(stderr, "edgelist_in : %d vertices, %d edges\n", k, edges);
	G->_num_vertices = k;
	G->_num_active_vertices = k;
  }
  
  /* destroy the hash tabel */
  (void) hdestroy();
  free(ids);
  
  return G;
}

bool has_kpartite_neighbors(Graph* G, int v1, int v2)
{
  int i, j, k;
  int partite1 = G->whichPartiteSet[v1];
  int partite2 = G->whichPartiteSet[v2];
  bool has_partite_neighbor;

  for (i=0; i < G->partiteSizes.size(); i++)
  {
    if (i == partite1 || i == partite2) continue;
//    std::cout << partite1 << "\t" << partite2 << "\t" << i << "\t" << G->partiteSizes[i] << "\t" << G->partiteSum[i] << std::endl;

    has_partite_neighbor = false;
    for (j=0; j < G->partiteSizes[i]; j++)
    {
      int whichvertex = G->partiteSum[i] + j;
 
//      std::cout << v1 << "\t" << v2 << "\t" << whichvertex << std::endl;
//      std::cout << j << std::endl;

      if (edge_exists(G, v1, whichvertex) && edge_exists(G, v2, whichvertex))
      {
        has_partite_neighbor = true;
        break;
      }
    }
    
    if (!has_partite_neighbor)
      return false;
  }

  return true;
}


//remove all edges between vertices in different partite sets that
//do not have a common neighbor in all other partite sets
void remove_interpartite_edges(Graph* G)
{
  int i, j, k, m, n;
  int v1, v2, num_deleted=0;

  for (i=0; i < G->partiteSizes.size(); i++)
    for (j=i+1; j < G->partiteSizes.size(); j++)
    {
      for (k=0; k < G->partiteSizes[i]; k++)
        for (m=0; m < G->partiteSizes[j]; m++)
        {
          v1 = G->partiteSum[i] + k;         
          v2 = G->partiteSum[j] + m;
          if (edge_exists(G, v1, v2))
          {
            if (!has_kpartite_neighbors(G, v1, v2))
            {
              delete_edge(G, v1, v2);
              num_deleted++;
            } 
          }
          //std::cout << v1 << "\t" << v2 << std::endl;
        }

    }

  printf("deleted %d inter-partite edges\n", num_deleted);
  
}


/* Write out a graph as unweighted edge-list to a file pointer */
void UW_EdgeList_out(FILE *fp, Graph *G)
{
  unsigned int i, j, n;
  fprintf(fp, "%d %d\n", num_active_vertex(G), num_edges(G));
  n = num_vertices(G);
  for (i = 0; i < n; i++)
    for (j = i + 1; j < n; j++)
      if (edge_exists(G, i, j))
        fprintf(fp, "%s\t%s\n", G->_label[i], G->_label[j]);
}

/* Write out a graph as an adjacency matrix to a file pointer */
void AdjMatrix_out(FILE *fp, Graph *G)
{
  unsigned int i, j, n;
  n = num_vertices(G);
  fprintf(fp, "%d %d %d\n", n, num_active_vertex(G), num_edges(G));
  for (i = 0; i < n; i++) {
    for (j = 0; j < n; j++)
      if (edge_exists(G, i, j))
        fprintf(fp, "1 ");
      else fprintf(fp, "0 ");
    fprintf(fp, "\n");
  }
}

/* Write out the degree of each vertex in a graph to a file pointer */
void DegreeList_out(FILE *fp, Graph *G)
{
  unsigned int i, n;
  n = num_vertices(G);
  fprintf(fp, "DegreeList %d %d\n", n, num_active_vertex(G));
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      fprintf(fp, "%s\t%d\n", G->_label[i], degree(G, i));
  return;
}
 

/** Functions to returns a vertex of certain degree **/

/* Returns the highest degree */
unsigned short highest_degree(Graph *G)
{
  unsigned int n, i;
  unsigned int h = 0; 
  n = num_vertices(G); 
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) > h) 
        h = degree(G, i);
  return h;
}


/* Returns the lowest degree */
unsigned short lowest_degree(Graph *G)
{
  unsigned int n, i;
  unsigned int l = 65535; 
  n = num_vertices(G); 
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) < l) 
        l = degree(G, i);
  return l;
}

/* Returns one of the vertices with highest degree */
unsigned int highest_degree_vertex(Graph *G)
{
  unsigned int n, i;
  unsigned int h = 0, highest; 
  n = num_vertices(G); 
  highest = n;
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) > h) {
        h = degree(G, i);
		highest = i;
      }
  return highest;
}

/* Returns one of the vertices with lowest degree */
unsigned int lowest_degree_vertex(Graph *G)
{
  unsigned int n, i;
  unsigned int l = 65535, lowest;; 
  n = num_vertices(G); 
  lowest = n;
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) < l) {
        l = degree(G, i);
		lowest = i;
      }
  return lowest;
}

/* Returns one of the vertices with degree = k */
int equal_degree_vertex(Graph *G, unsigned short k)
{
  unsigned int n, i;
  n = num_vertices(G); 
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) == k)
        return i;
  return -1;
}

/* Returns one of the vertices with degree > k */
int higher_degree_vertex(Graph *G, unsigned short k)
{
  unsigned int n, i;
  n = num_vertices(G); 
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) > k)
        return i;
  return -1;
}

/* Returns one of the vertices with degree < k */
int lower_degree_vertex(Graph *G, unsigned short k)
{
  unsigned int n, i;
  n = num_vertices(G); 
  for (i = 0; i < n; i++)
    if (vertex_exists(G, i))
      if (degree(G, i) < k)
        return i;
  return -1;
}



