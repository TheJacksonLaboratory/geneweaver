/*
   Name        : RandomGeneSetGenerator.cpp
   Author      : Matthew 
   Co-Author   : Felix
   Version     : 2.0
   Copyright   : Geneweaver
   Description : Create similarity curve from user input sample sizes. This is done by updating the database
                  of geneweaver. P-values of observed jaccard values are looked up from the table.

   Date Modified:
      as of 9/22/2015:
         File Created
         Null Distribution Generation
         Dynamic Programming

      9/22/2015:
         Step down function of sample size
         Auto prepopulation of database for all distinct combinations up to N, M sizes
            - Dynamic programming solution

      9/23/2015:
         p_value insertion with each row into database
         p_value calculation

      9/24/2015:
         UDPATE: sort jaccard_similarity in each distribution in ascending order to get true p_value
            -quickSort/insertionSort hybrid

      9/28/2015:
         UPDATE: correct distribution sorting

      10/3/2015:
         p_value updated to account for homology
         argv[3] (1/0) parameter to indicate prepopulation or look-up functionality
         homology table file
         output of file to account for subprocess integration (possibly just p-value lookup) 

      10/5/2015:
         UPDATED USAGE OF PROGRAM:
            ./a.out set_size1 set_size2 homology=True/False prepopulation=True/False

      10/6/2015:
         CONTINUED UPDATE:
            homology setting integrated into all functions
            homology map created
            file IO integrated
         TODO:
            rewrite homology map as a hash_map to improve look up time.
*/

#include <iostream>
#include <pqxx/pqxx>
#include <string>
#include <ctime>
#include <fstream>
#include <vector>
#include <math.h>
#include <algorithm>
#include <unordered_map>
#include <cstring>
#include "db_conn.h"

using namespace std;
using namespace pqxx;

#define J_FREQ pair<double, long int>
#define HOMO_PAIR pair<int, int>          // <gene_id, homology_id>

string CreateInsertQuery(long int size1, long int size2, float jaccard_coeff, long int freq, double p_value, bool homology){
   string query = "";
   if(homology) {
      query = "INSERT INTO jaccard_distribution_results(set_size1, set_size2, jaccard_coef, frequency, p_value, homology) select " 
         + to_string(size1) + ", " + to_string(size2) + ", " + to_string(jaccard_coeff) + ", " + to_string(freq) + ", " + to_string(p_value) + ", TRUE;";
   } else {
      query = "INSERT INTO jaccard_distribution_results(set_size1, set_size2, jaccard_coef, frequency, p_value, homology) select " 
         + to_string(size1) + ", " + to_string(size2) + ", " + to_string(jaccard_coeff) + ", " + to_string(freq) + ", " + to_string(p_value) + " FALSE;";
   }
   return query;

}



string CheckIfExists(long int size1, long int size2, bool homology){

   string query = "";
   if(homology) {
      query = "SELECT * FROM jaccard_distribution_results where set_size1 = " + to_string(size1) + " and set_size2 = " + to_string(size2) + " and homology = TRUE;";
   } else {
      query = "SELECT * FROM jaccard_distribution_results where set_size1 = " + to_string(size1) + " and set_size2 = " + to_string(size2) + " and homology = FALSE;";
   }
   
   return query;
}

bool findGene(vector<int> m, int element) {
   for(int i = 0; i < m.size(); i++) {
      if(element == m[i]) {
         return true;
      }
   }
   return false;
}

/*
   function: Intersection
   description: Given two sets, find total count of similar genes (based on homology setting)
               between the two sets. Homology counts homologous genes to be similar and
               count towards intersection.

   Author: Matthew Santiago
*/
int Intersection(int *pseudo_set1, long N, int *pseudo_set2, long M, unordered_map<int, int> &homology_map, bool homology=false) {
   int intersection = 0;

   if(homology) {
      // TODO: utilize homology map of some sort.
      int homoID1, homoID2;
      for(int n = 0; n < N; n++) {
      homoID1 = homology_map[pseudo_set1[n]];
         //cout << "gene_id: " << pseudo_set1[n] << " hom_id: " << homoID1 << endl;
         for(int m = 0; m < M; m++) {
            homoID2 = homology_map[pseudo_set2[m]];
            //cout << "\tgene_id: " << pseudo_set2[m] << " hom_id: " << homoID2 << endl;
            if(homoID1 > 0 && homoID2 > 0 && homoID1 == homoID2) {
               intersection++;
               continue;
            } else {
               if(pseudo_set1[n] == pseudo_set2[m]) {
                  intersection++;
                  continue;
               }
            }
         }
      }
   } else {
      //cout << "Homology is false" << endl;
      for(int n = 0; n < N; n++) {
         for(int m = 0; m < M; m++) {
            //printf("pseudo1 = %d\tpseudo2 = %d\n", pseudo_set1[n], psuedo_set2[m]);
            if(pseudo_set1[n] == pseudo_set2[m]) {
               intersection++;
               continue;
            }
         }
      }
   }

   return intersection;
}

int Intersection2(int *pseudo_set1, long N, int *pseudo_set2, long M) {
   int intersection = 0;
   for(int n = 0; n < N; n++) {
      for(int m = 0; m < M; m++) {
         //printf("pseudo1 = %d\tpseudo2 = %d\n", pseudo_set1[n], psuedo_set2[m]);
         if(pseudo_set1[n] == pseudo_set2[m]) {
            intersection++;
            continue;
         }
      }
   }
   return intersection;
}

int stepDownOrder(long N, long M) {
   return floor((N+M)/100);
}
/*
   function: calculateP_Value
   description: given a null distribution curve, a set of pairs (J_VALUE, FREQ), give the p_value
                  of each pair. A p_value in our case is the same as the relative frequency.
                  This is because these pairs are calculated from randomly generated sets.

   Author: Matthew Santiago
*/
double *calculateP_Value(vector<J_FREQ> null_distribution) {
   double *p_values = new double[null_distribution.size()];
   int sample_size = 0;

   // Obtain sample size of distribution curve
   for(int i = 0; i < null_distribution.size(); i++) {
      sample_size += null_distribution[i].second;
   }

   for(int i = 0; i < null_distribution.size(); i++) {
      int total = 0;
      for(int k = i; k < null_distribution.size(); k++) {
         total += null_distribution[k].second;
      }
      p_values[i] = (double)(total+1)/(sample_size+1); // p = (r+1)/(n+1)
   }
   return p_values;
}

void insertionSort(vector<J_FREQ> &arr) {
   for(int i = 1; i < arr.size(); i++) {
      J_FREQ x = arr[i];
      int j = i;
      while(j > 0 && arr[j-1].first > x.first) {
         arr[j] = arr[j-1];
         j--;
      }
      arr[j] = x;
   }
}

vector<J_FREQ> generateSimilarityCurve(long N, long M, int *database, long db_size, unordered_map<int, int> homology_map, bool homology=false) {
   clock_t start = clock();
   int SAMPLE_SIZE = 10000;
   /*
   if( stepDownOrder(N, M) > 0 ) {
      for(int i = stepDownOrder(N, M); i > 0; i--) {
         SAMPLE_SIZE *= 0.95;
      }
   }
   */

   vector<J_FREQ> null_distribution;               // list containing jaccard_coefficients and their frequency
   int *pseudo_set1 = new int[N];                  // Pseudoset 1
   int *pseudo_set2 = new int[M];                  // Pseudoset 2
   srand (time(NULL));                             // seed generation
   int multiplier = 1;
   //printf("\nN:%ld\tM:%ld\n", N, M );

   // Random generation of gene sets
   for(long int sample_size = 0; sample_size < SAMPLE_SIZE; sample_size++) {
      //cout << "sample_size: " << sample_size + 1 << endl;
      for(int n = 0; n < N; n++) {
         pseudo_set1[n] = database[rand() % db_size];
      }

      for(int m = 0; m < M; m++) {
         pseudo_set2[m] = database[rand() % db_size];  
      }

      int intersection = Intersection(pseudo_set1, N, pseudo_set2, M, homology_map, homology);
      //int intersection = Intersection2(pseudo_set1, N, pseudo_set2, M);
      double jaccard = (double)intersection/(N + M + intersection);
      bool contains_jaccard = false;
      int k;
      for(k = 0; k < null_distribution.size(); k++) {
         if(null_distribution[k].first == jaccard) {
            contains_jaccard = true;
            break;
         }
      }
      if(contains_jaccard) {
         null_distribution[k].second++;
      } else {
         J_FREQ j_pair(jaccard, 1);
         null_distribution.push_back(j_pair);
      }

      
      if(sample_size%(int)(SAMPLE_SIZE*0.05) == (int)floor((SAMPLE_SIZE*0.05)-1)) {
         printf("%d%% complete\n", 5*multiplier++);
      }
      
   }
   clock_t end = clock();
   double time = (double) (end-start) / CLOCKS_PER_SEC;
   cout << "Time elapsed: " << time << " seconds" << endl;
   delete pseudo_set1;
   delete pseudo_set2;
   return null_distribution;
}

int main(int argc, char* argv[]) {
   
   const char * sql;    // SQL query holder
   const char * sqlTwo;
   const char * checksql;
   const char * getResult;
   const char TRUE[] = "True";
   const char FALSE[] = "False";
   bool homologySetting;
   bool prepopulationMode;

   if(argc < 5) {
      cerr << "need more arguments\n";
      cerr << "Example use:\n";
      cerr << "\ta.out (set_size1) (set_size2) (homology=True/False) (prepopulation=True/False)\n";
      return -1;
   }

   if(strcmp(argv[3], TRUE) == 0) {
      homologySetting = true;
      //cout << "HOMOLOGY IS TWUE!" << endl;
   } else if(strcmp(argv[3], FALSE) == 0) {
      homologySetting = false;
      //cout << "HOMOLOGY IS FALSE!" << endl;
   } else {
      cerr << "Invalid use of homology setting:" << endl;
      cerr << "\tExample use:\n";
      cerr << "\t\ta.out (set_size1) (set_size2) (homology=True/False) (prepopulation=True/False)\n";
      return -1;
   }

   if(strcmp(argv[4], TRUE) == 0) {
      prepopulationMode = true;
      //cout << "PREPOP IS TWUE!" << endl;
   } else if(strcmp(argv[4], FALSE) == 0) {
      prepopulationMode = false;
      //cout << "PREPOP IS FALSE!" << endl;
   } else {
      cerr << "Invalid use of prepopulation setting:" << endl;
      cerr << "\tExample use:\n";
      cerr << "\t\ta.out (set_size1) (set_size2) (homology=True/False) (prepopulation=True/False)\n";
      return -1;
   }

   try{
      connection C(gw_conn_string());
      if (C.is_open()) {
         //cout << "Opened database successfully: " << C.dbname() << endl;

         } else {
            cout << "Can't open database" << endl;
            return 1;
         }

         // Populate genes bucket based on genes.dat file (populated by fileGenerator.cpp)
         ifstream myFile;
         myFile.open("genes.dat");
         if(!myFile) {
            cerr << "genes.dat failed to open." << endl;
            return -1;
         }
         int lineCount = count(istreambuf_iterator<char>(myFile),
                               istreambuf_iterator<char>(), '\n');
         myFile.clear();
         myFile.seekg(0, ios::beg);
         int *gene_ids = new int[lineCount];
         long int i = 0;
         int currentElement0 = -1;
         while(myFile >> currentElement0){
            gene_ids[i++] = currentElement0;
         }
         myFile.close();


         myFile.open("homology.dat");
         if(!myFile) {
            cerr << "homology.dat failed to open." << endl;
            return -1;
         }
         unordered_map<int, int> homology_map;
         int currentElement1, currentElement2;
         while(myFile >> currentElement1 >> currentElement2) {
            homology_map.insert(make_pair(currentElement1, currentElement2));
         }
         myFile.close();

         nontransaction N(C);    // Nontransaction object to handle queries to the database

         if(prepopulationMode) {
            long s1 = atol(argv[1]);
            long s2 = s1;
            while(s1 <= atol(argv[2])) {

               checksql = CheckIfExists(s1, s2, homologySetting).c_str();
               result P( N.exec( checksql ));

               if(P.size() == 0){

                  /* Allocate memory for null distribution */
                  vector<J_FREQ> null_distribution = generateSimilarityCurve(s1, s2, gene_ids, lineCount, homology_map, homologySetting);
                  insertionSort(null_distribution);
                  double *p_values = calculateP_Value(null_distribution);
                  cout << "set size 1: " << s1 << "\tset size 2: " << s2 << endl;
                  for(int k = 0; k < null_distribution.size(); k++) {
                     if(atol(argv[1]) > atol(argv[2])){
                        swap(argv[1],argv[2]);
                     }
                     sqlTwo = CreateInsertQuery(s1, s2, null_distribution[k].first, null_distribution[k].second, p_values[k], homologySetting).c_str();
                     N.exec( sqlTwo );
                     printf("\tJaccard_Coefficient: %f\tFrequency: %ld\tP_Value: %f\n", null_distribution[k].first, null_distribution[k].second, p_values[k]);
                  }
                  delete p_values;
               }
               else{
                  for (result::const_iterator c = P.begin(); c != P.end(); ++c) {
                     //printf("set size 1: %ld\tset size 2: %ld\tjaccard_coefficient: %f\tfrequency: %ld\tsample size: %ld", c[0].as<long>, c[1].as<long>, c[2].as<double>, c[3].as<long>, c[4].as<long>);
                     cout << "\nJaccard_Coefficient: " << c[3].as<double>() << "\tFrequency: " << c[4].as<long>() << "\tP_Value: " << c[5].as<double>() << endl;
                  }
                  cout << endl;
                     
               }

               if(s2++ == atol(argv[2])){
                  s2 = ++s1;
               }
            }
         } else {
            long s1 = atol(argv[1]);
            long s2 = atol(argv[2]);
            checksql = CheckIfExists(s1, s2, homologySetting).c_str();
            result P( N.exec( checksql ));

            if(P.size() == 0 || true){

               /* Allocate memory for null distribution */
               vector<J_FREQ> null_distribution = generateSimilarityCurve(s1, s2, gene_ids, lineCount, homology_map, homologySetting);
               insertionSort(null_distribution);
               double *p_values = calculateP_Value(null_distribution);
               cout << "set size 1: " << s1 << "\tset size 2: " << s2 << endl;
               for(int k = 0; k < null_distribution.size(); k++) {
                  if(atol(argv[1]) > atol(argv[2])){
                     swap(argv[1],argv[2]);
                  }
                  sqlTwo = CreateInsertQuery(s1, s2, null_distribution[k].first, null_distribution[k].second, p_values[k], homologySetting).c_str();
                  N.exec( sqlTwo );
                  printf("\tJaccard_Coefficient: %f\tFrequency: %ld\tP_Value: %f\n", null_distribution[k].first, null_distribution[k].second, p_values[k]);
               }
               delete p_values;
            }
            else{
               for (result::const_iterator c = P.begin(); c != P.end(); ++c) {
                  //printf("set size 1: %ld\tset size 2: %ld\tjaccard_coefficient: %f\tfrequency: %ld\tsample size: %ld", c[0].as<long>, c[1].as<long>, c[2].as<double>, c[3].as<long>, c[4].as<long>);
                  cout << "\nJaccard_Coefficient: " << c[3].as<double>() << "\tFrequency: " << c[4].as<long>() << "\tP_Value: " << c[5].as<double>() << endl;
               }
               cout << endl;
                  
            }
         }

         delete gene_ids;
         cout << "Operation done successfully" << endl;
         C.disconnect ();

   }catch (const std::exception &e){
      cerr << e.what() << std::endl;
      return 1;
   }
   return 0;
}
