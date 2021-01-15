#!/bin/sh

mascot(){
  cat << 'EOF'
geneweaver_ortholog_normalizer
EOF
}


if [ -z "$PRODUCTION" ] ; then
  echo "# System ------------"
  uname -a
  echo "# Storage -----------"
  lsblk
  echo "# CPU ---------------"
  lscpu
  
  
  mascot
fi

exec "$@"