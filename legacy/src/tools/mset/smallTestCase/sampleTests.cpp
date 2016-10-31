/*
sampleTests.cpp: try to shrink input size, run as

in script,

do{
./a.out backgroundSmall.txtorig > backgroundSmall.txt
./a.out interestSmall.txtorig > interestSmall.txt
msetCPP (1000*multiple used here) 10000 backgroundSmall.txt interestSmall.txt
}while( p value not in acceptable range)

Created: Fri Oct 28 15:25:35 CDT 2016
*/
#include <iostream>
#include "../WithoutReplacementSampler.h"
#include <fstream>
#include <vector>
#include <cstdlib>
using namespace std;
int main(int argc, char** argv){
    vector<string> genes;
    ifstream input(argv[1]);
    string gene;
    float percent=atof(argv[2]);
    while(input>>gene){
        genes.push_back(gene);
    }
    WithoutReplacementSampler<string> sampler;
    sampler.setSource(&genes);
    vector<string> sampled((long)(genes.size()*percent));
    sampler.sample(sampled);
    for(unsigned int i=0;i<sampled.size();i++){
        cout<<sampled[i]<<endl;
    }
    input.close();



    return 0;
}
