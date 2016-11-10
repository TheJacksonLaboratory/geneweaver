#include "./Mset.h"

int main(int argc, char** argv){
    if(argc<6){
        cerr<<"expected <num samples> <topFile path> <background filepath> <number of interestFiles> <set-of-intrest filepath>"<<endl; //TODO: change to log file
        exit(1);
    }
    /*    //string
    MSET<string> msetFinder;//main logic is in this mset class, which is templated incase requirements change
    /*/   //numeric
    MSET<int> msetFinder;
    //*/
    int numSamples=atoi(argv[1]);//TODO: use error checking version
    string topFile=argv[2];
    string backgroundFile=argv[3];
    int numInterestFiles=atoi(argv[4]);
    cout<<"{\"data\":["<<endl;//the cpp just puts the json objects into an array
    cout<<msetFinder.run(numSamples,topFile,backgroundFile,argv[5]);//run function outputs a json object of the results of the mset run
    for(int i=1;i<numInterestFiles;i++){
        cout<<","<<endl<<msetFinder.run(numSamples,topFile,backgroundFile,argv[i+5]);
    }
    cout<<endl;
    cout<<"]}"<<endl;
    return 0;
}
