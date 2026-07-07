/* Enumerate biclique in bipartite graphs
 * Author: Yun Zhang
 * Date: September 2006
 */


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "utility.h"
#include "bigraph.h"
#include "biclique.h"


#define LMIN 2

/* Global Variables */
int LLEAST, RLEAST;
int VERSION;
int PRINT;
int CACHE_SIZE;
Cache *CACHE;

typedef unsigned long num_t;

#ifdef PERFORMANCE
int node_num;
double time_check, time_expand, time_out;
#endif


/* ------------------------------------------------------------- *
 * Function: biclique_cache_make()                               *
 * ------------------------------------------------------------- */
Cache *biclique_cache_make(int size, int key_size)
{
  Cache *C;
  int i;
  C = (Cache *) malloc(sizeof(Cache));
  if (C == NULL) { perror("cache malloc"); exit(-1); }
  C->_cache_size = size;
  C->_key_size = key_size * sizeof(unsigned int);
  C->_timestamp = 0;
  C->_num_hit = 0;
  C->_entry = (Entry *) calloc(size, sizeof(Entry));
  if (C->_entry == NULL) { perror("cache entry calloc"); exit(-1); }
  for (i = 0; i < size; i++) {
	C->_entry[i]._key = (unsigned int *)calloc(key_size, sizeof(unsigned int));
    if (C->_entry[i]._key == NULL) { perror("cache key calloc"); exit(-1); }
  }
  return C;
}

/* ------------------------------------------------------------- *
 * Function: biclique_cache_free()                               *
 * ------------------------------------------------------------- */
void biclique_cache_free(Cache *C)
{
  int i;
  for (i = 0; i < C->_cache_size; i++) {
	free(C->_entry[i]._key);
  }
  free(C->_entry);
  free(C);
}

/* ------------------------------------------------------------- *
 * Function: biclique_cache_add_entry()                          *
 * ------------------------------------------------------------- */
void biclique_cache_add_entry(Cache *C, void *key, int value)
{
  int victim = 0, victim_timestamp;
  int i;
  victim_timestamp = C->_entry[0]._timestamp;
  for (i = 1; i < C->_cache_size; i++) {
	if (C->_entry[i]._timestamp < victim_timestamp) {
	  victim_timestamp = C->_entry[i]._timestamp;
	  victim = i;
	}
  }
  memcpy(C->_entry[victim]._key, key, C->_key_size);
  C->_entry[victim]._value = value;
  C->_entry[victim]._timestamp = C->_timestamp++;
}

/* ------------------------------------------------------------- *
 * Function: biclique_cache_find_key()                           *
 * ------------------------------------------------------------- */
int biclique_cache_find_key(Cache *C, void *key)
{
  int i;
  for (i = 0; i < C->_cache_size; i++) {
	if (!memcmp(C->_entry[i]._key, key, C->_key_size)) {
	  C->_num_hit++;
	  C->_entry[i]._timestamp = C->_timestamp++;
	  return (C->_entry[i]._value);
	}
  }
  return -1;
}

/* ------------------------------------------------------------- *
 * Function: biclique_cache_perform_out()                        *
 * ------------------------------------------------------------- */
void biclique_cache_perform_out(FILE *fp, Cache *C)
{
  fprintf(fp, "%llu checks\t", C->_timestamp);
  fprintf(fp, "%u hits\t", C->_num_hit);
  fprintf(fp, "%f hit ratio\n", (float)C->_num_hit/(float)C->_timestamp);
}



/* ------------------------------------------------------------- *
 * Function: biclique_out()                                      *
 * ------------------------------------------------------------- */
void biclique_out(FILE *fp, BiGraph *G, vid_t *right, \
		unsigned int *left, int rlen, int llen)
{
  int i, j;
  for (i = 0; i < rlen-1; i++)
	fprintf(fp, "%s\t", G->_label_v2[right[i]]);
  fprintf(fp, "%s\n", G->_label_v2[right[i]]);
  for (i = 0; i < llen; i++)
	if (IS_SET(left, i)) { fprintf(fp, "%s", G->_label_v1[i]); break; }
  for (j = i+1; j < llen; j++)
	if (IS_SET(left, j)) fprintf(fp, "\t%s", G->_label_v1[j]);
  fprintf(fp, "\n\n");
  return;
}


/* ------------------------------------------------------------- *
 * Function: biclique_num_right()                                *
 *   Use a cache to compute the number of neighbors of a set of  *
 *   vertices on left side.                                      *
 * ------------------------------------------------------------- */
int biclique_num_right(BiGraph *G, unsigned int *left, int llen)
{
  int n1 = bigraph_num_v1(G);
  int b1 = G->_num_bytes_v1;
  vid_t left_vertex[llen];
  unsigned int right[b1/sizeof(int)];
  int num_right;
  int i, j = 0;
  
  num_right = biclique_cache_find_key(CACHE, left);
  if (num_right != -1) { return num_right; }

  memset(left_vertex, 0, llen*sizeof(vid_t));
  for (i = 0; i < n1; i++) {
	if (IS_SET(left, i)) {
	  left_vertex[j++] = i;  if (j == llen) break;
	}
  }

  if (llen == 1) return bigraph_degree_v1(G, left_vertex[0]);
  
  memcpy(right, G->_neighbor_v1[left_vertex[0]], b1);
  for (i = 1; i < llen; i++)
	bit_intersect(right, G->_neighbor_v1[left_vertex[i]], b1);
  bit_count_ones(num_right, right, b1);
  
  biclique_cache_add_entry(CACHE, left, num_right);
  
  return num_right;
}

/* ------------------------------------------------------------- *
 * Function: biclique_find()                                     *
 *   Recursive function to find bicliques                        *
 * ------------------------------------------------------------- */
void biclique_find_v1(FILE *fp, BiGraph *G, num_t *nclique, \
		vid_t *right, unsigned int *left, int rlen, int llen)
{
  unsigned int n1 = bigraph_num_v1(G);
  unsigned int n2 = bigraph_num_v2(G);
  int b2 = G->_num_bytes_v2;
  unsigned int left_new[b2/sizeof(int)];
  vid_t right_new[n2];
  int llen_new;
  int nright = -1;
  int i;

//  for (i = 0; i < rlen; i++) printf("%d ", right[i]);
//  printf("\n");

  /* Decide if it is maximal */
  if (rlen >= RLEAST) {
    nright = biclique_num_right(G, left, llen);
    if (rlen == nright) { 
	  nclique[(rlen-1)*n1+llen-1]++;
	  if (PRINT) biclique_out(fp, G, right, left, rlen, n1);
    }
  }
  
  /* Recursively find bicliques */
  for (i = right[rlen-1]+1; i < n2; i++) {
	if (bigraph_degree_v2(G, i) < MAX(LLEAST,2)) continue;
	memcpy(left_new, left, b2);
    bit_intersect(left_new, G->_neighbor_v2[i], b2);
	bit_count_ones(llen_new, left_new, b2);
	if (llen_new >= MAX(LLEAST,LMIN)) {
      memcpy(right_new, right, n2*sizeof(vid_t));
	  right_new[rlen] = i;
	  biclique_find_v1(fp, G, nclique, right_new, left_new, rlen+1, llen_new);
	}
  }
  
  return;	
}



/* ------------------------------------------------------------- *
 * Function: biclique_find_left()                                *
 * ------------------------------------------------------------- */
void biclique_find_left(FILE *fp, BiGraph *G, num_t *nclique)
{
  unsigned int n1 = bigraph_num_v1(G);
  unsigned int n2 = bigraph_num_v2(G);
  int b2 = G->_num_bytes_v2;
  vid_t right_vertex[n2];
  unsigned int left[b2/sizeof(int)];
  int nright, nleft;
  vid_t i, j, k;
  
  for (i = 0; i < n1; i++) {
	nright = bigraph_degree_v1(G, i);
	if (nright < RLEAST) continue;
    
	/* Find the neighbors on right side */
    memset(right_vertex, 0, n2*sizeof(vid_t));
	j = 0;
    for (k = 0; k < n2; k++) {
	  if (IS_SET(G->_neighbor_v1[i], k)) {
	    right_vertex[j++] = k;  if (j == nright) break;
	  }
    }

	/* Decide if it is maximal */
    if (nright == 1) {
	  nleft = bigraph_degree_v2(G, right_vertex[0]);
	}
	else {
      memcpy(left, G->_neighbor_v2[right_vertex[0]], b2);
      for (k = 1; k < nright; k++)
	    bit_intersect(left, G->_neighbor_v2[right_vertex[k]], b2);
      bit_count_ones(nleft, left, b2);
	}
	
	/* Print out if it is maximal and update profile */
	if (nleft == 1) {
	  nclique[(nright-1)*n1+(nleft-1)]++;
      for (k = 0; k < nright; k++)
	    fprintf(fp, "%s\t", G->_label_v2[right_vertex[k]]);
      fprintf(fp, "\n");
	  fprintf(fp, "%s\n\n", G->_label_v1[i]);
	}
  }

  return;
}
  

/* ------------------------------------------------------------- *
 * Function: biclique_profile_out()                              *
 * ------------------------------------------------------------- */
void biclique_profile_out(FILE *fp, BiGraph *G, num_t *nclique)
{
  unsigned int n1 = G->_num_v1;
  unsigned int n2 = G->_num_v2;
  num_t num, sum=0;
  int ei=0, ej=0;
  int vi=0, vj=0;
  int i, j;
 
  fprintf(fp, "Pheno\tGene\tNumber\n");
  for (i = 1; i <= n2; i++) {
	for (j = 1; j <= n1; j++) {
	  num = nclique[(i-1)*n1+(j-1)];
	  if (num > 0) {
		fprintf(fp, "%d\t%d\t%lu\n", i, j, num);
		sum += num;
		if (i*j > ei*ej) { ei = i; ej = j; }
		if (i+j > vi+vj) { vi = i; vj = j; }
	  }
	}
  }
  
  fprintf(fp, "\n");
  fprintf(fp, "Number of genes          : %d\n", n1);
  fprintf(fp, "Number of phneotype      : %d\n", n2);
  fprintf(fp, "Number of edges          : %d\n", G->_num_edges);
  fprintf(fp, "Number of biclique       : %lu\n", sum);
  fprintf(fp, "Max edge biclique size   : (%d, %d)\n", ei, ej);
  fprintf(fp, "Max vertex biclique size : (%d, %d)\n", vi, vj);
}


/* ------------------------------------------------------------- *
 * Function: biclique_enumerate_v1()                             *
 * ------------------------------------------------------------- */
void biclique_enumerate_v1(FILE *fp, FILE *fp2, BiGraph *G, \
		vid_t *cand, int lcand)
{
  unsigned int n1 = bigraph_num_v1(G);
  unsigned int n2 = bigraph_num_v2(G);
  int b2 = G->_num_bytes_v2;
  int num_ints_v1 = b2 / sizeof(int);
  vid_t candidates[n2];
  unsigned int neighbor[num_ints_v1];
  num_t *nclique;
  int degree, u, i;
  
  /* Malloc memory */
  CACHE = biclique_cache_make(CACHE_SIZE, num_ints_v1);
  nclique = (num_t *) calloc(n1*n2, sizeof(num_t));
  if (!nclique) { perror("malloc nclique\n"); exit(-1); }
  
  /* Find bicliques */
  for (i = 0; i < lcand; i++) {
	u = cand[i];
	degree = G->_degree_v2[u];
	if (degree < MAX(LLEAST, LMIN)) continue;
	memset(candidates, 0, n2*sizeof(vid_t));
	memcpy(neighbor, G->_neighbor_v2[u], b2);
	candidates[0] = u;
	biclique_find_v1(fp, G, nclique, candidates, neighbor, 1, degree);
  }

  if (LLEAST == 1) biclique_find_left(fp, G, nclique);

  /* Print biclique profile */
  biclique_profile_out(fp2, G, nclique);
  biclique_cache_perform_out(stdout, CACHE);

  /* Free memory */
  biclique_cache_free(CACHE);
  free(nclique);
  
  return;
}




/* --------------------------------------------------- *
 *  Biclique Enumerating Version 2
 * --------------------------------------------------- */

void biclique_out_v2(FILE *fp, BiGraph *G, vid_t *right, \
		int nr, vid_t *left, int nl)
{
  int i;
#ifdef PERFORMANCE
  double utime = get_cur_time();
#endif
  for (i = 0; i < nr-1; i++) {
	fprintf(fp, "%s\t", G->_label_v2[right[i]]);
  }
  fprintf(fp, "%s\n", G->_label_v2[right[i]]);
  for (i = 0; i < nl-1; i++) {
	fprintf(fp, "%s\t", G->_label_v1[left[i]]);
  }
  fprintf(fp, "%s\n", G->_label_v1[left[i]]);
  fprintf(fp, "\n");
#ifdef PERFORMANCE
  time_out += get_cur_time() - utime;
#endif
}


void biclique_find_v2(FILE *fp, BiGraph *G, num_t *nclique, \
	vid_t *clique, int nc, vid_t *left, int nl, vid_t *right, int ne, int ce)
{
  unsigned int n1 = G->_num_v1;
  vid_t new_left[nl];
  vid_t new_right[ce];
  vid_t u, v, w, j, k;
  int new_nc, new_nl, new_ne, new_ce;
  int count, is_maximal=1;
#ifdef PERFORMANCE
  double utime;
#endif
#ifdef DEBUG
  vid_t i;
#endif

  while (ne < ce) {
	v = right[ne];
	
#ifdef PERFORMANCE
  node_num++;
#endif

#ifdef DEBUG
  for (i = 0; i < nc; i++) printf(" %s", G->_label_v2[clique[i]]);
  printf("\t|");
  for (i = 0; i < ne; i++) printf(" %s", G->_label_v2[right[i]]);
  printf("\t|");
  for (i = ne; i < ce; i++) printf(" %s", G->_label_v2[right[i]]);
  printf("\n");
  for (i = 0; i < nl; i++) printf(" %s", G->_label_v1[left[i]]);
  printf("\n\n");
#endif

#ifdef PERFORMANCE
  utime = get_cur_time();
#endif

	new_nc = nc;
	clique[new_nc++] = v;
	
	memset(new_left, -1, nl*sizeof(vid_t));
	new_nl = 0;
	for (j = 0; j < nl; j++) {
	  u = left[j];
	  if (bigraph_edge_exists(G, u, v)) new_left[new_nl++] = u;
	}
	
#ifdef PERFORMANCE
  time_expand += get_cur_time() - utime;
  utime = get_cur_time();
#endif

	memset(new_right, -1, ce*sizeof(vid_t));
	new_ne = 0;
	is_maximal = 1;
	for (j = 0; j < ne; j++) {
	  w = right[j];
	  count = 0;
	  for (k = 0; k < new_nl; k++) {
		u = new_left[k];
		if (bigraph_edge_exists(G, u, w)) count++;
	  }
	  if (count == new_nl) { is_maximal = 0; break; }
	  else if (count > 0) new_right[new_ne++] = w;
	}

	if (!is_maximal) { 
#ifdef DEBUG
  for (i = 0; i < new_nc; i++) printf(" %s", G->_label_v2[clique[i]]);
  printf("\t|");
  for (i = 0; i < new_ne; i++) printf(" %s", G->_label_v2[new_right[i]]);
  printf(" AAA %s", G->_label_v2[w]); 
  printf("\t|");
  for (i = ne+1; i < ce; i++) printf(" %s", G->_label_v2[right[i]]);
  printf("\n");
  for (i = 0; i < new_nl; i++) printf(" %s", G->_label_v1[new_left[i]]);
  printf("\n\n");
#endif
      ne++; continue;
	}
	
#ifdef PERFORMANCE
  time_check += get_cur_time() - utime;
  utime = get_cur_time();
#endif

	new_ce = new_ne;
	for (j = ne+1; j < ce; j++) {
	  w = right[j];
	  count = 0;
	  for (k = 0; k < new_nl; k++) {
		u = new_left[k];
		if (bigraph_edge_exists(G, u, w)) count++;
	  }
	  if (count == new_nl) { 
		clique[new_nc++] = w; 
#ifdef DEBUG
  printf("BBB %s\n\n", G->_label_v2[w]);
#endif
	  }
	  else if (count > 0)  { new_right[new_ce++] = w; }
	}
	
#ifdef PERFORMANCE
  time_expand += get_cur_time() - utime;
#endif

	nclique[(new_nc-1)*n1+(new_nl-1)]++;
	if (PRINT) biclique_out_v2(fp, G, clique, new_nc, new_left, new_nl);

	if (new_ne < new_ce) {
	  biclique_find_v2(fp, G, nclique, clique, new_nc, \
		new_left, new_nl, new_right, new_ne, new_ce);
	}
	else {
#ifdef DEBUG
  for (i = 0; i < new_nc; i++) printf(" %s", G->_label_v2[clique[i]]);
  printf("\t|");
  for (i = 0; i < new_ne; i++) printf(" %s", G->_label_v2[new_right[i]]);
  printf("\t|");
  for (i = new_ne; i < new_ce; i++) printf(" %s", G->_label_v2[new_right[i]]);
  printf("\n");
  for (i = 0; i < new_nl; i++) printf(" %s", G->_label_v1[new_left[i]]);
  printf("\n\n");
#endif
   }
	
	ne++;
  }
  
  return;
}

void biclique_enumerate_v2(FILE *fp1, FILE *fp2, BiGraph *G, \
		vid_t *cand, int lcand)
{
  unsigned int n1 = G->_num_v1;
  unsigned int n2 = G->_num_v2;
  num_t *nclique;
  vid_t left[n1], right[n2], clique[n2];
  int nc, nl, ne, ce;
  int count, is_maximal=1;
  vid_t u, v, w, i, j, k;
#ifdef PERFORMANCE
  double utime;
#endif
  
  nclique = (num_t *) calloc(n1*n2, sizeof(num_t));
  if (!nclique) { perror("malloc nclique\n"); exit(-1); }
  
  for (i = 0; i < lcand; i++) {

#ifdef PERFORMANCE
  node_num++;
#endif

	v = cand[i];

#ifdef PERFORMANCE
  utime = get_cur_time();
#endif

	/* Set right vertices in clique */
    memset(clique, -1, n2*sizeof(vid_t));
	nc = 0;
	clique[nc++] = v;

	/* Set neighbors on left */
	memset(left, -1, n1*sizeof(vid_t));
	nl = 0;
	for (u = 0; u < n1; u++) {
	  if (bigraph_edge_exists(G, u, v)) left[nl++] = u;
	}
	
#ifdef PERFORMANCE
  time_expand += get_cur_time() - utime;
  utime = get_cur_time();
#endif
	
	/* Set right vertices in not */
    memset(right, -1, n2*sizeof(vid_t));
	ne = 0;
	is_maximal = 1;
	for (j = 0; j < v; j++) {
	  count = 0;
	  w = j;
	  for (k = 0; k < nl; k++)
		if (bigraph_edge_exists(G, left[k], w)) count++;
	  if (count == nl) { is_maximal = 0; break; }
	  if (count > 0) right[ne++] = w;
	}
	
	if (!is_maximal) { continue; }

#ifdef PERFORMANCE
  time_check += get_cur_time() - utime;
  utime = get_cur_time();
#endif
	
	/* Set right vertices in cand */
	ce = ne;
	for (j = v+1; j < n2; j++) {
	  count = 0;
	  for (k = 0; k < nl; k++)
		if (bigraph_edge_exists(G, left[k], j)) count++;
	  if (count == nl) {
		clique[nc++] = j;
	  }
	  else if (count > 0) right[ce++] = j;
	}

#ifdef PERFORMANCE
  time_expand += get_cur_time() - utime;
#endif

	nclique[(nc-1)*n1+(nl-1)]++;
	if (PRINT) biclique_out_v2(fp1, G, clique, nc, left, nl);
	
	/* Recursively find bicliques */
	if (ne < ce)
	  biclique_find_v2(fp1, G, nclique, clique, nc, left, nl, right, ne, ce);
  }

  biclique_profile_out(fp2, G, nclique);

  free(nclique);

  return;
}


void biclique_enumerate(FILE *fp1, FILE *fp2, BiGraph *G, \
		vid_t *cand, int lcand)
{
  if (VERSION == 1)
	biclique_enumerate_v1(fp1, fp2, G, cand, lcand);
  else if (VERSION == 2)
	biclique_enumerate_v2(fp1, fp2, G, cand, lcand);
}

