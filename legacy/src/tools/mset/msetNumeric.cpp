/*
mset.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
seg fualting, but this version directly corresponds to original paper
*/
#include <iostream>
#include <fstream>
#include <sstream>
#include "vectorUnique.h"//move to separate h files so they can be linked
#include "WithoutReplacementSampler.h"//with this and with separate driver files
#include "IntersectSizeFinder.h"
#include <pqxx/pqxx>
using namespace std;
using namespace pqxx;

int main(int argc, char** argv){
    ofstream progress;
    stringstream cout;
    connection dbConnection("dbname=postgres user=postgres password=example_password hostaddr=127.0.0.1 port=5432");
    /*
    if(dbConnection.is_open()){
        cout<<"success!!"<<endl;
    }else{
        cout<<"failure"<<endl;
    }
    */
    set<int> setOfInterest;
    set<int> top;
    vector<int> background;


    nontransaction queryExecutor(dbConnection);
    result getBackground(queryExecutor.exec("select GENE_NO from background"));
    for(result::const_iterator row=getBackground.begin(); row != getBackground.end(); row++){
        background.push_back(row[0].as<int>());
    }

    int topResults=0;
    int numSamples=0;
    /*
    result getSetOfInterest(queryExecutor.exec("select GENE_NO from amMGI"));
    for(result::const_iterator row=getSetOfInterest.begin(); row != getSetOfInterest.end(); row++){
        setOfInterest.insert(row[0].as<int>());
    }
    cout<<"enter number of top results:>";
    cin>>topResults;

    cout<<"enter number of samples:>";
    cin>>numSamples;
    /*/
    if(argc!=4){
        cerr<<"expected <num top results> <num samples> <filepath> as arguments"<<endl; //TODO: change to log file, add support for multiple files
        exit(1);
    }
    topResults=atoi(argv[1]);
    numSamples=atoi(argv[2]);
    ifstream readLists(argv[3]);
    int input=0;
    while(readLists>>input){
        setOfInterest.insert(input);
    }

    readLists.clear();
    readLists.close();
    //*/


    //copy that number from background into top, converting to set in the
    //process
    int count=0;
    for(vector<int>::iterator i=background.begin(); distance(background.begin(),i)<topResults;i++){
        count++;
        top.insert(*i);
    }

    WithoutReplacementSampler<int> sampler;
    sampler.setSource(&background);

    IntersectSizeFinder<int> isectFinder(setOfInterest.begin(),setOfInterest.end());

    cout<<numSamples<<" simulated results of length "<<top.size()<<" generated from background"<<endl;
    //the length of the intersect with the top set and the intrest set to
    //compare to the simulations
    int checklength=isectFinder.getIntersectionSizeWith(top);
    cout<<checklength<<" matches to database found in microarray results"<<endl;
    vector<int> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
    cout<<"matches are: "<<endl;
    for(int i=0;i<(int)matches.size();i++){
        cout<<matches[i]<<endl;
    }

    vector<int> sampledList(top.size()*2);//don't know why times two but it is in the publication

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
        progress.open("msetOutput.txt");
        char str[2048];
        sprintf(str,"%04d/%d samples computed",i,numSamples);
        progress<<str<<endl;
        progress.clear();
        progress.close();
        //*/
    }

    double pvalue=((double)numGreater)/((double)numSamples);

    cout<<"p-value: "<<pvalue<<endl;
    cout<<endl;
    cout<<numGreater<<" simulated results of length "<<top.size()<<" contained at least as many matches"<<endl;
    cout<<"to database as actual expression results."<<endl;
    progress.open("msetOutput.txt");
    progress<<cout.str()<<endl;
    progress.clear();
    progress.close();
    return 0;
}
//*/
