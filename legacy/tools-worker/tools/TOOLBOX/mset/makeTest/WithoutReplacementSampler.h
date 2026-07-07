#include <vector>
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <random>
template<typename T>
class WithoutReplacementSampler{
    public:
        WithoutReplacementSampler(){
            gen=std::mt19937(rd());
        }
        void setSource(std::vector<T>* from){
            ndxs=std::vector<unsigned long>(from->size());
            for(unsigned long i=0;i<ndxs.size();i++){
                ndxs[i]=i;
            }
            fromVector=from;
        }
    //without replacement
    void sample(std::vector<T>& sampleInto){
        shuffle(ndxs.begin(),ndxs.end(),gen);
        for(unsigned long i=0;i<sampleInto.size();i++){
            sampleInto[i]=(*fromVector)[ndxs[i]];//copy the random element
        }
    }
    private:
        std::random_device rd;
        std::mt19937 gen;
        std::vector<T>* fromVector;
        std::vector<unsigned long> ndxs;
};
