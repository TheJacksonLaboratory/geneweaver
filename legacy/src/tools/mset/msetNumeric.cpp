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
#include <thread>
#include <mutex>
using namespace std;

mutex countLock;
mutex numLock;
void uniquify(vector<int>* sample,long size){
    unique(*sample);
    sample->resize(size);
}
void calculateIntersections(IntersectSizeFinder<int>* isectFinder, vector<int>* counts,
        vector<int>* sampledSet, long& numGreater,long checklength,long& maxIsectSize,long topSize){
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
    set<int> setOfInterest;
    set<int> top;
    vector<int> background;

    int countsArraySize=1000;
    vector<int> counts(countsArraySize);//assume intersect length wont exceed 40, but pushback if it is

    int topResults=0;
    int numSamples=0;
    if(argc!=5){
        cerr<<"expected <num top results> <num samples> <set-of-intrest filepath> <background filepath> as arguments"<<endl; //TODO: change to log file, add support for multiple files
        exit(1);
    }
    topResults=atoi(argv[1]);
    numSamples=atoi(argv[2]);
    ifstream readLists(argv[3]);
    if(!readLists){
        cerr<<"unable to open "<<argv[3]<<endl;
        exit(1);
    }
    int input=0;
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
    input=0;
    while(readLists>>input){
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
    long checklength=isectFinder.getIntersectionSizeWith(top);
    cout<<checklength<<" matches to database found in microarray results"<<endl;
    vector<int> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
    cout<<"matches are: "<<endl;
    for(int i=0;i<(int)matches.size();i++){
        cout<<matches[i]<<endl;
    }

    vector<vector<int>* > samples;
    for(int i=0;i<numSamples;i++){
        samples.push_back(new vector<int>(top.size()*2));//don't know why times two but it is in the publication
        sampler.sample(*samples[i]);//sample samples[i].size elements from background into samples[i] without replacement
    }


    cout<<endl<<"samples generated"<<endl;
    long numGreater=0;

    const int maxConcurentThreads=1000;
    thread threads[maxConcurentThreads];

    IntersectSizeFinder<int>* isectFinderPtr=&isectFinder;
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
    jsonOutput<<tb<<"densityPointCount: "<<counts.size()<<","<<endl;
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

    return 0;
}
