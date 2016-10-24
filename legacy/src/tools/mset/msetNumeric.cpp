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
using namespace std;

int main(int argc, char** argv){
    ofstream progress;
    //stringstream cout;
    set<int> setOfInterest;
    set<int> top;
    vector<int> background;

    int countsArraySize=40;
    vector<int> counts(countsArraySize);//assume intersect length wont exceed 40, but pushback if it is

    int topResults=0;
    int numSamples=0;
    if(argc!=5){
        cerr<<"expected <num top results> <num samples> <set-of-intrest filepath> <background filepath> as arguments"<<endl; //TODO: change to log file, add support for multiple files
        exit(1);
    }
    cout<<"-"<<argv[4]<<"-not opened"<<endl;
    topResults=atoi(argv[1]);
    numSamples=atoi(argv[2]);
    ifstream readLists(argv[3]);
    if(readLists){
        cout<<"readLists open"<<endl;
    }
    int input=0;
    while(readLists>>input){
        setOfInterest.insert(input);
    }

    readLists.clear();
    readLists.close();
    readLists.open(argv[4]);
    input=0;
    while(readLists>>input){
        cout<<input<<endl;
        background.push_back(input);
    }
    //*


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

    vector<vector<int> > samples;
    for(int i=0;i<numSamples;i++){
        samples.push_back(vector<int>(top.size()*2));//don't know why times two but it is in the publication
        sampler.sample(samples[i]);//sample samples[i].size elements from background into samples[i] without replacement
    }


    cout<<endl<<"samples generated"<<endl;
    int maxIntersectLength=0;
    int numGreater=0;
    for(int i=0;i<numSamples;i++){
        vector<int> sampledSet=unique(samples[i]);//using a set directly to do unique would sort it
        //because the set needs to be truncated after being converted to a set,
        //it cannot be sorted if the behavior of the mset.R file is to be copied
        sampledSet.resize(top.size());
        int intersectSize=isectFinder.getIntersectionSizeWith(sampledSet);

        if(intersectSize>maxIntersectLength){
            maxIntersectLength=intersectSize;
        }

        if(intersectSize>countsArraySize){//shouldn't happen but just incase
            countsArraySize=intersectSize;
            counts.resize(countsArraySize,0);
        }
        counts[intersectSize]++;

        //cout<<intersectSize<<endl;
        if(intersectSize>=checklength){
            //if the size of the intersect of sampledSet and setOfInterest> the checklength intersect from before
            numGreater++;//increment the count
        }
        progress.open("msetOutput.txt");
        char str[2048];
        //sprintf(str,"%04d/%d samples computed",i,numSamples);
        printf("%04d/%d samples computed\r",i,numSamples);
        progress<<str<<endl;
        progress.clear();
        progress.close();
    }

    cout<<"                                          "<<endl;
    counts.resize(maxIntersectLength+1);

    double pvalue=((double)numGreater)/((double)numSamples);

    cout<<"p-value: "<<pvalue<<endl;
    cout<<endl;
    cout<<numGreater<<" simulated results of length "<<top.size()<<" contained at least as many matches"<<endl;
    cout<<"to database as actual expression results."<<endl;
    cout<<"density:"<<endl;
    for(unsigned int i=0;i<counts.size();i++){
        cout<<i<<" "<<double(counts[i])/double(numSamples)<<endl;
    }
    progress.open("msetOutput.txt");
    //progress<<cout.str()<<endl;
    progress.clear();
    progress.close();
//*/
    return 0;
}
