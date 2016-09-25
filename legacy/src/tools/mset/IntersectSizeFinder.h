
#include <vector>
#include <set>
#include <map>
//this stores all the strings in the interest set in a map, making this a hashmap allows constant time lookup
//of if a string is in the iterestset, so for any set, to find the intersect with the interest set, just iterate over each
//element in the set to see if it is in this map, allowing intersections to be done in linear time
template<typename T>
class IntersectSizeFinder{
    public:
        template<typename Iterator>
        IntersectSizeFinder(Iterator beginIterator, Iterator endIterator){
            initializeMap(beginIterator,endIterator);
        }
        int getIntersectionSizeWith(std::set<T>& me){
            return intersectSizeWith(me.begin(),me.end());
        }
        int getIntersectionSizeWith(std::vector<T>& me){
            return intersectSizeWith(me.begin(),me.end());
        }

    private:
        //initializes the 
        template<typename Iterator>
        void initializeMap(Iterator beginIterator,Iterator endIterator){
            for(;beginIterator!=endIterator;beginIterator++){
                intersectCheck[*beginIterator]=true;
            }
        }
        //finds the size of the intersect with the setOfInterest using the precomputed checking map
        template<typename Iterator>
        int intersectSizeWith(Iterator beginIterator, Iterator endIterator){
            int toReturn=0;
            for(;beginIterator!=endIterator;beginIterator++){
                if(intersectCheck[*beginIterator]){
                    toReturn++;
                }
            }
            return toReturn;
        }
        std::map<T,bool> intersectCheck;//bool defaults to false
};


