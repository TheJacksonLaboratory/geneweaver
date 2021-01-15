#! /bin/bash

usage() {
  echo "$0 [PATH_TO_SECRETS_FILE] [PATH_TO_TESTING_SECRETS_FILE]"
  echo
  echo "Secrets files should contain one key=value pair per line. e.g."
  echo
  echo "DB_URL=sqlite://path_to_db.sqlite"
  echo "SECRET_KEY=thisisntarealsecretkey"
  echo "AUTH0_SECRET=notarealsecreteither"
  echo
}

if [ $# -lt 2 ]; then
  usage
  exit 1
fi

kubectl create secret generic "geneweaver-ortholog-normalizer-secrets" --from-env-file="$1"
kubectl create secret generic "geneweaver-ortholog-normalizer-testing-secrets" --from-env-file="$2"