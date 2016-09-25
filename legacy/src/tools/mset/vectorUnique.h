#include <vector>
#include <set>
//if its not in the set, add it to the return vector
//and the set
//
//allows returned vector to have unique elements in the same order as the
//original
template<typename T>
std::vector<T> unique(std::vector<T>& toUnorderedSet){
    std::set<T> checkWith;
    std::vector<T> toReturn;
    for(unsigned int i=0;i<toUnorderedSet.size();i++){
        if(checkWith.find(toUnorderedSet[i])==checkWith.end()){
            checkWith.insert(toUnorderedSet[i]);
            toReturn.push_back(toUnorderedSet[i]);
        }
    }
    return toReturn;
}
