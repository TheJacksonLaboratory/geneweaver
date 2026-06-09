#ifndef SETMISC_H
#define SETMISC_H
/**
 * Setmisc.h
 * Some templates for performing set operations.
 *
 * Daniel Morillo
 * December 16, 2010
 *
**/


#include <set>
#include <map>

using namespace std;


/**
 * is_subset
 *
 * Check if set A is a subset of set B.
 */
template<class T>
inline bool is_subset(set<T>& a,set<T>& b){
    typename set<T>::iterator i = a.begin();
    typename set<T>::iterator j = b.begin();
    int count=0;
    while(i!=a.end() && j!=b.end()){
        if(*i<*j){
            return false;
        }else if(*i>*j){
            j++;
        }else{
            count++;
            i++;
            j++;
        }
    }
    if(i!=a.end())
        return false;
    if(count)
        return true;
    return false;
}

/**
 * is_propersubset
 * 
 * Check if A is a proper subset of B. (doesn't include empty/full subset)
 */
template<class T>
inline bool is_propersubset(set<T>& a,set<T>& b){
    if(a.size()==b.size())return false;
    typename set<T>::iterator i = a.begin();
    typename set<T>::iterator j = b.begin();
    int count=0;
    while(i!=a.end() && j!=b.end()){
        if(*i<*j){
            return false;
        }else if(*i>*j){
            j++;
        }else{
            count++;
            i++;
            j++;
        }
    }
    if(i!=a.end())
        return false;
    if(count)
        return true;
    return false;
}

/**
 * is_disjoint
 * 
 * Check for an empty intersection between two sets.
 */
template<class T>
inline bool is_disjoint(set<T>& a,set<T>& b){
    typename set<T>::iterator i = a.begin();
    typename set<T>::iterator j = b.begin();
    while(i!=a.end() && j!=b.end()){
        if(*i<*j){
            i++;
        }else if(*i>*j){
            j++;
        }else{
            return false;
        }
    }
    return true;
}

/**
 * insertIntoGroup
 * 
 * Inserts an item into a key->set<item> mapping and creates a new set if the key didn't exist.
 */
template<class K, class T>
inline void insertIntoGroup(T& v,K& a,map<K,set<T> >& b){
    typename map<K,set<T> >::iterator iter = b.find(a);
    if(iter==b.end()){
        set<T> dlsettemp;
        dlsettemp.insert(v);
        b.insert(pair<K,set<T> >(a,dlsettemp));
    }else{
        iter->second.insert(v);
    }
}

/**
 * is_equalset
 * 
 * Check for equality between sets.
 */
template<class T>
inline bool is_equalset(set<T>& a,set<T>& b){
    typename set<T>::iterator i = a.begin();
    typename set<T>::iterator j = b.begin();
    int count = 0;
    while(i!=a.end() && j!=b.end()){
        if(*i<*j){
            return false;
        }else if(*i>*j){
            return false;
        }else{
            i++;
            j++;
        }
    }
    if(i!=a.end()||j!=b.end())return false;
    return true;
}

/**
 * intersect (3 arg)
 * 
 * Intersects A and B and deposits results into C.
 * Saves trouble with copy constructing large sets.
 */
template<class T>
inline void intersect(set<T>& a,set<T>& b,set<T>& c){
    typename set<T>::iterator i = a.begin();
    typename set<T>::iterator j = b.begin();
    while(i!=a.end() && j!=b.end()){
        if(*i<*j){
            i++;
        }else if(*i>*j){
            j++;
        }else{
            c.insert(*i);
            i++;
            j++;
        }
    }
}


#endif
