/*
mset.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
seg fualting, but this version directly corresponds to original paper
*/
#include <iostream>
#include <fstream>
#include "vectorUnique.h"//move to separate h files so they can be linked
#include "WithoutReplacementSampler.h"//with this and with separate driver files
#include "IntersectSizeFinder.h"
#include <pqxx/pqxx>
using namespace std;
using namespace pqxx;

int main(int argc, char** argv){
    connection dbConnection("dbname=postgres user=postgres password=example_password hostaddr=127.0.0.1 port=5432");
    if(dbConnection.is_open()){
        cout<<"success!!"<<endl;
    }else{
        cout<<"failure"<<endl;
    }
    set<int> setOfInterest;
    set<int> top;
    vector<int> background;


    nontransaction queryExecutor(dbConnection);
    result getBackground(queryExecutor.exec("select GENE_NO from background"));
    for(result::const_iterator row=getBackground.begin(); row != getBackground.end(); row++){
        background.push_back(row[0].as<int>());
    }

    result getSetOfInterest(queryExecutor.exec("select GENE_NO from amMGI"));
    for(result::const_iterator row=getSetOfInterest.begin(); row != getSetOfInterest.end(); row++){
        setOfInterest.insert(row[0].as<int>());
    }

    int topResults=0;
    cout<<"enter number of top results:>";
    cin>>topResults;

    //copy that number from background into top, converting to set in the
    //process
    int count=0;
    for(vector<int>::iterator i=background.begin(); distance(background.begin(),i)<topResults;i++){
        count++;
        top.insert(*i);
    }
    cout<<"count: "<<count<<", top.size(): "<<top.size()<<endl;

    int numSamples=0;
    cout<<"enter number of samples:>";
    cin>>numSamples;

    WithoutReplacementSampler<int> sampler;
    sampler.setSource(&background);

    IntersectSizeFinder<int> isectFinder(setOfInterest.begin(),setOfInterest.end());

    //the length of the intersect with the top set and the intrest set to
    //compare to the simulations
    int checklength=isectFinder.getIntersectionSizeWith(top);
    cout<<"matches to database found in microarray results "<<checklength<<endl;
    vector<int> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
    cout<<"matches are: "<<endl;
    for(int i=0;i<(int)matches.size();i++){
        cout<<matches[i]<<endl;
    }

    vector<int> sampledList(top.size()*2);//don't know why times two but it is in the publication

    cout<<"everything is read"<<endl;
    int numGreater=0;
    for(int i=0;i<numSamples;i++){
        sampler.sample(sampledList);//sample sampledList.size elements from background into sampledList without replacement
        vector<int> sampledSet=unique(sampledList);//using a set directly to do unique would sort it
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
