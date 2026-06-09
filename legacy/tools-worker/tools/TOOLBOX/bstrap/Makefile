# Adjust paths and compiler settings as necessary
CXX = g++
CXXFLAGS = -O3
LDFLAGS = -lpthread -lboost_thread -lboost_system

# List of source files
SRCS = bstrap.cpp Setmisc.cpp Stringmisc.cpp

# Output executable name
TARGET = bstrap

# Build target
all: $(TARGET)

$(TARGET): $(SRCS)
	$(CXX) $(CXXFLAGS) -o $@ $^ $(LDFLAGS)

clean:
	rm -f $(TARGET) *.o