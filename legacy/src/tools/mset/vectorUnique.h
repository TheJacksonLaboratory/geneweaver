#include <vector>
#include <set>
/*if its not in the set, add it to the return vector and the set

this allows returned vector to have unique elements in the same order as the
original

this was then changed to be inplace by overwriting the element at the current
uniquedIndex
*/
template<typename T>
void unique(std::vector<T>& toUnorderedSet){
    std::set<T> checkWith;
    std::vector<T> toReturn;
    unsigned int uniquedIndex=0;
    for(unsigned int i=0;i<toUnorderedSet.size();i++){
        if(checkWith.find(toUnorderedSet[i])==checkWith.end()){
            checkWith.insert(toUnorderedSet[i]);
            toUnorderedSet[uniquedIndex]=toUnorderedSet[i];
            uniquedIndex++;
        }
    }
    /* after running the algorithm, uniquedIndex is one more than
     * the last element, which convieniently is the new size we need
     */
    toUnorderedSet.resize(uniquedIndex);//resize truncates the original vector
}
/*sample trace through of algorithm for an array int[]={3,2,3,4,1,1};
 *
 *
element at i not in set, copy it to the element at u and add it, then increment u
vector:
 i
 v
[3][2][3][4][1][1]
 ^
 u
set:
{}


element at i not in set, copy it to the element at u and add it, then increment u
vector:
    i
    v
[3][2][3][4][1][1]
    ^
    u
set:
{3}


element at i already in set
vector:
       i
       v
[3][2][3][4][1][1]
       ^
       u
set:
{2,3}


element at i not in set, copy it to the element at u and add it, then increment u
vector:
          i         |>              i         
          v         |>              v         
[3][2][4][4][1][1]  |>    [3][2][4][4][1][1]  
       ^            |>              ^            
       u            |>              u            
set:                |>    set:                
{2,3,4}             |>    {2,3,4}             


element at i not in set, copy it to the element at u and add it, then increment u
vector:
             i      |>                 i         
             v      |>                 v         
[3][2][4][1][1][1]  |>    [3][2][4][1][1][1]  
          ^         |>                 ^            
          u         |>                 u            
set:                |>    set:                
{1,2,3,4}           |>    {1,2,3,4}             


element at i already in set
vector:
             i
             v
[3][2][4][1][1][1]
             ^
             u
set:
{1,2,3,4}


element at i already in set
vector:
                i
                v
[3][2][4][1][1][1]
             ^
             u
set:
{1,2,3,4}

now were done, just chop off from u on
[3][2][4][1][1][1] >> [3][2][4][1]
*/
