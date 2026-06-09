#ifndef STRINGMISC_H
#define STRINGMISC_H
/**
 * Stringmisc.h
 * Miscellaneous string functions (only one)
 *
 * Daniel Morillo
 * December 16, 2010
 *
**/

#include <string>
#include <vector>

using namespace std;

//C++ tokenizing function from oopweb.com
void Tokenize(const string& str,
              vector<string>& tokens,
              const string& delimiters = " ");

#endif
