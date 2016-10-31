#include "./Mset.h"

int main(int argc, char** argv){
    if(argc<6){
        cerr<<"expected <num samples> <topFile path> <background filepath> <number of interestFiles> <set-of-intrest filepath>"<<endl; //TODO: change to log file, add support for multiple files
        exit(1);
    }
    //*    //string
    MSET<string> msetFinder;
    /*/   //numeric
    MSET<int> msetFinder;
    //*/
    int numSamples=atoi(argv[1]);//TODO: use error checking version
    string topFile=argv[2];
    string backgroundFile=argv[3];
    int numInterestFiles=atoi(argv[4]);
    cout<<"{data:["<<endl;
    cout<<msetFinder.run(numSamples,topFile,backgroundFile,argv[5]);
    for(int i=1;i<numInterestFiles;i++){
        cout<<","<<endl<<msetFinder.run(numSamples,topFile,backgroundFile,argv[i+5]);
    }
    cout<<endl;
    cout<<"]}"<<endl;
    return 0;
}
