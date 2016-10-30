/*
 * created 30th of October
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

template<typename T>
void uniquify(vector<T>* sample,long size){
        unique(*sample);
        sample->resize(size);
}

template<typename T>
class MSET{

private:
    void calculateIntersections(IntersectSizeFinder<T>* isectFinder, vector<int>* counts,
            vector<T>* sampledSet, long& numGreater,long checklength,long& maxIsectSize){
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

public:
    int run(int numSamples,string topFile, string backgroundFile,string interestFile){
        ofstream progress;
        //stringstream cout;
        set<T> setOfInterest;
        set<T> top;
        vector<T> background;

        int countsArraySize=1000;
        vector<int> counts(countsArraySize);//assume intersect length wont exceed 40, but pushback if it is

        ifstream readLists(interestFile.c_str());
        if(!readLists){
            cerr<<"unable to open "<<interestFile<<endl;
            exit(1);
        }
        T input;
        while(readLists>>input){
            setOfInterest.insert(input);
        }

        readLists.clear();
        readLists.close();
        readLists.open(backgroundFile);
        if(!readLists){
            cerr<<"unable to open "<<backgroundFile<<endl;
            exit(1);
        }
        while(readLists>>input){
            background.push_back(input);
        }

        readLists.clear();
        readLists.close();
        readLists.open(topFile);
        if(!readLists){
            cerr<<"unable to open "<<topFile<<endl;
            exit(1);
        }
        while(readLists>>input){
            top.insert(input);
        }

        WithoutReplacementSampler<T> sampler;
        sampler.setSource(&background);

        IntersectSizeFinder<T> isectFinder(setOfInterest.begin(),setOfInterest.end());

        cout<<numSamples<<" simulated results of length "<<top.size()<<" generated from background"<<endl;
        //the length of the intersect with the top set and the intrest set to
        //compare to the simulations
        long checklength=isectFinder.getIntersectionSizeWith(top);
        cout<<checklength<<" matches to database found in microarray results"<<endl;
        vector<T> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
        cout<<"matches are: "<<endl;
        for(int i=0;i<(int)matches.size();i++){
            cout<<matches[i]<<endl;
        }

        vector<vector<T>* > samples;
        for(int i=0;i<numSamples;i++){
            samples.push_back(new vector<T>(top.size()*2));//don't know why times two but it is in the publication
            sampler.sample(*samples[i]);//sample samples[i].size elements from background into samples[i] without replacement
        }


        cout<<endl<<"samples generated"<<endl;
        long numGreater=0;

        const int maxConcurentThreads=1000;
        thread threads[maxConcurentThreads];

        IntersectSizeFinder<T>* isectFinderPtr=&isectFinder;
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
                    ref(numGreater),checklength,ref(resizeCountsTo));
                */
                threads[j]=thread(uniquify<T>,samples[id],top.size());
                id++;
            }
            for(long j=0;j<maxConcurentThreads;j++){
                threads[j].join();
            }
        }
        for(long j=0;j<remainder;j++){
            threads[j]=thread(uniquify<T>,samples[id],top.size());
            id++;
        }
        for(long j=0;j<remainder;j++){
            threads[j].join();
        }

        long resizeCountsTo=0;
        for(long i=0;i<numSamples;i++){
            calculateIntersections(
                    isectFinderPtr,countsPtr,samples[i],
                    ref(numGreater),checklength,ref(resizeCountsTo));
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
};
