# Makefile for Biclique

CC = gcc
MPICC = mpicc
CFLAGS = -O3 -g #-Wall
PTHREADS = -lm #-lpthread
LFSFLAG = -D_FILE_OFFSET_BITS=64
TESTFLAGS = #-DPERFORMANCE #-DDEBUG #-DVERBOSE

OBJECTS = bigraph.o utility.o sort.o
HEADERS = bigraph.h utility.h sort.h
EXECUTABLE = bicliquer

all: $(EXECUTABLE)

biclique: biclique-driver.o $(OBJECTS) $(HEADERS) Makefile
	$(CC) $(CFLAGS) $(LFSFLAG) $(TESTFLAGS) -o $@ biclique-driver.o $(OBJECTS) $(PTHREADS)

bicliquer: biclique-resampling.o $(OBJECTS) $(HEADERS) Makefile
	$(CC) $(CFLAGS) $(LFSFLAG) $(TESTFLAGS) -o $@ biclique-resampling.o $(OBJECTS) $(PTHREADS)

.c.o:
	$(CC) $(CFLAGS) $(LFSFLAG) $(TESTFLAGS) -c $*.c

clean:
	rm -f core* *.o $(EXECUTABLE)

