OBJS = distribution_generator.o file_generator.o
CC = g++
## These libs should always come after the input file arguments to g++, 
## otherwise the linker will throw errors.
LIBS = -lpqxx -lpq
OPTS = -O3 -std=c++11 -I /usr/local/include -L /usr/local/lib -Wl,-rpath=/usr/local/lib/

install:
	$(CC) $(OPTS) distribution_generator.cpp -o distribution_generator.o $(LIBS)
	$(CC) $(OPTS) fileGenerator.cpp -o file_generator.o $(LIBS)
	$(CC) $(OPTS) drone.cpp -o drone.o $(LIBS)

distribution_generator:
	$(CC) $(OPTS) distribution_generator.cpp -o distribution_generator.o $(LIBS)

file_generator:
	$(CC) $(OPTS) fileGenerator.cpp -o file_generator.o $(LIBS)

drone:
	$(CC) $(OPTS) drone.cpp -o drone.o $(LIBS)
