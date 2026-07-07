#include <string>
#include <map>
#include <omp.h>
#include <iostream>
#include <fstream>
#include <cstring>
#include <cstdlib>
#include "include/CsMset.h"

int main(int argc, char* argv[]) {

    // Check the number of parameters
    if (argc < 6) {
        // Tell the user how to run the program (just incase we forget).
        std::cerr << "Usage: "
                  << argv[0]
                  << " NUM_TRIALS LIST_1 1_BACKGROUND LIST_2 2_BACKGROUND [-U, --under, -O, --over]"
                  << std::endl;
        return 1;
    }

    // Get Command Line Arguments. We can keep it simple since we're also writing the interfacing program.
    std::istringstream ss(argv[1]);
    int NUM_TRIALS;
    if (!(ss >> NUM_TRIALS)) {
        std::cerr << "Invalid number of trials: " << argv[1] << '\n';
    } else if (!ss.eof()) {
        std::cerr << "WARNING: Trailing characters after number of trials ignored: " << argv[1] << '\n';
    }
    std::string list_1_path            = argv[2];
    std::string list_1_background_path = argv[3];
    std::string list_2_path            = argv[4];
    std::string list_2_background_path = argv[5];

    // Optional final argument to specify representation type (over/under)
    bool USE_OVER_REPRESENTATION = true;
    if (argc > 6) {
        // bool will be true if the input matches either string (short or long input)
        bool user_input_over  = (strncmp(argv[6],"--over",15) == 0 || strncmp(argv[6],"-O",5) == 0);
        bool user_input_under = (strncmp(argv[6],"--under",15) == 0 || strncmp(argv[6],"-U",5) == 0);
        if (user_input_over){
            USE_OVER_REPRESENTATION = true;
        } else if (user_input_under){
            USE_OVER_REPRESENTATION = false;
        } else {
            std::cerr << "Over/Under argument must be either -O/--over or -U/--under" << std::endl;
            return 1;
        }
    }
    bool PRINT_TO_CLI = false;
    if (argc > 7) {
        PRINT_TO_CLI = (strncmp(argv[7],"--cli",15) == 0 || strncmp(argv[7],"-C",5) == 0);
    }

    // Read Input Files
    std::vector<std::string> list_1_pre     = mset_files::read_sort_unique (list_1_path);
    std::vector<std::string> list_1_b       = mset_files::read_sort_unique (list_1_background_path);
    std::vector<std::string> list_2_pre     = mset_files::read_sort_unique (list_2_path);
    std::vector<std::string> list_2_b       = mset_files::read_sort_unique (list_2_background_path);

    // Calculate The Universe
    std::vector<std::string> universe;
    std::set_intersection(
            list_2_b.begin(), list_2_b.end(),
            list_1_b.begin(), list_1_b.end(),
            back_inserter(universe)
            );
    mset_files::sort_unique (universe);

    // Find list_1 in Universe
    std::vector<std::string> list_1;
    std::set_intersection(
            list_1_pre.begin(), list_1_pre.end(),
            universe.begin(), universe.end(),
            back_inserter(list_1));

    // Find list_2 in Universe
    std::vector<std::string> list_2;
    std::set_intersection(
            list_2_pre.begin(), list_2_pre.end(),
            universe.begin(), universe.end(),
            back_inserter(list_2));

    // We now know the correct sizes of each data set
    long list_2_size            = list_2.size();
    long list_1_size            = list_1.size();
    long universe_size          = universe.size();
    long comp_intersect_size    = mset_tools::intersection_size(list_2, list_1);

    // Let's keep track of some runtime parameters so we can report them later
    std::map<std::string, std::string> mset_output;
    mset_output["List 1 Size"]          = std::to_string(list_2_size);
    mset_output["List 2 Size"]          = std::to_string(list_1_size);
    mset_output["Universe Size"]        = std::to_string(universe_size);
    mset_output["List 1 / Universe"]    = std::to_string(list_2_size);
    mset_output["List 2 / Universe"]    = std::to_string(list_1_size);
    mset_output["List 1/2 Intersect"]   = std::to_string(comp_intersect_size);
    mset_output["Num Trials"]           = std::to_string(NUM_TRIALS);
    mset_output["Alternative"]          = ((USE_OVER_REPRESENTATION)? "Greater" : "Less");
    mset_output["Method"]               = ((USE_OVER_REPRESENTATION)? "Over" : "Under");

    if (mset_tools::intersection_size(list_2_pre, list_2_b) != list_2_pre.size()) {
        std::cerr << "list_2 not subset of its background" << std::endl;
        return 1;
    } else if (mset_tools::intersection_size(list_1_pre, list_1_b) != list_1_pre.size()){
        std::cerr << "list_1 not subset of its background" << std::endl;
        return 1;
    } else {
        // The trials array keeps track of the size of the intersect of the two sample datasets
        int *trials = new int[NUM_TRIALS];

        // Begin OpenMP Parallel code section. Each process will execute the contents of the closure on it's own
        // e.g. with four processes, there will be four list_2_s arrays, but still only one trials array.
        #pragma omp parallel
        {
            int *list_2_s = new int[list_2_size];
            int *list_1_s  = new int[list_1_size];

            // Populate the trials array with the results of each trial
            // 'omp for' divides up the work between the available processes
            #pragma omp for
            for(int i=0; i < NUM_TRIALS; i++){
                // Find the intersect size of a sampled list_1 and sampled list_2
                trials[i] = (mset_tools::trial (list_1_s, list_2_s, list_1_size, list_2_size, universe_size));
            }
            delete []list_1_s;
            delete []list_2_s;
        }
        // To find the number of trials with at least as large an intersect as our comparison, we first need to sort
        std::sort(trials, trials+NUM_TRIALS);

        // The number of trials above `comp_intersect_size` is the total number of trials minus the index of the
        // first element not lower than `comp_intersect_size` (index of el is the number of elements before el)
        int above = (int)(NUM_TRIALS - (std::lower_bound(trials, trials+NUM_TRIALS, comp_intersect_size) - trials));

        // Our p-value calculation changes depending on which representation type is used
        float pvalue;
        if (USE_OVER_REPRESENTATION) {
            pvalue = above / ((float)NUM_TRIALS);
        } else {
            pvalue = (NUM_TRIALS - above) / ((float)NUM_TRIALS);
        }

        // Produce a histogram of the sizes of sample intersections
        std::map<int, double> hist;
        mset_cli::create_hist(hist, trials, NUM_TRIALS);

        mset_output["Trials gt intersect"]  = std::to_string(above);
        mset_output["P-Value"]              = std::to_string(pvalue);
        mset_files::write_to_file(mset_output, "mset_output.tsv");
        mset_files::write_to_file(hist, "mset_hist.tsv");

        if (PRINT_TO_CLI) {
            mset_cli::print_output(mset_output);
            mset_cli::print_hist(hist);
        }

        delete []trials;

        return 0;
    }
}
