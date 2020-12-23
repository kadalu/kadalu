#!/bin/bash
set -e

# This script will be used by travis to run functional test
# against different kuberentes version
export KUBE_VERSION=$1

cli_test="yes"
if [ "$#" -ge 2 -a "$2" == "cli" ]; then
    cli_test="yes"
fi

# pull docker images to speed up e2e
if [ "$cli_test" == "no" ]; then
    echo "Starting YAML based tests (without CLI)"
    sudo tests/minikube.sh kadalu_operator
else
    echo "Starting CLI (kubectl kadalu) based tests"
    sudo tests/minikube.sh cli_tests
fi

#sudo chown -R travis: "$HOME"/.minikube /usr/local/bin/kubectl
# functional tests
# sample test

sudo tests/minikube.sh test_kadalu
