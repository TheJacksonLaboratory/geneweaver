/*
testToUpper.cpp: ...
Created: Wed Nov 30 17:48:26 CST 2016
*/
#include <iostream>
#include "Mset.h"
using namespace std;
int main(int argc, char** argv){
    MSET mset;
    string testStr=".{}-- abcd1234\n";
    cout<<"\""<<testStr<<"\""<<endl;
    mset.toUpper(testStr);
    cout<<"\""<<testStr<<"\""<<endl;
    return 0;
}
