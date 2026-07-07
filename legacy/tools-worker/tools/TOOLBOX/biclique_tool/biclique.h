/* Enumerate biclique in bipartite graph
 * Author: Yun Zhang
 * Date: September 2006
 */

#ifndef __BICLIQUE_H
#define __BICLIQUE_H


typedef unsigned short vid_t;


/* ---------------------------------------- *
 * Cache for deciding the maximality        *
 * ---------------------------------------- */
typedef struct cache_entry_t {
  unsigned int *_key;
  unsigned int _value;
  unsigned long long _timestamp;
} Entry;

typedef struct cache_t {
  int _cache_size;  /* number of entries in cache */
  int _key_size;    /* number of chars in key */
  unsigned long long _timestamp;
  unsigned int _num_hit;
  Entry *_entry;
} Cache;

#define biclique_cache_size(c)     (c->_cache_size)
#define biclique_cache_keysize(c)  (c->_key_size)
#define biclique_cache_key(c, i)   (c->_entry[i]._key)
#define biclique_cache_value(c, i) (c->_entry[i]._value)
#define biclique_cache_cur_timestamp(c) (c->_timestamp)
#define biclique_cache_hit(c)      (c->_num_hit)
#define biclique_cache_timestamp(c, i)  (c->_entry[i]._timestamp)

Cache *biclique_cache_make(int size, int key_size);
void biclique_cache_free(Cache *C);
void biclique_cache_add_entry(Cache *C, void *key, int value);


/* ---------------------------------------- *
 * Biclique Enumeration Functions           *
 * ---------------------------------------- */
void biclique_enumerate(FILE *fp, FILE *fp2, BiGraph *G, vid_t *, int);

#endif

