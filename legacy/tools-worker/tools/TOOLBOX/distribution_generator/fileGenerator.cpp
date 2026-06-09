/*
	Filename: 		homology.cpp
	Author: 		Matthew Santiago
	Description:	Program to be executed periodically (for updates) to populate a file with 
					gene homology information.
					The file will have the following format to be read in as a map.

					ode_gene_id hom_id

	Date Modified:
		10/5/2015:
			File Created

*/

#include <iostream>
#include <pqxx/pqxx>
#include <string>
#include <ctime>
#include <fstream>
#include <vector>
#include <math.h>
#include <algorithm>
#include <cstring>


using namespace std;
using namespace pqxx;

int homologyFileUpdate() {
	const char *sql;
	ofstream myFile("/var/www/html/dev-geneweaver/tools/cpp_tools/");
	if(!myFile.is_open()) {
		cerr << "Unable to open file: homology.dat" << endl;
		return -1;
	}

	try{
		connection C("dbname=geneweaver user=odeadmin password=odeadmin \
      	hostaddr=127.0.0.1 port=5432");
      	if(C.is_open()) {

      	} else {
      		cerr << "Cannot open database" << endl;
      		return -1;
      	}

      	sql = "SELECT ode_gene_id, hom_id FROM homology";
      	nontransaction N(C);
      	result R( N.exec( sql ));
      	
      	for(result::const_iterator c = R.begin(); c != R.end(); ++c) {
      		myFile << c[0].as<int>() << " " << c[1].as<int>() << endl;
      	}

      	C.disconnect();
	}catch (const exception &e) {
		cerr << e.what() << std::endl;
      	return 1;
	}

	myFile.close();
	return 0;
}

int geneFileUpdate() {
	const char *sql;
	ofstream myFile("/var/www/html/dev-geneweaver/tools/cpp_tools/genes.dat");
	if(!myFile.is_open()) {
		cerr << "Unable to open file: genes.dat" << endl;
		return -1;
	}

	try{
		connection C("dbname=geneweaver user=odeadmin password=odeadmin \
      	hostaddr=127.0.0.1 port=5432");
      	if(C.is_open()) {

      	} else {
      		cerr << "Cannot open database" << endl;
      		return -1;
      	}

      	sql = "select gv.ode_gene_id from geneset_value as gv, geneset as gs where gs.gs_id = gv.gs_id and gs.gs_status not like \'de%\'";
      	nontransaction N(C);
      	result R( N.exec( sql ));
      	
      	for(result::const_iterator c = R.begin(); c != R.end(); ++c) {
      		myFile << c[0].as<int>() << endl;;
      	}

      	C.disconnect();
	}catch (const exception &e) {
		cerr << e.what() << std::endl;
      	return 1;
	}

	myFile.close();
	return 0;
}

int main(int argc, char* argv[]) {
	if(strcmp(argv[1], "-h") == 0) {
		homologyFileUpdate();
	} else if(strcmp(argv[1], "-g") == 0) {
		geneFileUpdate();
	} else {
		cerr << "Invalid use of file:\n";
		cerr << "\t./generate.out -h/-g\n";
		cerr << "\tOptions:\n";
		cerr << "\t\t-h -> update homology.dat file\n";
		cerr << "\t\t-g -> update genes.dat file\n";
	}
	return 0;
}
