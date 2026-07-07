/**
 * @author Carter Ratley & Tina Wang
 * This file is an executable for the DBSCAN algorithm
 * Date Created: 9/22/16
 * Date Last Modified: 11/11/16
 */
#include <iostream>
#include <stdlib.h>
#include <string.h>
#include "dbscan.h"
#include "json.hpp"

using namespace std;
using json = nlohmann::json;

// Parses the parameters
vector<vector<long> > parseParameters(char**);
vector<vector<long> > parseData(char*&);

// helper functions to parse data
bool isNumericChar(char&);
long myAtol(char*);

// Used for testing, to be deleted
void initValues(vector<vector<long> > &);
void print2DVector(vector<vector<long> > const &);
json print2DVectorJSON(vector<vector<long> > const &);

const long NUM_PARAMETERS = 4; // The valid number of parameters

// Index values for each of the parameters
const int DATA_INDEX = 1;
const int EPSILON_INDEX = 2;
const int MIN_POINTS_INDEX = 3;

const char* ASTERISK = "*";

long epsilon; // Epsilon value
long minPts; // min points value
long numberOfGenes; // The number of genes

int main(int argc, char** argv)
{
    // Checks for valid number of parameters
    if(argc != NUM_PARAMETERS){
        cerr << "Usage: " << argv[0] << " (Data) (Epsilon) (minPts)" << endl;
        exit(1);
    }

    // Parses the parameters
    vector<vector<long> > geneToSet = parseParameters(argv);

    // Runs the DBSCAN algorithm
    vector<vector<long> > clusters = DBSCAN::findClustersDBSCAN(geneToSet, epsilon, minPts, numberOfGenes);

    // Prints the results to standard out
    if(clusters.size() == 0){
        // NO CLUSTERS FOUND
        cout << "@";
    }
    else{
        cout << print2DVectorJSON(clusters);
    }
    cout << endl;

    return 0;
}

/**
 * Parses all parameters
 * @param argv the list of command line parameters
 * @return the 2D vector representing the connections between genes and gene sets
 */
 vector<vector<long> > parseParameters(char** argv){
    // Converts the epsilon and min Points values to ints
    epsilon = myAtol(argv[EPSILON_INDEX]);
    minPts = myAtol(argv[MIN_POINTS_INDEX]);

    // Checks to see if minPts is valid
    if(epsilon < 1){
        cerr << "Epsilon is invalid" << endl;
        exit(1);
    }

    // Checks to see if minPts is valid
    if(minPts < 1){
        cerr << "Min Points is invalid" << endl;
        exit(1);
    }

    // Initializes gene to gene set graph
    vector<vector<long> > geneToSet = parseData(argv[DATA_INDEX]);

    return geneToSet;
 }

/**
 * parses the data passed in and creates the gene to set graph
 * @param data the data to parse
 * @return a 2D vector representing the connections between genes and gene sets
 */
vector<vector<long> > parseData(char*& data){
    long index = 0; // The current index we are at

    char* numGenesChar; // Array that holds number of genes as character

    numGenesChar = strtok((char*)(data + index), ASTERISK); // Gets the number of genes as a char*

    long numGenes = myAtol(numGenesChar); // Converts genes to long

    // Makes sure there are valid number of genes
    if(numGenes < 0){
        cerr <<  "Number of genes is invalid (must be greater than 0)" << endl;
        exit(1);
    }

    // Increments the index (plus one accounts for the delimiter
    index += strlen(numGenesChar) + 1;

    // Sets the global variable number of genes to the number of genes
    numberOfGenes = numGenes;

    char* numGeneSetsChar; // Array that holds number of genes as character

    numGeneSetsChar = strtok((char*)(data + index), ASTERISK); // Gets the number of genes as a char*

    long numGeneSets = myAtol(numGeneSetsChar); // Converts genes to long

    // Makes sure there are valid number of genes
    if(numGeneSets < 0){
        cerr <<  "Number of gene sets is invalid (must be greater than 0)" << endl;
        exit(1);
    }

    // Increments the index (plus one accounts for the delimiter
    index += strlen(numGeneSetsChar) + 1;

    char* numConnectionsChar; // Array that holds number of genes as character

    numConnectionsChar = strtok((char*)(data + index), ASTERISK); // Gets the number of genes as a char*

    long numConnections = myAtol(numConnectionsChar); // Converts genes to long

    // Checks for valid number of connections
    if(numConnections < 0){
        cerr << "There must be at least 1 connection between gene and gene set" << endl;
        exit(1);
    }

    // Increments the index (plus one accounts for the delimiter
    index += strlen(numConnectionsChar) + 1;

    // Vector holding the gene sets with the genes in each gene set
    vector<vector<long> > geneToSet(numGeneSets, vector<long>());


    char* geneChar; // The value of the gene as a char*
    char* geneSetChar; // The value of the gene set as a char*
    long gene; // The gene value
    long geneSet; // The gene set value

    // Loops through the list of connections
    for(int i = 0; i < numConnections; i++){

        // Grabs the gene and checks for validity
        if((geneChar = strtok((char*)(data + index), ASTERISK)) == NULL){
            cerr << "Input file format is invalid" << endl;
            exit(1);
        }

        // Converts the gene character array to a long and checks for validity
        gene = myAtol(geneChar);
        if(gene < 0 || gene >= numGenes){
            cerr << "Gene read in is invalid: Must be greater than 0 and less than " << numGenes << endl;
            exit(1);
        }

        // Increments the index (plus 1 accounts for the delimiter)
        index += strlen(geneChar) + 1;

        // Grabs the gene sets and checks for validity
        if((geneSetChar = strtok((char*)(data + index), ASTERISK)) == NULL){
            cerr << "Input file format is invalid: Must be greater than 0 and less than " << numGeneSets << endl;
            exit(1);
        }

        // Converts the character to a long and checks for validity
        geneSet = myAtol(geneSetChar);
        if(geneSet < 0 || geneSet >= numGenes){
            cerr << "Gene read in is invalid" << endl;
            exit(1);
        }

        // Increments the index (plus 1 accounts for the delimiter)
        index += strlen(geneSetChar) + 1;

        // Set value in vector
        geneToSet[geneSet].push_back(gene);

    }

    return geneToSet;
}

/**
 * Checks to see if a character is a number
 * @param x the character to check
 * @return whether or not the character is numeric
 */
bool isNumericChar(char& x)
{
    return (x >= '0' && x <= '9');
}

/**
 * Converts a character array to a long
 * @param str the character array to check
 * @return the character array converted to a long or -1 if there is an error
 */
long myAtol(char* str)
{
    // If it is null, return error
    if (str == NULL)
       return -1;

    long res = 0;  // The result

    // Iterate through all digits of input string and update result
    for (int i = 0; str[i] != '\0'; i++)
    {
        // If the character is non-numeric, there is an error
        if (!isNumericChar(str[i])){
            return -1;
        }

        // Adds the character to the result
        res = res * 10 + str[i] - '0';
    }

    return res;
}

/**
 * Converts a 2D vector to a JSON
 * @param geneToSet
 */
json print2DVectorJSON(vector<vector<long> > const &vect){
    json clusters(vect);
    return clusters;
}