/*
mset.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
*/
#include <iostream>
#include <fstream>
#include <sstream>
#include "vectorUnique.h"//move to separate h files so they can be linked
#include "WithoutReplacementSampler.h"//with this and with separate driver files
#include "IntersectSizeFinder.h"
#include <thread>
#include <mutex>
using namespace std;

mutex countLock;
mutex numLock;
void uniquify(vector<string>* sample,long size){
    unique(*sample);
    sample->resize(size);
}
void calculateIntersections(IntersectSizeFinder<string>* isectFinder, vector<int>* counts,
        vector<string>* sampledSet, long& numGreater,long checklength,long& maxIsectSize,long topSize){
    //uniquify(sampledSet,topSize);


    //numLock.lock();
    long intersectSize=isectFinder->getIntersectionSizeWith(*sampledSet);//not yet thread safe
    if(intersectSize>=checklength){
        if(maxIsectSize<intersectSize){
            maxIsectSize=intersectSize;
        }
        //if the size of the intersect of sampledSet and setOfInterest> the checklength intersect from before
        numGreater++;//increment the count
    }
    (*counts)[intersectSize]++;
    //numLock.unlock();

}

int main(int argc, char** argv){
    ofstream progress;
    //stringstream cout;
    set<string> setOfInterest;
    set<string> top;
    vector<string> background;

    int countsArraySize=1000;
    vector<int> counts(countsArraySize);//assume stringersect length wont exceed 40, but pushback if it is

    int topResults=0;
    int numSamples=0;
    if(argc!=5){
        cerr<<"expected <num top results> <num samples> <set-of-stringrest filepath> <background filepath> as arguments"<<endl; //TODO: change to log file, add support for multiple files
        exit(1);
    }
    topResults=atoi(argv[1]);
    numSamples=atoi(argv[2]);
    ifstream readLists(argv[3]);
    if(!readLists){
        cerr<<"unable to open "<<argv[3]<<endl;
        exit(1);
    }
    string input="";
    while(readLists>>input){
        setOfInterest.insert(input);
    }

    readLists.clear();
    readLists.close();
    readLists.open(argv[4]);
    if(!readLists){
        cerr<<"unable to open "<<argv[4]<<endl;
        exit(1);
    }
    input="";
    while(readLists>>input){
        background.push_back(input);
    }


    //copy that number from background stringo top, converting to set in the
    //process
    int count=0;
    for(vector<string>::iterator i=background.begin(); distance(background.begin(),i)<topResults;i++){
        count++;
        top.insert(*i);
    }

    WithoutReplacementSampler<string> sampler;
    sampler.setSource(&background);

    IntersectSizeFinder<string> isectFinder(setOfInterest.begin(),setOfInterest.end());

    cout<<numSamples<<" simulated results of length "<<top.size()<<" generated from background"<<endl;
    //the length of the stringersect with the top set and the stringrest set to
    //compare to the simulations
    long checklength=isectFinder.getIntersectionSizeWith(top);
    cout<<checklength<<" matches to database found in microarray results"<<endl;
    vector<string> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
    cout<<"matches are: "<<endl;
    for(int i=0;i<(int )matches.size();i++){
        cout<<matches[i]<<endl;
    }

    vector<vector<string>* > samples;
    for(int i=0;i<numSamples;i++){
        samples.push_back(new vector<string>(top.size()*2));//don't know why times two but it is in the publication
        sampler.sample(*samples[i]);//sample samples[i].size elements from background stringo samples[i] without replacement
    }


    cout<<endl<<"samples generated"<<endl;
    long numGreater=0;

    const int maxConcurentThreads=1000;
    thread threads[maxConcurentThreads];

    IntersectSizeFinder<string>* isectFinderPtr=&isectFinder;
    vector<int>* countsPtr=&counts;

    long numberOfCycles=numSamples/maxConcurentThreads;
    long remainder=numSamples%maxConcurentThreads;
    long id=0;
    for(long i=0;i<numberOfCycles;i++){
        for(long j=0;j<maxConcurentThreads;j++){
            /*
            threads[j]=thread(
                calculateIntersections,
                isectFinderPtr,countsPtr,samples[id],
                ref(numGreater),checklength,ref(resizeCountsTo),top.size());
            */
            threads[j]=thread(uniquify,samples[id],top.size());
            id++;
        }
        for(long j=0;j<maxConcurentThreads;j++){
            threads[j].join();
        }
    }
    for(long j=0;j<remainder;j++){
        threads[j]=thread(uniquify,samples[id],top.size());
        id++;
    }
    for(long j=0;j<remainder;j++){
        threads[j].join();
    }

    long resizeCountsTo=0;
    for(long i=0;i<numSamples;i++){
        calculateIntersections(
                isectFinderPtr,countsPtr,samples[i],
                ref(numGreater),checklength,ref(resizeCountsTo),top.size());
    }
    counts.resize(resizeCountsTo+1);

    for(int i=0;i<numSamples;i++){
        delete samples[i];
    } 
    cout<<"                                          "<<endl;
    stringstream jsonOutput;

    double pvalue=((double)numGreater)/((double)numSamples);

    string tb="    ";
    jsonOutput<<"{"<<endl;
    jsonOutput<<tb<<"pValue: "<<pvalue<<","<<endl;
    jsonOutput<<tb<<"densityPostringCount: "<<counts.size()<<","<<endl;
    jsonOutput<<tb<<"density: ["<<endl;
    for(unsigned int i=0;i<counts.size();i++){
        jsonOutput<<tb<<tb<<tb<<tb<<double(counts[i])/double(numSamples)<<","<<endl;
    }
    jsonOutput<<tb<<"]"<<endl;
    jsonOutput<<"}"<<endl;

    cout<<"p-value: "<<pvalue<<endl;
    cout<<endl;
    cout<<numGreater<<" simulated results of length "<<top.size()<<" contained at least as many matches"<<endl;
    cout<<"to database as actual expression results."<<endl;
    cout<<"density:"<<endl;
    for(unsigned int i=0;i<counts.size();i++){
        cout<<i<<" "<<double(counts[i])/double(numSamples)<<endl;
    }
    cout<<endl;
    cout<<endl;
    cout<<"json:"<<endl;
    cout<<jsonOutput.str()<<endl;

    //*/
    return 0;
}
