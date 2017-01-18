#include "./Mset.h"
#include <cstdlib>

using namespace std;

enum ERROR_CODES{NOT_ENOUGH_ARGS,SHORT_LIST,NO_INTEREST_FILE,NO_NUM_SAMPLES,UNEXPECTED_END};
string usageMessage="usage: prog  <# background files> <background files ...>\
<top file> <# interest files> <interest files ...> <# samples>";

class ArgumentIterator{
public:
    ArgumentIterator(int mainArgc,char** mainArgv){
        argNdx=1;
        argv=mainArgv;
        argc=mainArgc;
    }
    string get(){
        string toReturn=argv[argNdx];
        argNdx++;
        return toReturn;
    }
    int getInt(){
        return atoi(get().c_str());//TODO: use error checking version
    }
    bool done(){
        return argNdx>=argc;
    }
    string getName(){
        return argv[0];
    }
    vector<string> getVariableArgList(){
        vector<string> toReturn;
        int listSize=0;
        if(!done()){
            listSize=getInt();//use error checking version
        }
        for(int i=0;i<listSize;i++){
            if(done()){
                cerr<<"variable list ended early, was promised "<<listSize<<" args"<<endl;
                cerr<<usageMessage<<endl;
                exit(SHORT_LIST);
            }
            toReturn.push_back(get());
        }
        return toReturn;
    }
    int getPosition(){
        return argNdx;
    }
private:
    int argNdx;
    int argc;
    char** argv;
};

int main(int argc, char** argv){
    if(argc<6){
        cerr<<usageMessage<<endl;
        exit(NOT_ENOUGH_ARGS);
    }
    ArgumentIterator args(argc,argv);
    vector<string> backgroundFiles=args.getVariableArgList();
    if(args.done()){
        cerr<<"expected topGeneFile;"<<endl;
        cerr<<usageMessage<<endl;
        exit(NO_INTEREST_FILE);
    }
    string topGenePath=args.get();
    vector<string> interestFiles=args.getVariableArgList();
    if(args.done()){
        cerr<<"expected numSamples;"<<endl;
        cerr<<usageMessage<<endl;
        exit(NO_NUM_SAMPLES);
    }
    int numSamples=args.getInt();

    if(!args.done()){
        cerr<<"expected to be done with input, but was not!"<<endl;
        cerr<<"(reading ended at "<<argv[args.getPosition()]<<")"<<endl;
        cerr<<usageMessage<<endl;
        exit(UNEXPECTED_END);
    }

    ofstream cout("output.json");

    MSET msetFinder;//main logic is in this mset class
    cout<<"{\"data\":["<<endl;//the cpp just puts the json objects into an array
    cout<<msetFinder.run(numSamples,topGenePath,backgroundFiles,interestFiles[0]);//run function outputs a json object of the results of the mset run
    for(unsigned int i=1;i<interestFiles.size();i++){
        cout<<","<<endl<<msetFinder.run(numSamples,topGenePath,backgroundFiles,interestFiles[i]);
    }
    cout<<endl;
    cout<<"]}"<<endl;
    cout.close();
    return 0;
}
