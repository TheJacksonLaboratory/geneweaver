/*
testEndErase.cpp: ...
Created: Tue Sep 20 17:01:09 CDT 2016
*/
#include <iostream>
#include <vector>

using namespace std;
template< typename T>
void printVec(vector<T>& v){
    for(unsigned int i=0;i<v.size();i++){
        cout<<" "<<v[i];
    }
    cout<<endl;
}
/*
template< typename T>
void eraseToSize(vector<T>& toShorten, unsigned int size){
    for(unsigned int i=0;i<(toShorten.size()-size);i++){
        toShorten.erase(--toShorten.end());
    }
}

*/
int main(int argc, char** argv){
    vector<int> test{0,1,2,3,4,5,6,7,8,9};
    printVec(test);
    test.resize(4);
    printVec(test);
    cout<<(*(--test.end()))<<endl;
    return 0;
}
