# Makefile for Biclique

CC = g++
MPICC = mpicc
CFLAGS = -fPIC -O3 -g #-Wall
PTHREADS = -lpthread
LFSFLAG = -D_FILE_OFFSET_BITS=64

OBJECTS = bigraph.o utility.o biclique.o
HEADERS = bigraph.h utility.h biclique.h
EXECUTABLE = biclique

all: $(EXECUTABLE)

biclique: biclique-driver.o $(OBJECTS) $(HEADERS) Makefile
	$(CC) $(CFLAGS) $(LFSFLAG) -o $@ biclique-driver.o $(OBJECTS) $(PTHREADS)

.c.o:
	$(CC) $(CFLAGS) $(LFSFLAG) -c $*.c

clean:
	rm -f core* *.o $(EXECUTABLE)

