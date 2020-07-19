#!/bin/bash -e

DISK="$1"

# This test assumes a kubernetes setup available with host as minikube

HOSTNAME="$2"

function install_cli_package() {
    # install kubectl kadalu
    KADALU_VERSION="0.0.1canary" make cli-build
    return $?
}

function test_install() {
    sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator-master.yaml

    echo "Installing Operator through CLI"
    cli/build/kubectl-kadalu install --local-yaml manifests/kadalu-operator-master.yaml || return 1
}

function test_storage_add() {
    sed -i -e "s/DISK/${DISK}/g" tests/get-minikube-pvc.yaml
    kubectl create -f tests/get-minikube-pvc.yaml

    sleep 1
    cli/build/kubectl-kadalu storage-add test-volume3 --script-mode --type Replica3 --device ${HOSTNAME}:/mnt/${DISK}/file3.1 --path ${HOSTNAME}:/mnt/${DISK}/dir3.2 --pvc local-pvc || return 1

    # Test Replica2 option
    cli/build/kubectl-kadalu storage-add test-volume2 --script-mode --type Replica2 --device ${HOSTNAME}:/mnt/${DISK}/file2.1 --device ${HOSTNAME}:/mnt/${DISK}/file2.2 || return 1

    # Test Replica2 with tie-breaker option
    sudo truncate -s 2g /mnt/${DISK}/file2.{10,20}

    cli/build/kubectl-kadalu storage-add test-volume2-1 --script-mode --type Replica2 --device ${HOSTNAME}:/mnt/${DISK}/file2.10 --device ${HOSTNAME}:/mnt/${DISK}/file2.20 --tiebreaker tie-breaker.kadalu.io:/mnt || return 1

    # Check if the type default is Replica1
    cli/build/kubectl-kadalu storage-add test-volume1 --script-mode --device ${HOSTNAME}:/mnt/${DISK}/file1 || return 1

    # Check for external storage
    # TODO: (For now, keep the name as 'ext-config' as PVC should use this
    # to send request.
    cli/build/kubectl-kadalu storage-add ext-config --script-mode --external gluster1.kadalu.io:/kadalu || return 1
}

function main() {
    install_cli_package || (echo "install failed" && exit 1)
    test_install || (echo "CLI operator install failed" && exit 1)
    test_storage_add || (echo "Storage add commands failed" && exit 1)
}

main "$@"
