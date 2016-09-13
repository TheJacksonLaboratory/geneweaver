/*
testPvalueSame.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
*/
#include <fstream>
#include <iostream>
#include <algorithm>
#include <set>
#include <vector>
#include <cstdlib>
#include <ctime>
using namespace std;

//without replacement
void sample(vector<string>& sampleInto,vector<string>& from){
    for(unsigned int i=0;i<sampleInto.size();i++){
        sampleInto[i]=from[rand()%from.size()];
    }
}

//gets the size of the intersection between the two ranges defined by the four
//iterators
//modified from cplusplus.com algorithm's set_intersection
template<typename Iter1,typename Iter2>
int intersectSize(Iter1 first1,Iter1 last1,
                  Iter2 first2,Iter2 last2){
    int toReturn=0;
    while(first1!=last1 && first2!=last2){
        if(*first1<*first2) first1++;
        else if (*first2<*first1) first2++;
        else{
            toReturn++;
            first1++;
            first2++;
        }
    }
    return toReturn;
}

int main(int argc, char** argv){
    srand(time(0));
    set<string> backgroundRead;
    set<string> listOfInterestRead;
    vector<string> top;


    string bgFilename;
    cout<<"enter filename for background:>";
    cin>>bgFilename;

    string interestFilename;
    cout<<"enter filename for list of interest:>";
    cin>>interestFilename;

    ifstream readLists(bgFilename.c_str());

    string inputStr;
    while(readLists>>inputStr){
        if(inputStr!="---"){
            backgroundRead.insert(inputStr);//read into sets so they're unique
        }
    }
    readLists.clear();
    readLists.close();
    readLists.open(interestFilename.c_str());

    while(readLists>>inputStr){
        if(inputStr!="---"){
            listOfInterestRead.insert(inputStr);
        }
    }

    int topResults=0;
    cout<<"enter number of top results:>";
    cin>>topResults;

    //copy that number from background into top
    for(set<string>::iterator i=backgroundRead.begin(); distance(backgroundRead.begin(),i)<topResults;i++){
        top.push_back(*i);
    }

    vector<string> background(backgroundRead.begin(),backgroundRead.end());//copy the set into a vector so it can be shuffled
    vector<string> listOfInterest(listOfInterestRead.begin(),listOfInterestRead.end());//same deal

    int numSamples=0;
    cout<<"enter number of samples:>";
    cin>>numSamples;


    int checklength=intersectSize(top.begin(),top.end(),listOfInterest.begin(),listOfInterest.end());
    vector<string> sampledSet(listOfInterest.size());

    cout<<"everything is read"<<endl;
    int numGreater=0;
    for(int i=0;i<numSamples;i++){
        sample(sampledSet,background);
        if(intersectSize(sampledSet.begin(),sampledSet.end(),listOfInterest.begin(),listOfInterest.end())>checklength){
            numGreater++;
        }
    }

    double pvalue=((double)numGreater)/((double)numSamples);

    cout<<"pvalue: "<<pvalue<<endl;
    cout<<"number with at least as many matches as actual: "<<numGreater<<endl;

    return 0;
}
