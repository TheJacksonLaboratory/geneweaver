/*
testIntersectSizeFinder.cpp: ...
Created: Fri Sep 23 17:24:42 CDT 2016
*/
#include <iostream>
#include "../IntersectSizeFinder.h"
#include "printVec.h"
using namespace std;

int main(int argc, char** argv){

    set<int> testSet{3,5,2,2,7,3,4,1,636};
    cout<<"intersect "<<testSet<<endl;
    IntersectSizeFinder<int> isectFinder(testSet.begin(),testSet.end());

    set<int> testSet2{7,9,1,4};
    cout<<"with: "<<testSet2<<endl;
    cout<<isectFinder.getIntersectionSizeWith(testSet2)<<" should be 3"<<endl;

    vector<int> testVect{7,9,1,4};
    cout<<"with: "<<testVect<<endl;
    cout<<isectFinder.getIntersectionSizeWith(testVect)<<" should be 3"<<endl;

    set<int>     testSet3{7,9,636,23,2,1,4};
    cout<<"with: "<<testSet3<<endl;
    cout<<isectFinder.getIntersectionSizeWith(testSet3)<<" should be 5"<<endl;

    vector<int> testVect2{7,9,636,23,2,2,1,4};
    cout<<"with: "<<testVect2<<endl;
    cout<<isectFinder.getIntersectionSizeWith(testVect2)<<" should be 6"<<endl;


    vector<int> result=(isectFinder.getIntersectionWith(testVect2.begin(),testVect2.end()));
    cout<<"with: "<<testVect2<<"=";
    cout<<result<<endl;

    return 0;
}
