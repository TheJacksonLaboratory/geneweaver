#include <vector>
#include <algorithm>
#include <cstdlib>
#include <ctime>
#include <random>
#include <iostream>
/*
 * this class holds the state of the rng and the function to use it to sample 
 * into a given vector
 *
 * unfortunately, since each successive sample changes the state of the rng,
 * they cant be pulled in parrallel if the probability is to match the R implementation
 */
template<typename T>
class WithoutReplacementSampler{
    public:
        WithoutReplacementSampler(){
            /* mt19937 is a c++11 addition to random that implements
             * the mersenne twister random engine used in R as the default number generator
             *
             * it just so happens that the same configuration parameters used in R's mt engine
             * are the default arguments for mt19937
             */
            gen=std::mt19937(rd());
        }

        void setSource(std::vector<T>* from){
            fromVector=from;
            ndxs=std::uniform_int_distribution<unsigned long>(0,fromVector->size()-1);
        }
    //this is currently sampling with replacement, but doing so is an order of magnitude
    //faster than without, and didn't seem to affect the probabilities in a significant way
    void sample(std::vector<T>& sampleInto){
        //*//with replacement
        for(unsigned long i=0;i<sampleInto.size();i++){
            unsigned long pull=ndxs(gen);
            sampleInto[i]=(*fromVector)[pull];
        }
        /*///without replacement
        for(unsigned long i=0;i<sampleInto.size();i++){
            unsigned long pull=std::uniform_int_distribution<unsigned long>{0,sampleInto.size()-i-1}(gen);
            sampleInto[i]=(*fromVector)[pull];
            //swap pulled element and the element at 1 more than the sample out
            //of range
            T temp=(*fromVector)[pull];
            (*fromVector)[pull]=(*fromVector)[fromVector->size()-i-1];
            (*fromVector)[fromVector->size()-i-1]=temp;
        }
        //*/
    }
    private:
        std::random_device rd;
        std::mt19937 gen;
        std::vector<T>* fromVector;
        std::uniform_int_distribution<unsigned long> ndxs;
};
