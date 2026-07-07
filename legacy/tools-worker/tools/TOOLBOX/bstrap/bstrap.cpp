/**
 * bstrap.cpp
 * Bootstrapper main method
 *
 * Input: biclique file and base portion of output filename
 * Output: bootstrapped graph printouts
 *
 * Daniel Morillo
 * December 16, 2010
 *
**/
#include <iostream>
#include <fstream>
#include <set>
#include <string>
#include <time.h>

#include "BipartiteData.h"

#include "boost/algorithm/string.hpp"

using namespace std;
using namespace boost::algorithm;

int main(int argc,char* args[]){
    //track the time spent in the program
//    clock_t start,finish;
//    start = clock();

    //input file and output name are required
    if(argc<3){
        cout<<"Biclique file and output name are required.\n";
        return 0;
    }
    string biclique_file(args[1]);
    string outfile(args[2]);

    //used for tracking file containing names for terms
    bool useNames=false;
    string namefile="";

    bool blueOnly=false;

    //threading options
    bool forceThread=false;
    int threadChoice=-1;

    //holds multiple iteration/threshold values
    vector<int> iters;
    vector<double> pers;

    //options for printing out files
    vector<int> branchprints;
    vector<int> normalprints;

    int tempint=0;

    BipartiteData bd;

    bool noMP=false;
    
    //blue options maintain index number of iteration set that has blue-only option set
    set<int> blueprints;
    set<int> bluebranches;
    //process options
    for(int i=3;i<argc;i++){
        string s = args[i];

        if(iequals(s,"-prefix")&&i!=argc-1){
            bd.prefix=args[i+1];

        //threading processing
        }else if(iequals(s,"-t")&&i!=argc-1){
            forceThread=true;
            threadChoice=atoi(args[i+1]);
            i++;

        //change coloring threshold
        }else if(iequals(s,"-sig")&&i!=argc-1){
            string values(args[i+1]);
            vector<string> tok;
            Tokenize(values,tok," ");
            for(int j=0;j<(int)tok.size();j++){
                //allow for multiple thresholds for printing variations
                bd.sigvect.push_back(atof(tok[j].c_str()));
            }
            i++;

        //supply a file containing term names (termID -> name)
        }else if(iequals(s,"-name")&&i!=argc-1){
            useNames=true;
            string t(args[i+1]);
            i++;
            namefile=t;

        //print trees of nodes
        }else if(iequals(s,"-print")&&i!=argc-1){
            tempint=atoi(args[i+1]);
            normalprints.push_back(tempint);
            i++;

        //blue-only version of -print
        }else if(iequals(s,"-printblue")&&i!=argc-1){
            tempint=atoi(args[i+1]);
            normalprints.push_back(tempint);
            blueprints.insert((int)normalprints.size()-1);
            i++;

        //print branches of nodes
        }else if(iequals(s,"-printbranch")&&i!=argc-2){
            tempint=atoi(args[i+1]);
            branchprints.push_back(tempint);
            tempint=atoi(args[i+2]);
            branchprints.push_back(tempint);
            i++;
            i++;

        //blue-only version of -printbranch
        }else if(iequals(s,"-printbranchblue")&&i!=argc-2){
            tempint=atoi(args[i+1]);
            branchprints.push_back(tempint);
            tempint=atoi(args[i+2]);
            branchprints.push_back(tempint);
            bluebranches.insert((int)((branchprints.size()-2)));
            i++;
            i++;

        //specify iterations and bootstrap percent inside quotes, "100 .25"
        }else if(iequals(s,"-i")&&i!=argc-1){
            string t(args[i+1]);
            vector<string> tok;
            Tokenize(t,tok," \t");
            for(int i=0;i+1<(int)tok.size();i+=2){
                tempint = atoi(tok[i].c_str());
                if(tempint==0){
                    cout<<"Cannot use 0 as an iteration amount.\n";
                    cout<<"Please make sure each set of bootstrap parameters is in <iterationAmount>(space)<samplingRate> format.\n";
                    return 0;
                }
                iters.push_back(tempint); 
                pers.push_back(atof(tok[i+1].c_str()));
            }
        }
    }

    //check if iterations were specified, otherwise report and quit
    if(iters.empty()){
        cout<<"No iterations were specified (-i \"<iterations> <samplingRate>\", usage example: -i \"100 .5\"). Exiting.\n";
        return 0;
    }

    //set up default threshold vector
    if(bd.sigvect.empty())
        bd.sigvect.push_back(.5);

    time_t temp_t = time(NULL);

    //default to tree printing if needed
    if(branchprints.empty()&&normalprints.empty()){
        normalprints.push_back(-1);
    }

    //load biclique file with no node size exclusions
    bd.lowlimit=0;
    if(bd.loadBicliques_JJ(biclique_file.c_str())){
        cout<<"Could not load biclique file \""<<biclique_file<<"\".\n";
        return 0;
    }

    //load naming file
    if(useNames && bd.loadTermNames(namefile.c_str())){
        cout<<"Could not load name file \""<<namefile<<"\".\n";
        return 0;
    }

    //get processor count or default to one thread
    int procs = boost::thread::hardware_concurrency();
    if(forceThread)
        procs=threadChoice;
    if(procs<1)
        procs = 1;

    //run for each set of iterations
    for(int i=0;i<(int)iters.size();i++){
        cout<<"\n### Run #"<<i+1<<"/"<<iters.size()<<": "<<iters[i]<<","<<pers[i]<<endl;

        //obtain total iterations for reference
        int itertotal = iters[i];
        bd.iteration_total = itertotal;
        bd.clearLinks();

        //threading setup
        if(procs>1){
            IterThread* threads = new IterThread[procs];

            //split iterations between each processor
            int itersingle = iters[i]/procs;
            int* ithold = new int[procs];

            for(int p=0;p<procs;p++)
                ithold[p]=itersingle;

            //split remainder evenly among processors
            int iterremaining = iters[i]-itersingle*procs;
            int itemp=0;
            while(iterremaining>0){
                ithold[itemp]++;
                iterremaining--;
                itemp++;
                itemp=itemp%procs;
            }

            //set up data pointers and start thread
            for(int p=0;p<procs;p++){
                unsigned int val = (unsigned int)(temp_t);

                //shifting only good up to 32 cores (unsigned int seed)
                int shift = (7*p)%32;
                unsigned int val2 = (val << shift) | (val >> (32 - shift));
                threads[p].setIterations(ithold[p]);
                threads[p].attachData(&bd.bicliques,&bd.links,&bd.termset,pers[i],val2);
                threads[p].id=p;
                threads[p].start();
            }

            //wait for threads to finish
            for(int p=0;p<procs;p++){
                threads[p].join();
            }
            delete[] ithold;
            delete[] threads;
        }else
            //no thread version
            bd.iterateLinks(iters[i],pers[i]);

        //print out each tree setup
        int templimit=0;
        //print out a diagram per threshold value given

            //set up the output filename
            stringstream s;
            s<<outfile<<"_";
            string temp1=s.str();
            s.str("");
            s<<iters[i]<<"_"<<pers[i];         //<<"_t"<<sigvect[k];
            string temp2=s.str();

            for(int j=0;j<(int)normalprints.size();j++){
                stringstream t;
                t<<temp1;
                if(blueprints.find(j)!=blueprints.end()){
                    t<<"blueonly_";
                    blueOnly=true;
                }else
                    blueOnly=false;
                t<<temp2<<"_p"<<j;

                //positive values limit the tree's starting points from the bottom
                //3 = print all trees found until size 2 nodes are found
                //negative values limit the tree's starting points from the top
                //-3 = print all trees in the top 3 sizes
                if(normalprints[j]<0)
                    templimit=bd.max_biclique_size+normalprints[j];
                else
                    templimit=normalprints[j];

                cout<<"Printing diagrams (group "<<j+1<<")\n";

		// bd.outputDot(t.str().c_str(),templimit,blueOnly);
                bd.output_PM(templimit,blueOnly);
            }

            //print out branching diagrams
            for(int j=0;j<(int)branchprints.size();j+=2){
                stringstream t;
                t<<temp1;
                if(bluebranches.find(j)!=bluebranches.end()){
                    t<<"blueonly_";
                    blueOnly=true;
                }else
                    blueOnly=false;
                t<<temp2<<"_b"<<j/2;

                //values work similar to tree setup
                if(branchprints[j]<0)
                    templimit=bd.max_biclique_size+branchprints[j];
                else
                    templimit=branchprints[j];

                //second parameter controls limit on nodes being used for branching
                //positive = node size
                //negative = nodes size from the top
                int lowlimit = 0;
                if(branchprints[j+1]<0)
                    lowlimit = bd.max_biclique_size+branchprints[j+1];
                else
                    lowlimit = branchprints[j+1];

                cout<<"Printing branching diagrams (group "<<j/2+1<<")\n";

                bd.branchOutputDot(t.str().c_str(),lowlimit,templimit,blueOnly);
            }
    }
    //enable at top for time tracking
//    finish=clock();
//    cout<<"Ran for duration: "<<finish-start<<endl;
}

