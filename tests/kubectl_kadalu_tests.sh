#!/bin/bash -e

DISK="$1"

# This test assumes a kubernetes setup available with host as minikube

function install_cli_package() {
    apt install python3-pip
    python3 -m pip install setuptools
    cd cli;
    # install kubectl kadalu
    echo "0.0.1canary"  > VERSION
    sudo python3 setup.py install || return 1
    cd ..
    return 0
}

function test_install() {
    sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml

    echo "Installing Operator through CLI"
    kubectl kadalu install --local-yaml manifests/kadalu-operator.yaml || return 1
}

function test_storage_add() {
    sed -i -e "s/DISK/${DISK}/g" tests/get-minikube-pvc.yaml
    kubectl create -f tests/get-minikube-pvc.yaml

    sleep 1
    kubectl kadalu storage-add test-volume3 --type Replica3 --device minikube:/mnt/${DISK}/file3.1 --path minikube:/mnt/${DISK}/dir3.2 --pvc local-pvc || return 1

    # Test Replica2 option
    kubectl kadalu storage-add test-volume2 --type Replica2 --device minikube:/mnt/${DISK}/file2.1 --device minikube:/mnt/${DISK}/file2.2 || return 1

    # Test Replica2 with tie-breaker option
    sudo truncate -s 2g /mnt/${DISK}/file2.{10,20}

    kubectl kadalu storage-add test-volume2-1 --type Replica2 --device minikube:/mnt/${DISK}/file2.10 --device minikube:/mnt/${DISK}/file2.20 --tiebreaker tie-breaker.kadalu.io:/mnt || return 1

    # Check if the type default is Replica1
    kubectl kadalu storage-add test-volume1 --device minikube:/mnt/${DISK}/file1 || return 1

    # Check for external storage
    # TODO: (For now, keep the name as 'ext-config' as PVC should use this
    # to send request.
    kubectl kadalu storage-add ext-config --external gluster1.kadalu.io:/kadalu || return 1
}

function main() {
    install_cli_package || (echo "install failed" && exit 1)
    test_install || (echo "CLI operator install failed" && exit 1)
    test_storage_add || (echo "Storage add commands failed" && exit 1)
}

main "$@"
