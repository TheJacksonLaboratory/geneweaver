
#include <vector>
#include <set>
#include <unordered_map>
//this stores all the strings in the interest set in a map, making this a hashmap allows constant time lookup
//of if a string is in the iterestset, so for any set, to find the intersect with the interest set, just iterate over each
//element in the set to see if it is in this map, allowing intersections to be done in linear time
template<typename T>
class IntersectSizeFinder{
    public:
        /*
        every intersection done in mset is 
        intersect(<something>,set-of-interest)
        therefore the set of interest can be set up and just referenced to each time
        an intersect is needed. 

        the constructor here initializes the class with the set-of-interest's data
        */
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
        /*
         * to find the intersect with the map already set up, we just need to loop over
         * the collection and for each element, check the map to see if it's also in the 
         * set of interest, meaning it's in both, so it's part of the intersection
         * 
         * this function does the actual full intersect and returns a vector of the
         * intersection elements
         */
        template<typename Iterator>
        std::vector<T> getIntersectionWith(Iterator beginIterator, Iterator endIterator){
            std::vector<T> toReturn;
            for(;beginIterator!=endIterator;beginIterator++){
                if(intersectCheck[*beginIterator]){
                    toReturn.push_back(*beginIterator);
                }
            }
            return toReturn;
        }

    private:
        /*
        we store all the genes from the set of interest in a hash map which hashes the gene to a bool
        since every intersection is with set of interest, this only needs to be done once at the instanciation
        of the class
        */
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
        /* unordered map is a c++11 stl implementation of a hash map,
         * using this instead of just map saves 3 seconds, because stl map
         * uses a red black tree, so it performs in logN versus the near constant
         * time of a hash map
         */
        std::unordered_map<T,bool> intersectCheck;//bool defaults to false
};


