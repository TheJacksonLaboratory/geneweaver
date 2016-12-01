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

/*this is just the unique function from the vectorUnique.h file
 * it is global here to be able to pass it to the threads which run this on
 * many samples in parallel
 */
void uniquify(vector<string>* sample,long size){
        unique(*sample);
        sample->resize(size);
}

class MSET{

private:

    void calculateIntersections(IntersectSizeFinder<string>* isectFinder, vector<int>* counts,
            vector<string>* sampledSet, long& numGreater,long checklength,long& maxIsectSize){
        //uniquify(sampledSet,topSize);


//numLock.lock();

        /* the intersect finder is not yet thread safe, as doing so would require
         * writing our own thread safe version of unordered_map. because of this,
         * this part would need to be in the mutex, which would effectively serialize the execution
         * and negate the performance benifit from threading
         */
        long intersectSize=isectFinder->getIntersectionSizeWith(*sampledSet);
        if(intersectSize>=checklength){
            if(maxIsectSize<intersectSize){//we need to know the maximum intersect size to find the upper
                maxIsectSize=intersectSize;//bound on the density graph's X values, and crop it's array
            }
            //if the size of the intersect of sampledSet and setOfInterest> the checklength intersect from before
            numGreater++;//increment the count
        }
        /* we count the number of times the intersect size was x for each x
         * allowing us to show a probability density graph for the algorithm
         */
        (*counts)[intersectSize]++;
//numLock.unlock();

    }

public:
    void toUpper(string& input){
        for(unsigned int i=0;i<input.size();i++){
            int curr=int(input[i]);
            if(int('a')<=curr&&(int('z')+1)>curr){
                curr-=(int('a')-int('A'));
                input[i]=char(curr);
            }
        }
        input.erase(input.size()-1,1);
    }
    string run(int numSamples,string topFile, vector<string> backgroundFiles,string interestFile){
        stringstream readUpperCaseBuffer;
        string errorMsg="Warning! empty background selected, samples can't be generated";
        bool success=false;
        set<string> setOfInterest;
        set<string> top;
        vector<string> background;

        int countsArraySize=1000;
        vector<int> counts(countsArraySize);//assume intersect length wont exceed 1000
        //TODO: check if it does


        /////read in all the files/////
        ifstream readLists(interestFile.c_str());
        if(!readLists){
            cerr<<"unable to open "<<interestFile<<endl;
            exit(1);
        }
        string input;
        while(getline(readLists,input)){
            toUpper(input);
            setOfInterest.insert(input);
        }

        for(unsigned int i=0;i<backgroundFiles.size();i++){
            readLists.clear();
            readLists.close();
            readLists.open(backgroundFiles[i]);
            if(!readLists.is_open()){
                cerr<<"unable to open "<<backgroundFiles[i]<<endl;
                exit(1);
            }
            while(getline(readLists,input)){
                toUpper(input);
                background.push_back(input);
            }
        }

        readLists.clear();
        readLists.close();
        readLists.open(topFile);
        if(!readLists){
            cerr<<"unable to open "<<topFile<<endl;
            exit(1);
        }
        while(getline(readLists,input)){
            toUpper(input);
            top.insert(input);
        }
        readLists.clear();
        readLists.close();

        //////initialize the utility classes//////

        WithoutReplacementSampler<string> sampler;
        sampler.setSource(&background);

        IntersectSizeFinder<string> isectFinder(setOfInterest.begin(),setOfInterest.end());

        //the length of the intersect with the top set and the intrest set to
        //compare to the simulations
        long checklength=isectFinder.getIntersectionSizeWith(top);

        if(background.size()>0){
            success=true;
            errorMsg="";
        }else{
            numSamples=-1;
        }


        ////generate and store all of the samples we will use////
        vector<vector<string>* > samples;
        for(int i=0;i<numSamples;i++){
            samples.push_back(new vector<string>(top.size()*2));//don't know why times two but it is in the publication
            sampler.sample(*samples[i]);//sample samples[i].size elements from background into samples[i] without replacement
        }


        long numGreater=0;

        const int maxConcurentThreads=1000;
        thread threads[maxConcurentThreads];

        IntersectSizeFinder<string>* isectFinderPtr=&isectFinder;
        vector<int>* countsPtr=&counts;

        long numberOfCycles=numSamples/maxConcurentThreads;
        long remainder=numSamples%maxConcurentThreads;
        long id=0;
        /*for number of times maxConcurentThreads goes in evenly into num samples,
         * spawn maxConcurentThreads threads running uniquify and wait for them to finish
         */
        for(long i=0;i<numberOfCycles;i++){
            for(long j=0;j<maxConcurentThreads;j++){
                /*
                threads[j]=thread(
                    calculateIntersections,
                    isectFinderPtr,countsPtr,samples[id],
                    ref(numGreater),checklength,ref(resizeCountsTo));
                */
                threads[j]=thread(uniquify,samples[id],top.size());
                id++;
            }
            for(long j=0;j<maxConcurentThreads;j++){
                threads[j].join();
            }
        }

        //take care of the remaining samples
        for(long j=0;j<remainder;j++){
            threads[j]=thread(uniquify,samples[id],top.size());
            id++;
        }
        for(long j=0;j<remainder;j++){
            threads[j].join();
        }

        //do all the instersections
        long resizeCountsTo=0;
        for(long i=0;i<numSamples;i++){
            //ref() explicitly tells the compiler that a variable is pass by reference,
            //which is needed if this is used in a multithreaded way later on
            calculateIntersections(
                    isectFinderPtr,countsPtr,samples[i],
                    ref(numGreater),checklength,ref(resizeCountsTo));
        }

        //crop all the 0 elements at the end out of the probability density data
        counts.resize(resizeCountsTo+1);

        //clean up the memory used for the samples
        for(int i=0;i<numSamples;i++){
            delete samples[i];
        } 
        stringstream jsonOutput;

        //pvalue is calculated as 
        //
        //count( length(intersect(set-of-interest,sample[i]) >= length(intersect(set-of-interest,top)) ) for all samples
        //______________________________________________________________________________________________________________
        //                                           number of samples
        double pvalue=((double)numGreater)/((double)numSamples);


        /////output everything to json and return it
        string tb="    ";
        jsonOutput<<"{"<<endl;
        jsonOutput<<tb<<"\"name\": \""<<interestFile<<"\","<<endl;
        jsonOutput<<tb<<"\"success\": \"";
        if(success){
            jsonOutput<<"true";
        }else{
            jsonOutput<<"false";
        }
        jsonOutput<<"\","<<endl;
        jsonOutput<<tb<<"\"errorMsg\": \""<<errorMsg<<"\","<<endl;

        //matches to database found in microarray results
        jsonOutput<<tb<<"\"inTopAndInterestCount\": "<<checklength<<","<<endl;
        jsonOutput<<tb<<"\"inTopAndInterest\": ["<<endl;
        vector<string> matches=isectFinder.getIntersectionWith(top.begin(),top.end());
        for(unsigned int i=0;i<matches.size();i++){
            jsonOutput<<tb<<tb<<"\""<<matches[i]<<"\"";
            if(i!=(matches.size()-1)){
                jsonOutput<<",";
            }
            jsonOutput<<endl;
        }
        jsonOutput<<tb<<"],"<<endl;
          //number of samples where
         //simulated results of length n contained at least as many matches
        //to database as actual expression results.
        jsonOutput<<tb<<"\"numSamples\": "<<numSamples<<","<<endl;
        jsonOutput<<tb<<"\"intersectGreaterCount\": "<<numGreater<<","<<endl;
        jsonOutput<<tb<<"\"sampleLength\": "<<top.size()<<","<<endl;//length of each sample
        jsonOutput<<tb<<"\"pValue\": "<<pvalue<<","<<endl;
        jsonOutput<<tb<<"\"densityPointCount\": "<<counts.size()<<","<<endl;//length of density array
        jsonOutput<<tb<<"\"density\": ["<<endl;//density array
        for(unsigned int i=0;i<counts.size();i++){
            jsonOutput<<tb<<tb<<double(counts[i])/double(numSamples);
            if(i!=(counts.size()-1)){
                jsonOutput<<",";
            }
            jsonOutput<<endl;
        }
        jsonOutput<<tb<<"],"<<endl;
        jsonOutput<<tb<<"\"interestToBackgroundSizeRatio\": ";
        if(numSamples!=-1){
            jsonOutput<<double(setOfInterest.size())/double(background.size());
        }
        else{
            jsonOutput<<"-1";
        }
        jsonOutput<<endl;
        jsonOutput<<"}";

        return jsonOutput.str();

    }
};
