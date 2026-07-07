## Makefile for MSET

## WARNING: This has been testing with g++ version 8.x and above. Lower versions of g++ may not work
## correctly. If you have trouble compiling MSET please install g++ 8.x or greater.
##
## It's possible to install two version of g++. In that case, just specify the location of g++ 8.x+ below
## e.g. CC = /user-specific-location/gcc-8/bin/g++

CC = g++
CFLAGS = -static-libstdc++ -O3
LIBFLAGS = -fopenmp
EXE = MSETcpp

all:
	$(CC) $(CFLAGS) $(LIBFLAGS) -o $(EXE) main.cpp
