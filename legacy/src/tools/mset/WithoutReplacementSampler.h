#include <vector>
#include <algorithm>
#include <cstdlib>
#include <ctime>
template<typename T>
class WithoutReplacementSampler{
    public:
        WithoutReplacementSampler(){
            srand(time(0));
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
        random_shuffle(ndxs.begin(),ndxs.end());
        for(unsigned long i=0;i<sampleInto.size();i++){
            sampleInto[i]=(*fromVector)[ndxs[i]];//copy the random element
        }
    }
    private:
        std::vector<T>* fromVector;
        std::vector<unsigned long> ndxs;
};
