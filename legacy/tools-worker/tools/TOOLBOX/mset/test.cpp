#include <iostream>
#include <stdlib.h>
#include <fstream>

using namespace std;

const int MIN_NUM_PARAMS = 4;

int main(int argc, char** argv){
	ofstream myfile;
	myfile.open("results.txt");
	if(argc < MIN_NUM_PARAMS){
		myfile << "Usage: " << argv[0] << " (Background) (Top Genes) "
		       << "(Data)+ (NumberofSamples)" 
		       << endl;
	}
	else{
		myfile << argv[1] << endl;
	}
	myfile.close();
	cout << "HELLO WORLD" << endl;
	return 0;

}


