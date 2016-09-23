/*
testIntersectSizeFinder.cpp: ...
Created: Fri Sep 23 17:24:42 CDT 2016
*/
#include <iostream>
#include "../IntersectSizeFinder.h"
using namespace std;
int main(int argc, char** argv){

    set<int> testSet{3,5,2,2,7,3,4,1,636};
    IntersectSizeFinder<int> isectFinder(testSet.begin(),testSet.end());

    set<int> testSet2{7,9,1,4};
    cout<<isectFinder.getIntersectionSizeWith(testSet2)<<" should be 3"<<endl;

    vector<int> testVect{7,9,1,4};
    cout<<isectFinder.getIntersectionSizeWith(testVect)<<" should be 3"<<endl;

    set<int> testSet3{7,9,636,23,2,2,1,4};
    cout<<isectFinder.getIntersectionSizeWith(testSet3)<<" should be 3"<<endl;

    vector<int> testVect2{7,9,636,23,2,2,1,4};
    cout<<isectFinder.getIntersectionSizeWith(testVect2)<<" should be 3"<<endl;


    return 0;
}
