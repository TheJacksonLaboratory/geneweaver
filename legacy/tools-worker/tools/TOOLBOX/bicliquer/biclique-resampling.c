// DAG resampling code
// Jeremy Jay - Oct 2008
//
// much of this is taken from Yun Zhang's codes:
//    biclique.c, biclique-driver.c, permutest.pl and bic2dag.pl
// and modified for speed/applicability

#include <math.h>
#include <string.h>
#include "bit.h"
#include "bigraph.h"
#include "utility.h"

int LLEAST, RLEAST;

extern long long node_num;
extern double time_check, time_expand, time_out, time_sort;
extern int SORT_TYPE;

typedef unsigned long num_t;
typedef long double score_type;

num_t sz_bicliques;

// number of bicliques to allocate if allocation fails
#define BACKUP_BICLIQUES 20000

#define NUM_SCORES  2
#define CONDENSATION 0   // aka parsimony (number of nodes)
#define OVERLAP 1        // product of node probabilities

char *SCORE_NAMES[NUM_SCORES] = {
"parsimony",
"overlap",
};

// n choose k
unsigned long combinatorial(int n, int k) {
  int i=0;
  double c=1.0;
  for(i=0; i<k; i++) {
    c*=(double)(n-i)/(double)(k-i);
  }
  if( c >= (unsigned long)(-1) ) return (unsigned long)(-1);
  return c;
}

// calculates the number of possible bicliques
unsigned int comb_bicliques(int n) {
  // c=n+1 so we dont have to check k=n (1) and k=1 (n)
  unsigned int i=0, k=2, c=n+1;
  for(k=2; k<n; k++) {
    c+=combinatorial(n,k);
  }
  return c;
}

//////////
// nearly identical to biclique_find_basic, (minus unused/#ifdef'd code)
//   modified to save list of bicliques instead of outputting
//   removed fp and nclique parameters and added bicliques and num_bicliques parameters
void biclique_find_simple(BiGraph *G, num_t *bicliques, num_t *num_bicliques,
    vid_t *clique, int nc, vid_t *left, int nl, vid_t *right, int ne, int ce)
{
  unsigned int n1 = G->_num_v1;
  unsigned int n2 = G->_num_v2;
  vid_t new_left[nl];
  vid_t new_right[ce];
  vid_t u, v, w, j, k;
  int new_nc, new_nl, new_ne, new_ce;
  int i=0;
  int count, is_maximal=1;

  while (ne < ce) {

    /* Choose one vertex from candidate set */
    v = right[ne];

    /* Set right vertices in clique */
    new_nc = nc;
    clique[new_nc++] = v;

    /* Set neighbors on left */
    memset(new_left, -1, nl*sizeof(vid_t));
    new_nl = 0;
    for (j = 0; j < nl; j++) {
      u = left[j];
      if (bigraph_edge_exists(G, u, v)) new_left[new_nl++] = u;
    }

    /* Set right vertices in not */
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

    /* Stop this branch if it is not maximal */
    if (!is_maximal) { 
      ne++; continue;
    }

    /* Set right vertices in cand */
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
      }
      else if (count > 0)  { 
        new_right[new_ce++] = w;
      }
    }

    /* save the found maximal biclique */
    if (new_nc >= RLEAST && new_nl >= LLEAST) {
      int clique_num = *num_bicliques;
      if( clique_num == sz_bicliques ) 
        { perror("too many bicliques!"); exit(1); }
      *num_bicliques=clique_num+1;

      clique_num=clique_num*(n2+2);
      bicliques[clique_num++] = new_nc; // # phenos
      bicliques[clique_num++] = new_nl; // # genes

      for(i=0; i<new_nc; i++) {
        bicliques[ clique_num + clique[i] ] = 1;
      }
    }

    /* Recursively find bicliques */
    if ((new_ne < new_ce) && (new_nc+(new_ce-new_ne) >= RLEAST)) {
      biclique_find_simple(G, bicliques, num_bicliques, clique, new_nc, new_left, new_nl, new_right, new_ne, new_ce);
    }

    /* Move v to former candidate set */
    ne++;
  }

  return;
}

////////////////////////////////////////////////////////
// calculates various scores and saves to scores ptr (at idx)

void collect_scores(BiGraph *G, num_t *bicliques, num_t num_bicliques, int *npos, int nphenos, int ngenes, score_type *scores, int idx) {
  // counts is used for two different metrics, but same array to save memory
  int *counts = (int *)calloc( (num_bicliques>nphenos?num_bicliques:nphenos), sizeof(int));
  // 1=subset, 2=direct subset(ie edge in DAG)
  char *isSubset = (char *)calloc( num_bicliques*num_bicliques, sizeof(char));
  int bsz = nphenos+2;
  int i,j,k, sz=0;
  int a=0,b=0,c=0;
  unsigned long comb;
  score_type prob;
  double x,y,z;
  //////
  int parsimony=num_bicliques, depth=0, breadth=0;
  score_type combscore=1.0, topcombscore=1.0;

  ////////////////////////////////////////////
  // calculate depth  (num levels with nodes)

  for(i=0; i<num_bicliques; i++) {
    sz=bicliques[i*bsz];
    if( sz!=0 ) counts[sz-1]++;
  }
  
  for(i=0; i<nphenos; i++) {
    if( counts[i]!=0 ) depth++;
    counts[i]=0;
  }

  ////////////////////////////////////////////
  // calculate breadth (num roots)

  for(i=0; i<num_bicliques; i++) {
    a=bicliques[i*bsz];

    for(j=0; j<num_bicliques; j++) {
      if( i==j ) continue;

      b=bicliques[j*bsz];

      for(k=2,c=0; k<(nphenos+2); k++)
        if( bicliques[j*bsz+k]==1 && bicliques[i*bsz+k]==1 ) c++;

      // a = size of biclique i
      // b = size of biclique j
      // c = size of intersection
      if( c==b && a > b ) {
        isSubset[i*num_bicliques + j]=2;

        // j is a subset of i (ie: j is not a root)
        counts[j]=1;
      }
    }
  }
  breadth=0;
  for(i=0; i<num_bicliques; i++) {
    if( counts[i]==0 ) breadth++;
  }

  //////////////////////////////////////////
  // node scores

  // build DAG
  for(i=0; i<num_bicliques; i++) {

    for(j=0; j<num_bicliques; j++) {
      if( i==j ) continue;

      for(k=0; k<num_bicliques; k++) {
        if( k==j || k==i ) continue;
        if( isSubset[i*num_bicliques + k] && isSubset[k*num_bicliques + j] )
          isSubset[i*num_bicliques + j]=1;
      }
    }
  }
  
  combscore=1.0;
  for(i=0; i<num_bicliques; i++) {
    if( bicliques[i*bsz]==1 ) continue; // dont count leaves
    
    a=0; b=0;
    for(j=0; j<num_bicliques; j++) // count genes in direct subsets
      if( isSubset[i*num_bicliques + j]==2 )
        { a++; b+=bicliques[j*bsz + 1]; }

    // remove multi-counted genes
    x = b - ((a-1) * bicliques[i*bsz + 1]);
    y = bicliques[i*bsz + 1];

    prob = (score_type)bicliques[i*bsz] * ( 1.0 / (score_type)combinatorial((int)x,(int)y) );
    if( prob > topcombscore ) topcombscore=prob;

//    printf("%d:  %d * ( 1.0 / (%f choose %f) ) = %f\n", i, bicliques[i*bsz], y,x,y, z );
    combscore*=prob;
  }
/*
  //////////////////////////////////////////
  // calculate node score products
 
  x=-1;
  for(i=0; i<num_bicliques; i++) {
    if( bicliques[i*bsz]==1 ) continue;

    comb = combinatorial(ngenes, bicliques[i*bsz+1]);
    prob = powl( 1.0 / (score_type)comb, bicliques[i*bsz]);
    //prob = (score_type)comb;
    combscore*=prob;

    // largest set, or same as largest with better p-value
    if( bicliques[i*bsz]>x || (bicliques[i*bsz]==x && prob < topcombscore) ) {
      topcombscore=prob;
      x=bicliques[i*bsz];
    }
  }
*/
  //////////////////////////////////////////
//scores[idx*NUM_SCORES + CONDENSATION] = (score_type)parsimony;
  scores[idx*NUM_SCORES + CONDENSATION] = (score_type)parsimony / (score_type)comb_bicliques(nphenos);
//  scores[idx*NUM_SCORES + DEPTH] = (score_type)depth;
//  scores[idx*NUM_SCORES + BREADTH] = (score_type)breadth;
  scores[idx*NUM_SCORES + OVERLAP] = (score_type)combscore;
//  scores[idx*NUM_SCORES + TOPCOMBSCORE] = (score_type)topcombscore;
  
  free(isSubset);
  free(counts);
}

// takes the number of positives per column in npos
// and permutes the bigraph to contain them
void resample(BiGraph *G, int *npos, int ncol, int nrow) {
  int u=0, v=0, curpos=0;
  
  // clear current graph
  G->_num_edges=0;
  memset(G->_degree_v1, 0, nrow * sizeof(unsigned short));
  memset(G->_degree_v2, 0, ncol * sizeof(unsigned short));
  memset(G->_neighbor_v2[0], 0, G->_num_bytes_v2*ncol);
  memset(G->_neighbor_v1[0], 0, G->_num_bytes_v1*nrow);

  /////////////////
  // for each column, fix the number of positives
  for(v=0; v<ncol; v++) {
    // randomly assign positives to rows
    curpos = 0;
    while (curpos < npos[v]) {
      u = random() % nrow;

      while( bigraph_edge_exists(G, u, v) ) u=(u+1)%nrow;
      bigraph_add_edge(G, u, v);
      curpos++;
    }
  }
}
// an example output, with a fairly normal distribution and a major outlier:
//   the outlier just happens to be the "test" point, which is why it is uppercase
// .A............................aaabeimqkyzxtoigdbaa.a................................................
void get_sparkline(score_type *scores, int n, int col, score_type value, score_type min, score_type max) {
  int counts[100], maxcount=0, i, scaled;
  int nbins=n/100;
  score_type binsize = (max-min)/(score_type)100.0;//nbins;
  score_type cur = 0;

  if( binsize<0.0 ) binsize=-binsize;

  for(i=0; i<100; i++) counts[i]=0;

  for(i=0; i<n; i++) {
    cur = scores[i*NUM_SCORES + col]-min;
    cur/=binsize;
    //cur++;
    counts[ (int)cur ]++;
    if( counts[ (int)cur ] > maxcount ) maxcount=counts[(int)cur];
  }
  cur = ((value-min)/binsize)+1;
  printf("%d, ", (int)cur);
  for(i=0; i<100; i++) {
    scaled=(counts[i]*25)/maxcount;
    if( i==(int)cur ) printf("%c", 'A'+scaled );
    else if( counts[i]==0 ) printf("." );
    else printf("%c", 'a'+scaled );
  }
  printf(" (%Lg - %Lg)", min, max);
}

void output_pvalues(score_type *scores, int n) {
  int i=0, k=0;
  score_type v, pval_less, pval_more;
  score_type s_min, s_max;
  int less,more;

  printf("\nscore:\tvalue\tp-value(smaller)\tp-value(larger)\n");
  for(k=0; k<NUM_SCORES; k++) {
    less=more=0;
    v = scores[k];
    //s_min=s_max=scores[NUM_SCORES+k];
    s_min=s_max=v;
    for(i=0; i<=n; i++) {  // start i at 1 to exclude this dag from p-value calc.
      if( scores[i*NUM_SCORES + k] <= v ) less++;
      if( scores[i*NUM_SCORES + k] >= v ) more++;
      
      if( scores[i*NUM_SCORES + k] < s_min ) s_min=scores[i*NUM_SCORES + k];
      if( scores[i*NUM_SCORES + k] > s_max ) s_max=scores[i*NUM_SCORES + k];
      // printf("%s: \t%g\n", SCORE_NAMES[k], scores[i*NUM_SCORES+k]);
    }

    pval_less=(score_type)less/(score_type)i;
    pval_more=(score_type)more/(score_type)i;

    printf("%s:\t%Lg\t%Lg\t%Lg\n  ", SCORE_NAMES[k], v, pval_less, pval_more);
//    printf("%s:\t%Lg\t%Lg  (%Lg) [", SCORE_NAMES[k], v, pval, s_min);
    get_sparkline(scores, n, k, v, s_min, s_max);
    printf( "\n" );
//    printf("] (%Lg)\n",s_max);
  }
}

//////////////////////////////////////
// based on biclique_enumerate
void resampling_biclique(FILE *out, BiGraph *G, int n, int maxtime) {
  double t=0, starttime=get_cur_time();
  int i=0, lp=20, p=0;
  unsigned int n1 = G->_num_v1;
  unsigned int n2 = G->_num_v2;
  num_t num_bicliques;
  num_t *bicliques;
  vid_t left[n1], right[n2], clique[n2];
  vid_t u, v;
  int npos[n2];

  score_type *scores = (score_type *) calloc( (n+1)*NUM_SCORES, sizeof(score_type));
  if (!scores) { perror("malloc scores\n"); exit(-1); }

  /* Initialization */
  sz_bicliques = (n2+2)*comb_bicliques(n2);
  bicliques = (num_t *) calloc( sz_bicliques, sizeof(num_t));
  if (!bicliques) { 
    sz_bicliques = BACKUP_BICLIQUES;
    bicliques = (num_t *) calloc( sz_bicliques, sizeof(num_t));
    if (!bicliques) { 
      perror("malloc bicliques\n");
      exit(-1);
    }
  }
    
  for (u = 0; u < n1; u++) left[u] = u;  // every left vertex is candidate 
  for (v = 0; v < n2; v++) {
    right[v] = v; // every right vertex is candidate
    npos[v] = bigraph_degree_v2( G, v ); // count num positives
  }

  for(i=0; i<=n; i++) {
    if( i%100==1 || (t > 1 && i%10==1) ) { 
      t*=(n-i);
      if( t>maxtime ) {
        int t2=maxtime - (get_cur_time()-starttime);
        if( t2<0 ) t=0;
        printf("cutoff ETA: %5d:%02d\n",((int)t2)/60, ((int)t2) % 60); 
        fflush(stdout); 
      }
      if( t>60 ) {
        printf("full ETA: %5d:%02d\n",((int)t)/60, ((int)t) % 60); 
        fflush(stdout); 
      }
    }
    t = get_cur_time();
    if( t-starttime > maxtime ) { 
      printf("Time limit exceeded at n=%d\n", i);
      n=i; break; 
    }

    memset(clique, -1, n2*sizeof(vid_t));  // initially Clique is empty
    memset(bicliques, 0, sz_bicliques*sizeof(num_t));
    num_bicliques=0;

    // resample G (except first time - to get the true scores in scores[0] )
    if( i!=0 )
      resample(G, npos, n2, n1);

    /* Call the recursive function to find maximal bicliques */
    biclique_find_simple(G, bicliques, &num_bicliques, clique, 0, left, n1, right, 0, n2);

    // score output
    collect_scores(G, bicliques, num_bicliques, npos, n2, n1, scores, i );
    t = get_cur_time()-t;
//    break;
  }
  printf("Completed.\n",((int)t)/60, ((int)t) % 60); 

  output_pvalues( scores, n );
  
  /* Free memory */
  free(bicliques);
  free(scores);
}

//////////////////////////////////////
// based on bigraph_binarymatrix_in
//   simply changes 0/1 to NULL/anything

#define LINE_LENGTH 320000     // ODE can produce some big files

BiGraph * bigraph_odematrix_in(FILE *fp)
{
  BiGraph *G;
  char line[LINE_LENGTH];
  char delims[] = " \t\n";
  char *a = NULL;
  int n1, n2, k1, k2, i, j;

  fgets(line, LINE_LENGTH, fp);
  a = strtok(line, delims);
  n1 = atoi(a);
  a = strtok(NULL, delims);
  n2 = atoi(a);

  G = bigraph_make(n1, n2);

  a = strtok(NULL, delims);
  k2 = 0;
  G->_label_v2[k2++] = strdup(a);
  while ((a = strtok(NULL, delims)) != NULL) {
    G->_label_v2[k2++] = strdup(a);
  }

  fgets(line, LINE_LENGTH, fp); // skip geneset name
  k1 = 0;
  while (fgets(line, LINE_LENGTH, fp) != NULL) {
    a = strtok(line, delims);
    G->_label_v1[k1] = strdup(a);
    strtok(NULL, delims); // skip gene symbol
    i = 0;
    while ((a = strtok(NULL, delims)) != NULL) {
//      j = atoi(a);
//      if (j==1) { bigraph_add_edge(G,k1,i); }
      // NULL = no edge
      if (a[0]=='1') { bigraph_add_edge(G,k1,i); }
      i++;
    }
    k1++;
  }

//  if (k1 != n1) 
//    fprintf(stderr, "binarymatrix_in: # left vertices incorret %d!=%d\n", k1, n1);
//  if (k2 != n2) 
//    fprintf(stderr, "binarymatrix_in: # right vertices incorret %d!=%d\n", k2, n2);

  return G;
}

//////////////////////////////////////

int main(int argc, char  **argv)
{
  // defaults, n=5000, limit 1 minute
  int n=5000, l=1;
  int i;
  BiGraph *G;
  FILE *fp;

  LLEAST = 1;
  RLEAST = 1;

  if( argc==1 ) { fprintf(stderr, "USAGE: %s input.odemat [-n###] [-l###]\n", argv[0]); return 1; }
  for(i=2; i<argc; i++) {
    if( argv[i][1]=='n' ) n = atoi(argv[i]+2);
    // give a time limit
    if( argv[i][1]=='l' ) l = atoi(argv[i]+2);
  }
  l*=60;
  printf("n=%d\nlimit=%d\n", n, l);

  fp = fopen(argv[1], "r");
  G = bigraph_odematrix_in(fp);
  resampling_biclique(stdout, G, n, l);
  bigraph_free(G);

  fclose(fp);

  return 0;
}

