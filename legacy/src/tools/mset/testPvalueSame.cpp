/*
testPvalueSame.cpp: ...
Created: Sun Sep 11 18:47:33 CDT 2016
*/
#include <fstream>
#include <iostream>
#include <set>
#include <cstdlib>
#include <ctime>
using namespace std;

//without replacement
set<string> sample(set<string>& from, int size){
    set<string> toReturn;
    for(int i=0;i<size;i++){
        int which=rand()%from.size();//choose a random index
        int element=0;
        set<string>::iterator j=from.begin();
        while(element<which && j!=from.end()){
            j++;//get to it
            element++;
        }
        toReturn.insert(*j);//insert the element there into the return set
        from.erase(j);//remove it from the input set (without replacement)
    }
    return toReturn;
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
    set<string> background;
    set<string> top;
    set<string> listOfInterest;


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
            background.insert(inputStr);
        }
    }
    readLists.clear();
    readLists.close();
    readLists.open(interestFilename.c_str());

    while(readLists>>inputStr){
        if(inputStr!="---"){
            listOfInterest.insert(inputStr);
        }
    }

    int topResults=0;
    cout<<"enter number of top results:>";
    cin>>topResults;

    //copy that number from background into top
    for(set<string>::iterator i=background.begin(); distance(background.begin(),i)<topResults;i++){
        top.insert(*i);
    }

    int numSamples=0;
    cout<<"enter number of samples:>";
    cin>>numSamples;


    int checklength=intersectSize(top.begin(),top.end(),listOfInterest.begin(),listOfInterest.end());
    int sampleSize=listOfInterest.size();

    int numGreater=0;
    for(int i=0;i<numSamples;i++){
        set<string> sampledSet=sample(background,sampleSize);
        if(intersectSize(sampledSet.begin(),sampledSet.end(),listOfInterest.begin(),listOfInterest.end())>checklength){
            numGreater++;
        }
    }

    double pvalue=((double)numGreater)/((double)numSamples);

    cout<<"pvalue: "<<pvalue<<endl;

    return 0;
}
