/*
testSample.cpp: ...
Created: Tue Sep 20 18:04:36 CDT 2016
*/
#include <iostream>
#include "../WithoutReplacementSampler.h"
#include "printVec.h"
using namespace std;


int main(int argc, char** argv){
    vector<int> sampleFrom{23,45,4,2,65,2,6,3,4,2,6,7,8,9,3,2,3,5,7,2,45};
    vector<int> sampleTo(7);
    WithoutReplacementSampler<int> sampler;
    cout<<sampleFrom<<endl;
    sampler.setSource(&sampleFrom);

    for(int i=0;i<10;i++){
        sampler.sample(sampleTo);
        cout<<sampleTo<<endl;
        cout<<endl;
        cout<<endl;
    }

    return 0;
}
