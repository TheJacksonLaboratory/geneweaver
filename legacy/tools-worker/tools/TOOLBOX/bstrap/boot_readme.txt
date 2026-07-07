===========================================================================
Bootstrapper
===========================================================================
Written by Daniel Morillo
Date: Dec. 16, 2010

Originally made for analyzing MP term to abstract relations.

===========================================================================
Dependencies
===========================================================================
C++ Boost library (uses extra string functions (boost::algorithm) and random generators)
- Thread library (boost::thread) requires compiling on current platform
-- Pthreads is required for Linux machines, Boost uses Windows threading API in Windows

===========================================================================
Command line usage
===========================================================================

Bootstrapper.exe <bicliqueFile> <outputName> [options]

The <bicliqueFile> is organized in this manner:
<termNumber>(tab)<abstractNumber>
The first number indicates the group (geneset). The second indicates a member of the group (gene).

The <outputName> is the base portion of the filename at the beginning of every file. Iteration options will add other tags to differentiate files.
Ex: 'Bootstrapper.exe inputFile abc -i "100 .25 -print -1"' will create files of the format:
abc_100_0.25_p0_t0.5_file_1.dot
abc represents the <outputName>
100 represents the current iteration set (100)
0.25 represents the current sampling rate (.25)
p0 represents the current printout set (-print -1 is the first and only listed here. Adding another print option would have the second set print out as 'p1'.
t0.5 represents the threshold value for determining blue-colored edges. This can be changed with the -sig option.
file_1 represents the current file created from the bootstrapped data.


===========================================================================
Misc. files
===========================================================================

mpbiclique is a file containing bicliques from the bootstrap research project. There are about 18,000 and can be used to run in the bootstrapper.
mptermnames is a file containing the names for the terms referenced in the mpbiclique file.

===========================================================================
Options
===========================================================================

---------------------------------------------------------------------------
Multithreading
---------------------------------------------------------------------------
Threading will default to 1 if it cannot identify the amount of CPUs present. Otherwise, the maximum count will be used by default.

-t <numberThreads>
Forces the multithreading algorithm to use <numberThreads> amount of threads when performing iterations. Only the iteration handler is multithreaded. The program will try to guess CPU amounts with the Boost library. A single CPU will not create a separate thread from the main program.


---------------------------------------------------------------------------
Main Actions
---------------------------------------------------------------------------
The program will exit early if no iteration amounts are specified.


-i "<iterationAmount> <percentAmount> [iterationAmount2 percentAmount2...]"
Sets up the bootstrapper to perform the amount of iterations (<iterationAmount>) specified, with a <percentAmount> sampling rate. An input of "100 .75" would perform 100 iterations at 75% sampling rate. An input of "1000 .25 1000 .5 1000 .75" would perform 1000 iterations over each of the different sampling rates in different runs.


---------------------------------------------------------------------------
Output formatting
---------------------------------------------------------------------------

-prefix <prefixString>
Inserts a prefix to the ID number printed out in each node for each item. "-prefix MPTerm" would add MPTerm to each ID number in the term list inside a biclique node: '296' 
would become 'MPTerm296'.

-name <filename>
Provides a file with names to apply to the items inside the biclique nodes. The file is in the format "<termID/genesetID>(tab)<name>" on each line. If the name is unavailable for a specific item, it will be left blank.
Ex:
Naming file contains '296(tab)misc phenotype'
The term ID in the finished graph will contain "296:misc phenotype" in its rectangle.

-sig "<value> [<value2> <value3> <value4>...]"
Changes the threshold requirement for coloring edges blue in the graph printout. Valid values range between 0-1. Specifying multiple values (in quotes to keep them together) will create a file for each threshold for each file in the printout run, therefore creating:
abc_100_0.25_p0_t0.4_file_1.dot
abc_100_0.25_p0_t0.5_file_1.dot
abc_100_0.25_p0_t0.6_file_1.dot
if -sig ".4 .5 .6" was used. Each file printed would have 3 versions of itself: the .4, .5, and .6 versions. This 3 version multiplier stacks with the multiple files produced from the print options below.
Ex:
abc_100_0.25_p0_t0.4_file_1.dot
abc_100_0.25_p0_t0.5_file_1.dot
abc_100_0.25_p0_t0.6_file_1.dot
abc_100_0.25_p0_t0.4_file_2.dot
abc_100_0.25_p0_t0.5_file_2.dot
abc_100_0.25_p0_t0.6_file_2.dot


---------------------------------------------------------------------------
Output modes
---------------------------------------------------------------------------
"-print 0" will be substituted into the command line if no print options are requested.


-print <printLimit>
Prints out the bootstrapped graph using a one-way top->bottom walk from the largest available nodes in the graph. Negative values for <printLimit> reverse the limitation on how far the program goes to find an unprinted node. For a graph with a size 10 node as the max size, -print -1 will only print all graphs containing a node with biclique size 10. -2 would print size 10 bicliques and size 9. -print 2 (positive value) will print all nodes that have not been printed yet until it reaches size 1 nodes, thus generating possibly a lot of files. Some overlap in the printouts may occur between graphs that have aunts and uncles that are similarly sized. The files are named similarly, and the current file has a number at the end distinguishing it from the others (the file_1 part seen above will become file_2, etc.). The output indicator in the file is the 'p0' portion, seen in the example:
abc_100_0.25_p0_t0.5_file_1.dot
-print commands can be requested more than once in separate commands: "-print -1 -print 3" is valid, and the -1 command will use 'p0', while the next will use 'p1' and so on.

A quick survey can be printed by using "-print -1", while printing out all files can be done with "-print 0".


-printbranch <printLimit> <branchLimit>
Prints out the bootstrapped graph using a depth-first search to collect all nodes connected to a base node. <printLimit> acts the same as in the -print option. <branchLimit> limits which nodes can be traced into when searching for new nodes to add to the branch. Having a "-print -1 3" means that nodes of size 2 or less will not appear in the graph, and will not be used for connecting nodes together. To print all branches, use "-print 0 0". Numbering starts at 1 (file_1, file_2, as seen in the first example). The output indicator for this version is the 'b0' portion, seen in this example:
abc_100_0.25_b0_t0.5_file_1.dot
-printbranch commands can be requested more than once: "-printbranch 0 0 -printbranch -3 3" is valid and 'b0' is assigned to the first, while 'b1' is assigned to the second and so on.


-printblue <printLimit>
Prints similar to "-print", but only nodes connected to edges above threshold will be kept. This is a quick way to see all significant results from a bootstrap.

-printbranchblue <printLimit> <branchLimit>
Prints similar to "-printbranch", but only nodes connected to edges above threshold will be kept. This is a quick way to see all significant results from a bootstrap. Some disconnection may occur in the graph if a node is disconnected from a parent, but has a valid child node connection above threshold.
