#include <vector>
#include <set>
//if its not in the set, add it to the return vector
//and the set
//
//allows returned vector to have unique elements in the same order as the
//original
template<typename T>
void unique(std::vector<T>& toUnorderedSet){
    std::set<T> checkWith;
    std::vector<T> toReturn;
    unsigned int index=0;
    for(unsigned int i=0;i<toUnorderedSet.size();i++){
        if(checkWith.find(toUnorderedSet[i])==checkWith.end()){
            checkWith.insert(toUnorderedSet[i]);
            toUnorderedSet[index]=toUnorderedSet[i];
            index++;
        }
    }
    toUnorderedSet.resize(index);
}
