#!/bin/bash
set -e

# This script will be used by travis to run functional test
# against different kuberentes version
export KUBE_VERSION=$1
sudo tests/minikube.sh up
