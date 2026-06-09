#!/bin/sh

sleep 1200 && killall -9 dot & 2>/dev/null
/usr/bin/dot $@ 2>/dev/null
killall sleep 2>/dev/null
