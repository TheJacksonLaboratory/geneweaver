/*
mset.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
seg fualting, but this version directly corresponds to original paper
*/
#include <fstream>
#include <iostream>
#include "vectorUnique.h"//move to separate h files so they can be linked
#include "WithoutReplacementSampler.h"//with this and with separate driver files
#include "IntersectSizeFinder.h"
using namespace std;



int main(int argc, char** argv){

    set<string> setOfInterest;
    set<string> top;
    vector<string> background;


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
            background.push_back(inputStr);
        }
    }
    readLists.clear();
    readLists.close();
    readLists.open(interestFilename.c_str());

    while(readLists>>inputStr){
        if(inputStr!="---"){
            setOfInterest.insert(inputStr);
        }
    }

    readLists.clear();
    readLists.close();

    int topResults=0;
    cout<<"enter number of top results:>";
    cin>>topResults;

    //copy that number from background into top, converting to set in the
    //process
    int count=0;
    for(vector<string>::iterator i=background.begin(); distance(background.begin(),i)<topResults;i++){
        count++;
        top.insert(*i);
    }
    cout<<"count: "<<count<<", top.size(): "<<top.size()<<endl;

    int numSamples=0;
    cout<<"enter number of samples:>";
    cin>>numSamples;

    WithoutReplacementSampler<string> sampler;
    sampler.setSource(&background);

    IntersectSizeFinder<string> isectFinder(setOfInterest.begin(),setOfInterest.end());

    //the length of the intersect with the top set and the intrest set to
    //compare to the simulations
    int checklength=isectFinder.getIntersectionSizeWith(top);
    cout<<"matches to database found in microarray results "<<checklength<<endl;
    vector<string> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
    cout<<"matches are: "<<endl;
    for(int i=0;i<(int)matches.size();i++){
        cout<<matches[i]<<endl;
    }

    vector<string> sampledList(top.size()*2);//don't know why times two but it is in the publication

    cout<<"everything is read"<<endl;
    int numGreater=0;
    for(int i=0;i<numSamples;i++){
        sampler.sample(sampledList);//sample sampledList.size elements from background into sampledList without replacement
        vector<string> sampledSet=unique(sampledList);//using a set directly to do unique would sort it
        //because the set needs to be truncated after being converted to a set,
        //it cannot be sorted if the behavior of the mset.R file is to be copied
        sampledSet.resize(top.size());
        int intersectSize=isectFinder.getIntersectionSizeWith(sampledSet);
        //cout<<intersectSize<<endl;
        if(intersectSize>=checklength){
            //if the size of the intersect of sampledSet and setOfInterest> the checklength intersect from before
            numGreater++;//increment the count
        }
        //*/
    }

    double pvalue=((double)numGreater)/((double)numSamples);

    cout<<"pvalue: "<<pvalue<<endl;
    cout<<"number with at least as many matches as actual: "<<numGreater<<endl;

    return 0;
}
//*/
