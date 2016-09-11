/*
mset.cpp: test making a c++ equivalent of R's match function
Created: Wed Sep  7 10:43:48 CDT 2016
*/
#include <iostream>
#include <ctime>
#include <vector>
#include <cstdlib>

template<typename T>
void printVec(std::vector<T>& v){
    if(v.size()>0){
        std::cout<<"c("<<v[0];
        for(int i=1;i<v.size();i++){
            std::cout<<","<<v[i];
        }
        std::cout<<")";
    }
}

template<typename T>
void printResVec(std::vector<T>& v){
    if(v.size()>0){
        if(v[0]==-1){
            std::cout<<"NA";
        }else{
            std::cout<<v[0];
        }
        for(int i=1;i<v.size();i++){
            std::cout<<" ";
            if(v[i]==-1){
                std::cout<<"NA";
            }else{
                std::cout<<v[i];
            }
        }
    }
}
template<typename T>
std::vector<int> match(std::vector<T>& findNdxOf, std::vector<T>& findIn){
    std::vector<int> toReturn;
    for(unsigned int i=0;i<findNdxOf.size();i++){
        int j=0;
        bool found=false;
        while(!found&&j<findIn.size()){
            if(findNdxOf[i]==findIn[j]){
                found=true;
            }
            j++;
        }
        if(!found){
            j=-1;
        }
        toReturn.push_back(j);
    }
    return toReturn;

}
std::vector<int> randomIntVec(){
    std::vector<int> toReturn;
    for(int i=0;i<rand()%20+1;i++){
        toReturn.push_back(rand()%20);
    }
    return toReturn;
}



int main(int argc, char** argv){
    srand(time(0));
    /*
    int init1[]={11,4,19,15,17,14,4};
    int init1size=sizeof(init1)/sizeof(int);
    int init2[]={9,18,13,14,6,15};
    int init2size=sizeof(init2)/sizeof(int);
    std::vector<int> matchFrom(init1,init1+init1size);
    std::vector<int> toMatch(init2,init2+init2size);
    /*/
    std::vector<int> matchFrom=randomIntVec();
    std::vector<int> toMatch=randomIntVec();
    //*/
    std::vector<int> result=match(matchFrom,toMatch);
    std::cout<<"match(";
    printVec(matchFrom);
    std::cout<<",";
    printVec(toMatch);
    std::cout<<"); ";
    std::cout<<"print('";
    printResVec(result);
    std::cout<<"')"<<std::endl;
    
    return 0;
}
