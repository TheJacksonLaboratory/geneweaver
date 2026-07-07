#include <iostream>
#include <cstdlib>

#include "BitVector.h"

BitVector::BitVector(unsigned int num) : Size(num), Degree(0)  //constructor - inputs number of bits
{
  Blocks = ((num-1)>>5)+1;
  Data = (unsigned int*)calloc(Blocks, 4);
}

BitVector::~BitVector()                                   //destructor
{
  free(Data);
}

BitVector::BitVector(const BitVector& right) : Blocks(right.Blocks),    //copy constructor
                                               Size(right.Size),
                                               Degree(right.Degree)
{
  Data = (unsigned int*)malloc(Blocks*4);
  for (unsigned int i=0; i<Blocks; i++)
    Data[i] = right.Data[i];
}

BitVector& BitVector::operator=(const BitVector& right)           //assignment
{
  Blocks = right.Blocks;
  Size = right.Size;
  Degree = right.Degree;

  Data = (unsigned int*)realloc(Data, right.Blocks*4);

  for (unsigned int i=0; i<Blocks; i++)
    Data[i] = right.Data[i];

  return *this;
}

int BitVector::size() { return Size; }

int BitVector::degree() { return Degree; }

int BitVector::blocks() { return Blocks; }

void BitVector::setBit(unsigned int bitnum)
{
  unsigned int mask = 1 << (bitnum & 31);

  if ( !(mask & Data[bitnum>>5]))
    Degree++; 

  Data[bitnum>>5] ^= mask;
}

void BitVector::clearBit(unsigned int bitnum)
{
  unsigned int mask = 1 << (bitnum & 31);
  Data[bitnum>>5] &= ~mask;
}

bool BitVector::getBit(unsigned int bitnum)
{
  unsigned int mask = 1 << (bitnum & 31);

  if ( mask & Data[bitnum>>5])
    return true;
  else
    return false;
}

void BitVector::addBit()
{
  Blocks = (Size>>5)+1;
  Data = (unsigned int*)realloc(Data, Blocks*4);
  clearBit(Size);
  Size++;
}

void BitVector::clear()
{
  for (unsigned int i=0; i<Blocks; i++)
    Data[i] = 0;
}

void BitVector::fill()
{
  for (unsigned int i=0; i<Blocks; i++)
    Data[i] = 0xffffffff;
}
