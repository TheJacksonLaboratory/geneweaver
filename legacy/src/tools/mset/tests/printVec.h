
#include<iostream>
#include<vector>
template<typename T>
void printVec(std::vector<T>& v){
    for(unsigned int i=0;i<v.size();i++){
        std::cout<<" "<<v[i];
    }
    std::cout<<std::endl;
}
