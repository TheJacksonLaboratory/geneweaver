#!/bin/sh

# Resolve the graphviz binary from PATH (e.g. Homebrew's /opt/homebrew/bin/dot),
# falling back to the container's /usr/bin/dot.
DOT="$(command -v dot 2>/dev/null || echo /usr/bin/dot)"

sleep 1200 && killall -9 dot & 2>/dev/null
"$DOT" $@ 2>/dev/null
killall sleep 2>/dev/null
