#ifndef BIPARTITEDATA_H
#define BIPARTITEDATA_H
/**
 * BipartiteData.h
 * Contains classes for managing a bipartite graph and its bicliques.
 *
 * Daniel Morillo
 * December 16, 2010
 *
**/

#include <iostream>
#include <fstream>
#include <sstream>
#include <set>
#include <map>
#include <time.h>
#include <vector>
#include <string>

#include "Stringmisc.h"
#include "Setmisc.h"

#include "boost/thread.hpp"

#include <boost/random/mersenne_twister.hpp>
#include <boost/random/uniform_int.hpp>
#include <boost/random/variate_generator.hpp>

using namespace std;

/**
 * Biclique class
 * 
 * Holds the grouping of terms and articles for a specific biclique.
 */
class Biclique{
public:
    set<int> terms;
    set<int> articles;
    int groupsize;
    int id;
    set<Biclique*> children;
    set<Biclique*> parents;
    set<Biclique*> nephews;
    int touched;
};

/**
 * DirectedLink
 * 
 * Represents a directed edge connecting bicliques together in a phenome map.
 */
class DirectedLink{
public:
    int start;
    int end;
    int counter;
    int id;
};

/**
 * BipartiteData
 * 
 * Holds biclique and phenome map information, and generates bootstrapped data.
 */
class BipartiteData{
public:
    //set of edges in phenome map
    //uniqueID -> edge
    map<int,DirectedLink> links;
    //set of bicliques grouped by size of term ID set
    //size -> group of bicliques with same size
    map<int,set<Biclique*> > termgroups;
    map<int,set<DirectedLink*> > bicliqueToLink;
    //set of all bicliques
    //uniqueID -> biclique
    map<int,Biclique> bicliques;
    //mapping of links to bicliques

    //term ID -> primary term name
    map<int,string> articlenames;
    //term ID -> primary term name
    map<int,string> termnames;
    //set containing all known terms
    set<int> termset;
    //temporary set containing current terms used in iteration
    set<int> currentterms;
    //reminder of largest biclique
    int max_biclique_size;
    //used to divide edge counters for bootstrap values
    int iteration_total;
    //check if names were loaded
    bool hasnames;
    //limitation on size of bicliques loaded
    int lowlimit;
    //vector containing term IDs for random access
    vector<int> termvect;
    //value to consider coloring nodes blue instead of red, default .5
    double sigvalue;
    vector<double> sigvect;

    //prefix to print out in front of terms
    string prefix;


    //mersenne twister
    boost::mt19937 gen;

    //constructor seeds random number generator
    BipartiteData(){
        //for single-threaded iterations
        gen.seed((unsigned int)time(NULL));
//        srand((unsigned int)time(NULL));
        sigvalue=.5;
        prefix="";
    }


    //Places input file into mapping of term IDs to strings
    int loadTermNames(const char* filename){
        ifstream in(filename);
        if(!in.is_open())
            return 1;
        cout<<"Loading "<<filename<<"...\n";
        hasnames=true;
        while(!in.eof()){
            string buffer;
            getline(in,buffer);
            vector<string> tok;
            Tokenize(buffer,tok,"\t\r\n");
            if(tok.size()<2)continue;
            //first name entered is the one used
            termnames.insert(pair<int,string>(atoi(tok[0].c_str()),tok[1]));
        }
        return 0;
    }

    //loads bicliques into memory
    int loadBicliques_JJ(const char* filename){
        max_biclique_size=0;
        ifstream in(filename);
        if(!in.is_open()){
            return 1;
        }
        hasnames=true;
	map<string, int> termmap;
	map<string, int> articlemap;
	int distinct_id=1;
        cout<<"Loading "<<filename<<"...\n";
        int counter=0;
        int linecounter=0;
        while(!in.eof()){
            vector<string> tokens;
            vector<string> tokens2;
            string buffer;
            getline(in,buffer);
            if(buffer.length()<1)continue;

            //reverse tokens2 and tokens to switch terms/abstracts order
            Tokenize(buffer,tokens2,"\t");
            getline(in,buffer);
            Tokenize(buffer,tokens,"\t");

            Biclique b;

            //use if wanting to limit the size of bicliques allowed
//            if((int)tokens.size()<lowlimit)continue;

            //get term IDs
            for(int i=0;i<(int)tokens.size();i++){
                //int t = atoi(tokens[i].c_str());
                int t = -1;
		if( termmap.find(tokens[i])==termmap.end() ) {
		  t = distinct_id++;
		  termmap.insert(make_pair(tokens[i], t));
		  termnames.insert(make_pair(t, tokens[i]));
		} else {
		  t = termmap[ tokens[i] ];
		}

                b.terms.insert(t);
                termset.insert(t);
                termvect.push_back(t);
            }

            //get article IDs
            for(int i=0;i<(int)tokens2.size();i++){
                int aid = -1;
		if( articlemap.find(tokens2[i])==articlemap.end() ) {
		  aid = distinct_id++;
		  articlemap.insert(make_pair(tokens2[i], aid));
		  termnames.insert(make_pair(aid, tokens2[i]));
		} else {
		  aid = articlemap[ tokens2[i] ];
		}

                b.articles.insert(aid);
		//b.articles.insert(atoi(tokens2[i].c_str()));
            }

            //update total count
            linecounter++;
            if(linecounter%100==0){
                cout<<"Biclique #"<<linecounter<<"..."<<endl;
            }
            b.id=counter;
            b.groupsize=(int)tokens.size();
            b.touched=0;

            //add new node to size group
            if(max_biclique_size<b.groupsize)
                max_biclique_size=b.groupsize;
            bicliques.insert(pair<int,Biclique>(counter,b));
            Biclique* bp = &(bicliques.find(counter)->second);
            insertIntoGroup<int,Biclique*>(bp,b.groupsize,termgroups);

            counter++;
        }
        in.close();
        cout<<"Connecting bicliques...\n";
        connectBicliques();
        cout<<"Connecting links...\n";
        connectLinks();
        return 0;
    }
    //loads bicliques into memory
    int loadBicliques(const char* filename){
        max_biclique_size=0;
        ifstream in(filename);
        if(!in.is_open()){
            return 1;
        }
        cout<<"Loading "<<filename<<"...\n";
        int counter=0;
        int linecounter=0;
        while(!in.eof()){
            vector<string> tokens;
            vector<string> tokens2;
            string buffer;
            getline(in,buffer);
            if(buffer.length()<1)continue;

            //reverse tokens2 and tokens to switch terms/abstracts order
            Tokenize(buffer,tokens2,"\t");
            getline(in,buffer);
            Tokenize(buffer,tokens,"\t");

            Biclique b;

            //use if wanting to limit the size of bicliques allowed
//            if((int)tokens.size()<lowlimit)continue;

            //get term IDs
            for(int i=0;i<(int)tokens.size();i++){
                int t = atoi(tokens[i].c_str());
                b.terms.insert(t);
                termset.insert(t);
                termvect.push_back(t);
            }

            //get article IDs
            for(int i=0;i<(int)tokens2.size();i++){
                b.articles.insert(atoi(tokens2[i].c_str()));
            }

            //update total count
            linecounter++;
            if(linecounter%100==0){
                cout<<"Biclique #"<<linecounter<<"..."<<endl;
            }
            b.id=counter;
            b.groupsize=(int)tokens.size();
            b.touched=0;

            //add new node to size group
            if(max_biclique_size<b.groupsize)
                max_biclique_size=b.groupsize;
            bicliques.insert(pair<int,Biclique>(counter,b));
            Biclique* bp = &(bicliques.find(counter)->second);
            insertIntoGroup<int,Biclique*>(bp,b.groupsize,termgroups);

            counter++;
        }
        in.close();
        cout<<"Connecting bicliques...\n";
        connectBicliques();
        cout<<"Connecting links...\n";
        connectLinks();
        return 0;
    }

    //creates DirectedLink objects from bicliques
    int connectLinks(){
        int dlcounter=0;
        //iterate through each biclique node and connect it in a new DirectedLink object
        for(map<int,Biclique>::iterator it = bicliques.begin();it!=bicliques.end();it++){
            Biclique& b = it->second;
            if(!b.children.empty()){
                for(set<Biclique*>::iterator it2 = b.children.begin();
                    it2!=b.children.end();
                    it2++){
                        DirectedLink dl;
                        dl.id=dlcounter;
                        dl.counter=0;
                        dl.start=b.id;
                        dl.end=(*it2)->id;

                        links.insert(pair<int,DirectedLink>(dlcounter,dl));
                        DirectedLink* dltemp = &(links.find(dlcounter)->second);

                        dlcounter++;
                }
            }
        }
        //add links to biclique->link list
        for(map<int,DirectedLink>::iterator it = links.begin();it!=links.end();it++){
            DirectedLink* test = &(it->second);
            insertIntoGroup<int,DirectedLink*>(test,it->second.start,bicliqueToLink);
            insertIntoGroup<int,DirectedLink*>(test,it->second.end,bicliqueToLink);
        }
        return 0;
    }

    //recursively makes biclique connections
    set<Biclique*> recursiveConnect(Biclique& b){
        set<Biclique*> children;
        set<Biclique*> nephews;
        
        //work backwards until finished
        for(int i=b.groupsize-1;i>0;i--){
            map<int,set<Biclique*> >::iterator it = termgroups.find(i);
            if(it==termgroups.end())continue;
            for(set<Biclique*>::iterator it2 = it->second.begin();it2!=it->second.end();it2++){
                Biclique& current = *(*it2);

                //check for biclique being a subset of node above
                if(is_propersubset<int>(current.terms,b.terms)){
                    if(is_disjoint<Biclique*>(children,current.parents) && is_disjoint<Biclique*>(nephews,current.parents)){
                        //if the node is somehow related, it gets added
                        current.parents.insert(&b);
                        children.insert(&current);

                        //update nephew groups (unused in this setup)
                        if(!current.touched){
                            //get child nodes for this node if it's not already done
                            set<Biclique*> btemp = recursiveConnect(current);
                            nephews.insert(btemp.begin(),btemp.end());
                        }else{
                            nephews.insert(current.children.begin(),current.children.end());
                            nephews.insert(current.nephews.begin(),current.nephews.end());
                        }
                    }
                }
            }
        }
        b.children.insert(children.begin(),children.end());
        b.nephews.insert(nephews.begin(),nephews.end());
        b.touched=1;
        children.insert(nephews.begin(),nephews.end());
        return children;
    }

    //connects biclique data together
    int connectBicliques(){
        cout<<termgroups.size()<<" size groups to connect..."<<endl;
        //start from bottom and move up, uses memoization
        for(map<int,set<Biclique*> >::iterator it = termgroups.begin();it!=termgroups.end();it++){
            if(it->first<lowlimit)continue;
            cout<<"Connecting groups of size "<<it->first<<"..."<<endl;
            for(set<Biclique*>::iterator it2 = it->second.begin();it2!=it->second.end();it2++){
                Biclique& b = *(*it2);
                if(!b.touched)
                    //process node unless already done
                    recursiveConnect(b);
            }
        }
        return 0;
    }


    //selects a subset of term IDs according to the bootstrapping rate
    int randomizeTerms(double percent){
        boost::uniform_int<> dist(0, (int)termset.size()-1);
        boost::variate_generator<boost::mt19937&, boost::uniform_int<> > roller(gen, dist);
        currentterms.clear();
        int sz = (int)termset.size();
        int amount = (int)(sz*percent);

        //randomly select a term with replacement and place it in the set
        //if selected again, a term has no extra effect on weighting
        for(int i=0;i<amount;i++){
//            int c = rand()%sz;
            int c=roller();
            currentterms.insert(termvect[c]);
        }
        return 0;
    }

    //perform bootstrapping iterations
    void iterateLinks(int amount,double percent){
        iteration_total=amount;
        for(int i=0;i<amount;i++){
            if((i+1)%50==0){
                cout<<"Iteration "<<i+1<<"..."<<endl;
            }

            //get bootstrap set
            randomizeTerms(percent);

            //generate intersections
            map<int,set<int> > combinations;
            for(map<int,Biclique>::iterator it = bicliques.begin();it!=bicliques.end();it++){
                set<int> temp;
                intersect<int>(it->second.terms,currentterms,temp);
                combinations.insert(pair<int,set<int> >(it->first,temp));
            }

            //check links for endpoint being a subset of start point
            for(map<int,DirectedLink>::iterator it = links.begin();it!=links.end();it++){
                set<int>& newterm1 = combinations.find(it->second.start)->second;
                set<int>& newterm2 = combinations.find(it->second.end)->second;

                //use is_equalset for a slightly different distribution
//                if(!newterm1.empty() && !newterm2.empty() && !is_equalset<int>(newterm1,newterm2)){
                if(!newterm1.empty() && !newterm2.empty() && is_propersubset<int>(newterm2,newterm1)){
                    it->second.counter++;
                }
            }
        }
    }

    //header for output file, dot format
    //based on output file from ODE site
    void outputDotHeader(ostream& out){
        out<<"digraph G{\n";
        out<<"  splines=true;\n";
        out<<"  epsilon=.1; maxiter=100;\n";
        out<<"  node [shape=box, style=filled, color=black, fillcolor=\"#ccffcc\", fontname=\"Helvetica, Arial, sans-serif\", fontsize=\"10px\"];\n";
        out<<"  edge [fontcolor=black, penwidth = 2];\n";
        out<<"  ranksep=2;\n";
    }

    //footer for output file
    void outputDotFooter(ostream& out){
        out<<"}\n";
    }

    //collect the nodes visible for printing (branch), depth first; breadth first needs extra structures for tracking
    //if needed, the blue-only printing can be expanded here to limit searches in the branching ahead of time
    //currently, the blue-only check happens during the threshold loops during dot file printing
    void collectNodes(Biclique& b, set<int>& inc, set<int>& resume,set<int>& used,set<int>& sizes,int low,int depth){
        //windows computer breaks call stack after 9000 recursions
        //save rest of items for a later call
        if(depth>=6000){
            resume.insert(b.id);
            return;
        }
        for(set<Biclique*>::iterator it = b.parents.begin();it!=b.parents.end();it++){
            Biclique& b2 = *(*it);
            if(inc.find(b2.id)!=inc.end())continue;
            if(b2.groupsize<low)continue;

            //mark current node before recursion
            sizes.insert(b2.groupsize);
            inc.insert(b2.id);
            used.insert(b2.id);
            collectNodes(b2,inc,resume,used,sizes,low,depth+1);
        }
        for(set<Biclique*>::iterator it = b.children.begin();it!=b.children.end();it++){
            Biclique& b2 = *(*it);
            if(inc.find(b2.id)!=inc.end())continue;
            if(b2.groupsize<low)continue;

            //mark current node before recursion
            sizes.insert(b2.groupsize);
            inc.insert(b2.id);
            used.insert(b2.id);
            collectNodes(b2,inc,resume,used,sizes,low,depth+1);
        }
    }

    //print out a branching diagram
    //lowerEndThreshold = starting point limit
    //nodeSizeThreshold = branching lower limit
    void branchOutputDot(const char* filename, int lowerEndThreshold, int nodeSizeThreshold,bool blueOnly=false){
        set<int> included;
        set<int> resume;
        set<int> used;
        set<int> sizes;
        int counter=1;
        //iterate through all size groups
        for(map<int,set<Biclique*> >::reverse_iterator it = termgroups.rbegin();it!=termgroups.rend();it++){
            if(it->first<nodeSizeThreshold)continue;
            for(set<Biclique*>::iterator it2 = it->second.begin();it2!=it->second.end();it2++){
                Biclique& b = *(*it2);
                //avoid unnecessary searches
                if(used.find(b.id)!=used.end())continue;
                cout<<"Outputting file #"<<counter<<"\n";
                included.clear();
                sizes.clear();
                sizes.insert(b.groupsize);
                included.insert(b.id);
                used.insert(b.id);

                //'used' determines available starting points, 'included' determines printable nodes
                cout<<"Collecting nodes...\n";
                collectNodes(b,included,resume,used,sizes,lowerEndThreshold,0);

                //continue from points that had too much recursion
                while(!resume.empty()){
                    Biclique& b2 = bicliques.find(*(resume.begin()))->second;
                    resume.erase(resume.begin());
                    collectNodes(b2,included,resume,used,sizes,lowerEndThreshold,0);
                }
                cout<<" Nodes collected: "<<included.size()<<"\n";
                outputDot(filename,included,counter,sizes,blueOnly);
                counter++;
            }
        }
    }

    //collects the nodes visible for printing (tree)
    void collectNodes(Biclique& b, set<int>& used, set<int>& inc,set<int>& sizes){
        for(set<Biclique*>::iterator it = b.children.begin();it!=b.children.end();it++){
            Biclique& b2 = *(*it);
            sizes.insert(b2.groupsize);
            used.insert(b2.id);
            inc.insert(b2.id);
            collectNodes(b2,used,inc,sizes);
        }
    }

    //outputs top-down walk diagrams
    //sizeThreshold = starting point limit
    void outputDot(const char* filename, int sizeThreshold,bool blueOnly=false){
        set<int> included;
        set<int> sizes;
        set<int> used;
        int counter=1;
        //iterate through all size groups
        for(map<int,set<Biclique*> >::reverse_iterator it = termgroups.rbegin();it!=termgroups.rend();it++){
            if(it->first<sizeThreshold)continue;
            for(set<Biclique*>::iterator it2 = it->second.begin();it2!=it->second.end();it2++){
                Biclique& b =*(*it2);
                //avoid unnecessary searches
                if(used.find(b.id)!=used.end())continue;
                if(counter%100==0)
                    cout<<"Outputting file #"<<counter<<"\n";
                included.clear();
                included.insert(b.id);
                used.insert(b.id);

                //'used' determines available starting points, 'included' determines printable nodes
                sizes.insert(b.groupsize);
                collectNodes(b,used,included,sizes);
                outputDot(filename,included,counter,sizes,blueOnly);
                counter++;
            }
        }
    }

    //outputs a file based on selected nodes
    //inc = nodes to check
    //sizes = size groups to print brackets for
    //checkThres = for blue-only maps
    int outputDot(const char* filename, set<int>& inc, int current,set<int>& sizes, bool checkThres = false){
        //iterate through each significant value used for thresholding
        for(int z=0;z<(int)sigvect.size();z++){
            sigvalue = sigvect[z];

            //build filename
            stringstream currentfile;
            currentfile<<filename<<"_t"<<sigvalue<<"_file_"<<current<<".dot";
            ofstream out(currentfile.str().c_str());

            if(!out.is_open()){
                cout<<"Could not open "<<currentfile.str()<<" for writing.";
                return 1;
            }

            //output header
            outputDotHeader(out);
            //walk down size groups in reverse
            for(map<int,set<Biclique*> >::reverse_iterator it=termgroups.rbegin();it!=termgroups.rend();it++){
                if(sizes.find(it->first)==sizes.end())continue;
                out<<" {rank=same;\n";
                for(set<Biclique*>::iterator it2=it->second.begin();it2!=it->second.end();it2++){
                    Biclique& b = *(*it2);

                    //check if node is included in list for display
                    if(inc.find(b.id)==inc.end())continue;


                    //check if node is above threshold if enabled
                    if(checkThres){
                        //find edge involving current biclique
                        map<int,set<DirectedLink*> >::iterator ittemp = bicliqueToLink.find(b.id);
                        if(ittemp==bicliqueToLink.end())continue;

                        set<DirectedLink*>& tempdl = ittemp->second;
                        bool found=false;

                        //check each edge attached to biclique for being above threshold
                        for(set<DirectedLink*>::iterator it0 = tempdl.begin();it0!=tempdl.end();it0++){
                            DirectedLink& dl = *(*it0);
                            if(inc.find(dl.start)==inc.end()||inc.find(dl.end)==inc.end())
                                continue;
                            if(dl.counter*1.0/iteration_total>=sigvalue){
                                found=true;
                                break;
                            }
                        }

                        //force blue only connections to print
                        if(!found)
                            continue;
                    }


                    stringstream s;
                    stringstream t;
                    //print out terms and names if available
                    for(set<int>::iterator itt = b.terms.begin();itt!=b.terms.end();itt++){
                        if(!t.str().empty()){
                            t<<"\\n";
                        }
                        //output prefix here
                        t<<prefix;
                        t<<*itt;

                        //name printing
                        if(hasnames&&termnames.find(*itt)!=termnames.end())
                            t<<":"<<termnames.find(*itt)->second;
                    }
                    //print out article count
                    t<<"\\n\\n("<<b.articles.size()<<" articles)";

                    //create dot node
                    s<<"Ph_node_"<<b.id<<" [label=\""<<t.str()<<"\"";

                    //items without parents have red rectangle
                    if(b.parents.empty())
                        s<<",color=red";
                    s<<"];\n";
                    out<<s.str();
                }
                out<<"}\n";
            }
            
            //check links for used connections
            for(map<int,DirectedLink>::iterator it = links.begin();it!=links.end();it++){
                DirectedLink& dl = it->second;
                if(inc.find(dl.start)==inc.end()||inc.find(dl.end)==inc.end())continue;
                stringstream s;

                //decimal is based on times found over total iterations
                double res = dl.counter*1.0/iteration_total;
                if(checkThres && res<sigvalue)continue;

                //print out edge definition
                s<<"Ph_node_"<<dl.start<<"->Ph_node_"<<dl.end<<" ["<<"label=\""<<res<<"\",color=";

                //the significant value threshold (.5) determines color of the edge
                if(res<sigvalue)
                    s<<"red";
                else
                    s<<"blue";
                s<<"];\n";
                out<<s.str();
            }
            outputDotFooter(out);
            out.close();
        }

        return 0;
    }

    //outputs top-down walk diagrams
    //sizeThreshold = starting point limit
    void output_PM(int sizeThreshold,bool blueOnly=false){
        set<int> included;
        set<int> sizes;
        set<int> used;
        int counter=1;
        //iterate through all size groups
        for(map<int,set<Biclique*> >::reverse_iterator it = termgroups.rbegin();it!=termgroups.rend();it++){
            if(it->first<sizeThreshold)continue;
            for(set<Biclique*>::iterator it2 = it->second.begin();it2!=it->second.end();it2++){
                Biclique& b =*(*it2);
                //avoid unnecessary searches
                if(used.find(b.id)!=used.end())continue;
                included.clear();
                included.insert(b.id);
                used.insert(b.id);

                //'used' determines available starting points, 'included' determines printable nodes
                sizes.insert(b.groupsize);
                collectNodes(b,used,included,sizes);
                output_PM(included,counter,sizes,blueOnly);
                counter++;

		// just want the first one
		// return;
            }
        }
    }
    //outputs a file based on selected nodes
    //inc = nodes to check
    //sizes = size groups to print brackets for
    //checkThres = for blue-only maps
    int output_PM(set<int>& inc, int current,set<int>& sizes, bool checkThres = false){
        //iterate through each significant value used for thresholding
        for(int z=0;z<(int)sigvect.size();z++){
            sigvalue = sigvect[z];

            //walk down size groups in reverse
            for(map<int,set<Biclique*> >::reverse_iterator it=termgroups.rbegin();it!=termgroups.rend();it++){
                if(sizes.find(it->first)==sizes.end())continue;
                for(set<Biclique*>::iterator it2=it->second.begin();it2!=it->second.end();it2++){
                    Biclique& b = *(*it2);

                    //check if node is included in list for display
                    if(inc.find(b.id)==inc.end())continue;


                    //check if node is above threshold if enabled
                    if(checkThres){
                        //find edge involving current biclique
                        map<int,set<DirectedLink*> >::iterator ittemp = bicliqueToLink.find(b.id);
                        if(ittemp==bicliqueToLink.end())continue;

                        set<DirectedLink*>& tempdl = ittemp->second;
                        bool found=false;

                        //check each edge attached to biclique for being above threshold
                        for(set<DirectedLink*>::iterator it0 = tempdl.begin();it0!=tempdl.end();it0++){
                            DirectedLink& dl = *(*it0);
                            if(inc.find(dl.start)==inc.end()||inc.find(dl.end)==inc.end())
                                continue;
                            if(dl.counter*1.0/iteration_total>=sigvalue){
                                found=true;
                                break;
                            }
                        }

                        //force blue only connections to print
                        if(!found)
                            continue;
                    }

                    //create dot node
                    cerr << b.id << endl;
                }
            }
	    // blank line between nodes and edges
	    cerr << endl;
            
            //check links for used connections
            for(map<int,DirectedLink>::iterator it = links.begin();it!=links.end();it++){
                DirectedLink& dl = it->second;
                if(inc.find(dl.start)==inc.end()||inc.find(dl.end)==inc.end())continue;

                //decimal is based on times found over total iterations
                double res = dl.counter*1.0/iteration_total;
                if(checkThres && res<sigvalue)continue;

		cerr << dl.start << "\t" << dl.end << "\t" << res << endl;
            }
	    // blank line between nodes and edges
	    cerr << endl;
        }

        return 0;
    }


    //reset counter on DirectedLink objects between iterations
    void clearLinks(){
        for(map<int,DirectedLink>::iterator it = links.begin();it!=links.end();it++){
            it->second.counter=0;
        }
    }
};

//mutex for saving values
boost::mutex simpleMutex;

/**
 * IterThread
 * 
 * Class that performs multithreaded iterations
 */
class IterThread{
public:
    IterThread(){}

    void start(){
        //starts a thread (method, class pointer) for threads inside a class
        thr=boost::thread(&IterThread::proc,this);
    }

    void join(){
        //blocks until finishing
        thr.join();
    }

    //copies information over
    void setIterations(int iter){
        iterlimit=iter;
    }

    //connect pointers to data
    void attachData(map<int,Biclique>* b,map<int,DirectedLink>* l,set<int>* t,double p,unsigned int startdata){
        bicliques = b;
        links = l;
        percent=p;
        termset = t;
        //set up vector for random access
        for(set<int>::iterator i = termset->begin();i!=termset->end();i++){
            termvect.push_back(*i);
        }
        starttime=startdata;
    }
    void proc(){
        //mersenne twister with a distribution of 0-(size of terms-1)
        boost::mt19937 gen(starttime);
        boost::uniform_int<> dist(0, (int)termset->size()-1);
        boost::variate_generator<boost::mt19937&, boost::uniform_int<> > roller(gen, dist);
//        srand(stime);
        stringstream t;
        t<<"Proc "<<id<<" starting...\n";
        cout<<t.str();

        set<int> currentterms;
        int sz = (int)(termset->size()*percent);

        //maintain separate accounts of counters changing
        map<int,int> linktotal;
        //perform intersections and store them
        map<int,set<int> > combinations;
        for(int i=0;i<(int)links->size();i++){
            linktotal.insert(pair<int,int>(i,0));
        }
        for(int i=0;i<(int)bicliques->size();i++){
            set<int> temp;
            combinations.insert(pair<int,set<int> >(i,temp));
        }

        for(int i=0;i<iterlimit;i++){
            //print out line without mutex
            if((i+1)%50==0){
                stringstream s;
                s<<id<<": Iteration "<<i+1<<"...\n";
                cout<<s.str();
            }

            //reset random subset
            currentterms.clear();

            //create bootstrap list
            for(int i = 0;i<sz;i++){
//                int temp = rand()%((int)termset->size());
                int temp=roller();
                currentterms.insert(termvect[temp]);
            }

            //intersect all nodes with bootstrap list
            for(map<int,Biclique>::iterator it = bicliques->begin();it!=bicliques->end();it++){
                map<int,set<int> >::iterator it2 = combinations.find(it->first);
                it2->second.clear();
                intersect<int>(it->second.terms,currentterms,it2->second);
            }

            //check each connection for remaining valid groups
            for(map<int,DirectedLink>::iterator it = links->begin();it!=links->end();it++){
                set<int>& newterm1 = combinations.find(it->second.start)->second;
                set<int>& newterm2 = combinations.find(it->second.end)->second;
                //if endpoint is a proper subset of startpoint, increment counter

                //use is_equalset for a slightly different distribution
//                if(!newterm1.empty() && !newterm2.empty() && !is_equalset<int>(newterm1,newterm2)){
                if(!newterm1.empty() && !newterm2.empty() && is_propersubset<int>(newterm2,newterm1)){
                    linktotal.find(it->first)->second++;
                }
            }
        }

        //update main link counters after all iterations complete
        simpleMutex.lock();
        for(map<int,DirectedLink>::iterator it = links->begin();it!=links->end();it++){
            map<int,int>::iterator it2 = linktotal.find(it->first);
            it->second.counter+=it2->second;
        }
        simpleMutex.unlock();

        t.str("");
        t<<"Proc "<<id<<" finishing ("<<iterlimit<<")\n";
        cout<<t.str();
    }

    //seed time
    unsigned int starttime;

    //random access of term set
    vector<int> termvect;

    //pointer to biclique (read-only implied)
    map<int,Biclique>* bicliques;

    //pointer to links (mutex used for writing)
    map<int,DirectedLink>* links;

    //pointer to terms (read-only implied)
    set<int>* termset;

    //iteration data
    double percent;
    int iterlimit;

    //thread reference
    boost::thread thr;

    //thread id
    int id;
};

#endif
