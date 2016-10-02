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
    vector<int> expectedOutput{2,5,6,3,7,9,1,10};
    cout<<"unique on: "<<uniquify<<endl;
    cout<<"expected to be "<<expectedOutput<<endl;
    cout<<"actual: "<<unique(uniquify)<<endl;
    return 0;
}
