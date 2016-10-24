#include <vector>
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <random>
#include <iostream>
template<typename T>
class WithoutReplacementSampler{
    public:
        WithoutReplacementSampler(){
            gen=std::mt19937(rd());
        }
        void setSource(std::vector<T>* from){
            fromVector=from;
            std::cout<<fromVector->size()<<std::endl;
            ndxs=std::uniform_int_distribution<unsigned long>(0,fromVector->size());
        }
    //without replacement
    void sample(std::vector<T>& sampleInto){
        for(unsigned long i=0;i<sampleInto.size();i++){
            unsigned long pull=ndxs(gen);
            sampleInto[i]=(*fromVector)[pull];
        }
    }
    private:
        std::random_device rd;
        std::mt19937 gen;
        std::vector<T>* fromVector;
        std::uniform_int_distribution<unsigned long> ndxs;
};
