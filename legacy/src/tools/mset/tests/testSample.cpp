/*
testSample.cpp: ...
Created: Tue Sep 20 18:04:36 CDT 2016
*/
#include <iostream>
#include <vector>
#include <cstdlib>
#include <ctime>
#include <algorithm>
using namespace std;

//without replacement
template<typename T>
void sample(vector<T>& sampleInto,vector<T>& from,vector<unsigned long>& ndxs){
    random_shuffle(ndxs.begin(),ndxs.end());
    for(unsigned long i=0;i<sampleInto.size();i++){
        sampleInto[i]=from[ndxs[i]];//copy the random element
    }
}
template<typename T>
void printVec(vector<T>& v){
    for(unsigned int i=0;i<v.size();i++){
        cout<<" "<<v[i];
    }
    cout<<endl;
}

int main(int argc, char** argv){
    srand(time(0));
    vector<int> sampleFrom{23,45,4,2,65,2,6,3,4,2,6,7,8,9,3,2,3,5,7,2,45};
    vector<unsigned long> ndxs;
    vector<int> sampleTo(7);
    for(unsigned long i=0;i<sampleFrom.size();i++){
        ndxs.push_back(i);
    }
    cout<<"ndxs before"<<endl;
    printVec(ndxs);
    printVec(sampleFrom);
    sample(sampleTo,sampleFrom,ndxs);

    cout<<"ndxs after"<<endl;
    printVec(ndxs);
    printVec(sampleTo);

    return 0;
}
