#!/bin/bash
set -e

# This script will be used by travis to run functional test
# against different kuberentes version
export KUBE_VERSION=$1
sudo tests/minikube.sh up
# pull docker images to speed up e2e
sudo tests/minikube.sh kadalu_operator
sudo chown -R travis: "$HOME"/.minikube /usr/local/bin/kubectl
# functional tests
# sample test

sudo tests/minikube.sh test_kadalu

sudo tests/minikube.sh clean
