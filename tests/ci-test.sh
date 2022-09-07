#!/bin/bash
set -e

cli_test="no"
if [ "$#" -ge 1 -a "$1" == "cli" ]; then
    cli_test="yes"
fi

if [ "$cli_test" == "no" ]; then
    echo "Starting YAML based tests (without CLI)"
    sudo tests/minikube.sh kadalu_operator
else
    echo "Starting CLI (kubectl kadalu) based tests"
    sudo tests/minikube.sh cli_tests
fi

sudo tests/minikube.sh test_kadalu
