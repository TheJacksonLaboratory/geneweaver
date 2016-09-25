/*
testUnique.cpp.cpp: ...
Created: Fri Sep 23 18:15:28 CDT 2016
*/
#include <iostream>
#include "../vectorUnique.h"
#include "printVec.h"
using namespace std;
int main(int argc, char** argv){
    vector<int> uniquify{2,5,6,3,2,5,3,7,9,7,1,10};
    vector<int> expectedOutput{2,5,6,3,7,8,1,10};
    cout<<"unique on: ";
    printVec(uniquify);
    cout<<"expected to be ";
    printVec(expectedOutput);
    vector<int> result=unique(uniquify);
    cout<<"actual: ";
    printVec(result);
    return 0;
}
