
#include<iostream>
#include<vector>
#include<set>
template<typename T>
std::ostream& operator<<(std::ostream& os,std::vector<T>& v){
    for(unsigned int i=0;i<v.size();i++){
        if(i==0){
            os<<"[";
        }else{
            os<<", ";
        }
        os<<v[i];
    }
    os<<"]";
    return os;
}

template<typename T>
std::ostream& operator<<(std::ostream& os,std::set<T>& v){
    typename std::set<T>::iterator i=v.begin();
    for(;i!=v.end();i++){
        if(i==v.begin()){
            os<<"{";
        }else{
            os<<", ";
        }
        os<<*i;
    }
    os<<"}";
    return os;
}
