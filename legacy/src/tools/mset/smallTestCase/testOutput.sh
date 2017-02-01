#!/bin/bash
if ../a.out 10 10000 interestSmall.txt backgroundSmall.txt | grep -E "alue: 0.00([1-9][0-9]|0[1-9])" >/dev/null; then
    echo "pass"
    exit 0
else 
    echo "fail" 
    exit 1
fi
