/*
count.cpp: confirming that ploting density function in original mset is the 
number of times the intersection length was the same on the sample.
i.e.
with 10 samples, if intersect length was 3 for 4 samples, and 2 for 6 samples,
it would be 
x  y
3 .4
2 .6
Created: Wed Oct 19 19:32:06 CDT 2016
*/
#include <iostream>
#include <fstream>
using namespace std;
int main(){
    int counts[22]={0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0,0};
    int input=0;
    ifstream file("plotpointsSorted");
    int count=0;
    while(file>>input){
        counts[input]++;
        count++;
    }
    for(int i=0;i<22;i++){
        cout<<i<<" "<<double(counts[i])/double(count)<<endl;
        //cout<<i<<" "<<counts[i]<<" "<<double(counts[i])/double(count)<<endl;
    }
    cout<<endl;
    file.close();
    return 0;
}
