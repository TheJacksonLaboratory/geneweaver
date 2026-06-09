#ifndef BITVECTOR_H
#define BITVECTOR_H

class BitVector
{
public:
  BitVector(unsigned int);
  ~BitVector();
  BitVector(const BitVector&);
  BitVector& operator=(const BitVector&);

  void setBit(unsigned int);       //sets a particular bit to 1
  void clearBit(unsigned int);     //sets a particular bit to 0
  bool getBit(unsigned int);       //returns the value of a particular bit
  void addBit();                   //adds a bit to the vector
  void clear();                    //sets all bits to 0
  void fill();                     //sets all bits to 1

  int size();                      //get functions
  int degree();
  int blocks();          

private:
  unsigned int* Data;      //pointer to bit vector
  unsigned int Size;       //number of bits in bit vector
  unsigned int Degree;     //number of bits set to 1 (i.e. the degree of a vertex)
  unsigned int Blocks;     //number of 32-bit blocks currently allocated for the bit vector
};

#endif
