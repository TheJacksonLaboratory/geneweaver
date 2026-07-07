//
// Created by Alexander Berger on 9/12/18.
//
#include <string>
#include <random>
#include <cmath>
#include <algorithm>
#include <stdio.h>
#include <cstdio>
#include <iomanip>
#include <iostream>
#include <fstream>
#include <map>

#ifndef MSETCPP_CS_MSET_H
#define MSETCPP_CS_MSET_H

namespace mset_tools
{
    // A counter to keep track of our intersect size
    struct Counter
    {
        struct value_type { template<typename T> value_type(const T&) { } };
        void push_back(const value_type&) { ++count; }
        size_t count = 0;
    };

    // Calculates the size of the intersect of two containers without saving that intersect to memory
    // The containers to compare must both have the .begin() and .end() methods implemented
    template<typename T1, typename T2>
    size_t intersection_size(const T1& s1, const T2& s2)
    {
        Counter c;
        set_intersection(s1.begin(), s1.end(), s2.begin(), s2.end(), std::back_inserter(c));
        return c.count;
    }

    // Exactly like `intersection_size` except for use on arrays
    inline size_t intersection_size_arr(const int *arr_1, const long arr_1_size, const int *arr_2, const long arr_2_size)
    {
        Counter c;
        set_intersection(arr_1, arr_1 + arr_1_size, arr_2, arr_2 + arr_2_size, std::back_inserter(c));
        return c.count;
    }

    // Uniformly samples from the universe without replacement to create a data set of size `sample_size`
    // arr is modified in place by overwriting its contents with a new sample.
    //
    // @param arr: A pointer to the int array to overwrite. arr should be allocated prior to calling and should be at
    //              least of size sample_size.
    // @param sample_size: The size of the array
    // @param universe_size: The size of the population to sample from
    // @return void: The results are stored in arr
    inline void overwrite_with_sample(int *arr, long sample_size, long universe_size)
    {
        std::random_device r;
        // We use mt19937 to stay consistent with the previous c++ and R implementations of MSET
        // TODO: We should have a better justification for our decision on random engine
        std::mt19937 gen { r() };

        for(int i = 0; i < sample_size; i++){
            // The size of our uniform distribution is the `sample_size` minus the number of times we've already sampled
            std::uniform_int_distribution<int> distribution(0, universe_size-1-i);
            // Pick a value from out distribution
            int val = distribution(gen);
            // J keeps track of which array index we're comparing to
            int j;
            for(j = 0; j < i; j++){
                // If the value of the array at the `j` is greater than our pick, the pick should be inserted at the `j`
                if(arr[j] > val) {
                    // Move everything after the `j` over by one
                    for(int k=i; k > j; k--){
                        arr[k] = arr[k-1];
                    }
                    break;
                }
                // For values that are smaller than our pick, we need to increase the pick value by 1
                // This corrects for the shrinking distribution size as `i` approaches the sample_size
                else { val += 1; }
            }
            // Insert our picked value at `j`
            arr[j] = val;
        }
    }

    // Generate two sampled datasets on the _s arrays and return the size of their intersect
    //
    // @param arr_1: a pointer to an int array of size arr_1_size
    // @param arr_2: a pointer to an int array of size arr_2_size
    // @param arr_1_size: the size of arr_1
    // @param arr_2_size: the size of arr_2
    // @param u_size: The size of the universe, AKA the size of the population we sample from
    // @return int: The size of the intersect of sampled arr_1 and arr_2
    inline int trial(int* arr_1, int* arr_2, long arr_1_size, long arr_2_size, long u_size) {
        overwrite_with_sample(arr_1, arr_1_size, u_size);
        overwrite_with_sample(arr_2, arr_2_size, u_size);
        return int(intersection_size_arr(arr_1, arr_1_size, arr_2, arr_2_size));
    }
}

namespace mset_files
{
    // Convert a string to upper case and remove newline characters
    inline void toUpper(std::string& input){
        std::transform(input.begin(), input.end(), input.begin(), toupper);
        if(input[input.size()-1]=='\n'){
            input.erase(input.size()-1,1);
        }
    }

    // Removes duplicates from a vector
    inline void sort_unique(std::vector<std::string>& vec){
        sort(vec.begin(), vec.end());
        vec.erase(std::unique(vec.begin(), vec.end()), vec.end());
    }

    // Reads the contents of a file located at `path`, converts to upper case, sorts, and removes duplicates
    std::vector<std::string> read_sort_unique(std::string& path){
        std::ifstream ifs(path.c_str());
        std::vector<std::string> contents;
        if(!ifs){
            exit(1);
        }
        std::string input;
        while (getline(ifs, input)) {
            toUpper(input);
            contents.push_back(input);
        }
        sort_unique(contents);
        return contents;
    }
    inline void write_to_file(std::map<std::string, std::string>& output, std::string path){
        std::ofstream outfile;
        std::cout << path.c_str() << std::endl;
        outfile.open(path.c_str(), std::ofstream::out);

        if (outfile) {
            for (auto p : output) {
                outfile << p.first.c_str() << "\t" << p.second.c_str() << "\n";
            }
            outfile.close();
        } else {
            std::cout << "Error opening output file";
        }
    }

    inline void write_to_file(std::map<int, double>& output, std::string path){
        std::ofstream outfile;
        outfile.open(path.c_str(), std::ofstream::out);
        
        if (outfile) {
            for (auto p : output) {
                outfile << p.first << "\t" << p.second << "\n";
            }
            outfile.close();
        } else {
            std::cout << "Error opening output file";
        }
    }
}

namespace mset_cli
{
    // Return a histogram of the ratio of occurrence for each intersect size
    void create_hist(std::map<int, double> & hist, const int *trials, int NUM_TRIALS){
        // Count the number of times we see each intersect size
        for (int i=0; i < NUM_TRIALS; i++) {
            ++hist[trials[i]];
        }
        // Divide each total amount seen by the total number of trials
        for (auto p : hist){
            hist[p.first] = p.second / (double)NUM_TRIALS;
        }
    }

    void print_hist(std::map<int,double>& hist){
        std::cout << std::endl
                  << std::endl
                  << "Sizes of Sample Intersects:"
                  << std::endl;
        for (auto p : hist) {
            std::cout << std::fixed << std::setprecision(1) << std::setw(2)
                      << p.first << ' ' << std::string(unsigned(p.second/0.004),'*') << '\n';
        }
    }

    void print_output(std::map<std::string, std::string>& outputs){
        for (auto p : outputs) {
            std::cout << std::fixed << std::setprecision(1) << std::setw(20)
                      << p.first << "\t" << p.second << std::endl;
        }
    }
}
#endif //MSETCPP_CS_MSET_H
