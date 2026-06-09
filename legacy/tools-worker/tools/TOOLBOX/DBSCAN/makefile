OBJS = dbscan.o dbscanMain.o
CC = g++
CFLAGS = -c
## These libs should always come after the input file arguments to g++
## otherwise the linker will throw errors
LIBS = -lstdc++
PTHREAD = -lpthread


OPTS = -std=c++11 -I /usr/local/include

dbscan: $(OBJS)
	$(CC) $(LIBS) $(OPTS) -o dbscan $(OBJS)

dbscanMain.o: dbscanMain.cpp
	$(CC) $(OPTS) $(CFLAGS) dbscanMain.cpp

dbscan.o: dbscan.cpp dbscan.h
	$(CC) $(OPTS) $(CFLAGS) dbscan.cpp
clean:
	\rm $(OBJS) dbscan