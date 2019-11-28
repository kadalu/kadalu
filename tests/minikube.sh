#!/bin/bash -e

#Based on ideas from https://github.com/rook/rook/blob/master/tests/scripts/minikube.sh

function wait_for_ssh() {
    local tries=100
    while ((tries > 0)); do
        if minikube ssh echo connected &>/dev/null; then
            return 0
        fi
        tries=$((tries - 1))
        sleep 0.1
    done
    echo ERROR: ssh did not come up >&2
    exit 1
}

function copy_image_to_cluster() {
    local build_image=$1
    local final_image=$2
    if [ -z "$(docker images -q "${build_image}")" ]; then
        docker pull "${build_image}"
    fi
    if [[ "${VM_DRIVER}" == "none" ]]; then
        docker tag "${build_image}" "${final_image}"
        return
    fi
    docker save "${build_image}" | \
        (eval "$(minikube docker-env --shell bash)" && \
             docker load && docker tag "${build_image}" "${final_image}")
}

# install minikube
function install_minikube() {
    if type minikube >/dev/null 2>&1; then
        local version
        version=$(minikube version)
        read -ra version <<<"${version}"
        version=${version[2]}
        if [[ "${version}" != "${MINIKUBE_VERSION}" ]]; then
            echo "installed minikube version ${version} is not matching requested version ${MINIKUBE_VERSION}"
            exit 1
        fi
        echo "minikube already installed with ${version}"
        return
    fi

    echo "Installing minikube. Version: ${MINIKUBE_VERSION}"
    curl -Lo minikube https://storage.googleapis.com/minikube/releases/"${MINIKUBE_VERSION}"/minikube-linux-amd64 && chmod +x minikube && mv minikube /usr/local/bin/
}

function install_kubectl() {
    if type kubectl >/dev/null 2>&1; then
        local version
        version=$(kubectl version --client | grep "${KUBE_VERSION}")
        if [[ "x${version}" != "x" ]]; then
            echo "kubectl already installed with ${KUBE_VERSION}"
            return
        fi
        echo "installed kubectl version ${version} is not matching requested version ${KUBE_VERSION}"
        exit 1
    fi
    # Download kubectl, which is a requirement for using minikube.
    echo "Installing kubectl. Version: ${KUBE_VERSION}"
    curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/"${KUBE_VERSION}"/bin/linux/amd64/kubectl && chmod +x kubectl && mv kubectl /usr/local/bin/
}

# configure minikube
MINIKUBE_VERSION=${MINIKUBE_VERSION:-"latest"}
KUBE_VERSION=${KUBE_VERSION:-"v1.16.0"}
MEMORY=${MEMORY:-"3000"}
VM_DRIVER=${VM_DRIVER:-"virtualbox"}
#configure image repo
KADALU_IMAGE_REPO=${KADALU_IMAGE_REPO:-"docker.io/kadalu"}
K8S_IMAGE_REPO=${K8S_IMAGE_REPO:-"quay.io/k8scsi"}

#feature-gates for kube
K8S_FEATURE_GATES=${K8S_FEATURE_GATES:-"BlockVolume=true,CSIBlockVolume=true,VolumeSnapshotDataSource=true"}

DISK="sda1"
if [[ "${VM_DRIVER}" == "kvm2" ]]; then
    # use vda1 instead of sda1 when running with the libvirt driver
    DISK="vda1"
fi

case "${1:-}" in
up)
    install_minikube
    #if driver  is 'none' install kubectl with KUBE_VERSION
    if [[ "${VM_DRIVER}" == "none" ]]; then
        mkdir -p "$HOME"/.kube "$HOME"/.minikube
        install_kubectl
    fi

    echo "starting minikube with kubeadm bootstrapper"
    minikube start --memory="${MEMORY}" -b kubeadm --kubernetes-version="${KUBE_VERSION}" --vm-driver="${VM_DRIVER}" --feature-gates="${K8S_FEATURE_GATES}"

    # environment
    if [[ "${VM_DRIVER}" != "none" ]]; then
        wait_for_ssh
        # shellcheck disable=SC2086
        minikube ssh "sudo mkdir -p /mnt/${DISK}; sudo truncate -s 4g /mnt/${DISK}/file{1,3.1,3.2,3.3}"
    else
        sudo mkdir -p /mnt/${DISK};
        sudo truncate -s 4g /mnt/${DISK}/file{1,3.1,3.2,3.3}
    fi
    kubectl cluster-info
    ;;
down)
    minikube stop
    ;;
copy-image)
    echo "copying the kadalu-operator image"
    copy_image_to_cluster kadalu/kadalu-operator:${KADALU_VERSION} "${KADALU_IMAGE_REPO}"/kadalu-operator:${KADALU_VERSION}
    ;;
ssh)
    echo "connecting to minikube"
    minikube ssh
    ;;

kadalu_operator)
    docker images

    echo "Starting the kadalu Operator"

    # pick the operator file from repo
    sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml
    kubectl create -f manifests/kadalu-operator.yaml

    # Start storage
    cp examples/sample-storage-file-device.yaml /tmp/kadalu-storage.yaml
    sed -i -e "s/DISK/${DISK}/g" /tmp/kadalu-storage.yaml
    kubectl create -f /tmp/kadalu-storage.yaml

    # give it some time
    cnt=0
    while true; do
        cnt=$((cnt + 1))
        sleep 1
        ret=$(kubectl get pods -nkadalu | grep 'Running' | wc -l)
        if [[ $ret -ge 8 ]]; then
            echo "Successful after $cnt seconds"
            break
        fi
        if [[ $cnt -eq 100 ]]; then
            kubectl get pods
            echo "giving up after 100 seconds"
            break
        fi
        if [[ $((cnt % 10)) -eq 0 ]]; then
            echo "$cnt: Waiting for pods to come up..."
        fi
    done
    kubectl get pods -nkadalu

    ;;

test_kadalu)
    fail=0
    date
    echo "Requesting PVC and Sample apps"
    echo "Running default sample test app (Replica1) yml from repo"
    cp examples/sample-test-app1.yaml /tmp/kadalu-test-app1.yaml
    # Run ReadWriteOnce test
    kubectl create -f /tmp/kadalu-test-app1.yaml

    echo "Running sample test app (Replica3) yml from repo "
    cp examples/sample-test-app3.yaml /tmp/kadalu-test-app3.yaml
    # Run ReadWriteOnce test
    kubectl create -f /tmp/kadalu-test-app3.yaml
    # give it some time

    echo "Running sample test app from external Gluster"
    cp examples/sample-external-storage.yaml /tmp/kadalu-test-app-ext.yaml
    # Run ReadWriteOnce test
    kubectl create -f /tmp/kadalu-test-app-ext.yaml
    # give it some time

    cnt=0
    while true; do
        cnt=$((cnt + 1))
        sleep 1
        ret=$(kubectl get pods | grep 'Completed' | wc -l)
        if [[ $ret -eq 5 ]]; then
            echo "Successful after $cnt seconds"
            break
        fi
        if [[ $cnt -eq 200 ]]; then
	    kubectl get pvc
            kubectl get pods -nkadalu
            kubectl get pods
            echo "exiting after 200 seconds"
            fail=1
            break
        fi
        if [[ $((cnt % 25)) -eq 0 ]]; then
            echo "$cnt: Waiting for pods to come up..."
        fi
    done
    kubectl get pvc
    kubectl get pods

    # Log everything so we are sure if things are as expected
    for p in $(kubectl -n kadalu get pods -o name); do
        echo "====================== Start $p ======================"
        kubectl -nkadalu --all-containers=true --tail 100 logs $p
        echo "======================= End $p ======================="
    done

    echo "---- Logs from pod3 & pod1 ----"
    kubectl describe pod pod-ext
    echo "------------------"
    kubectl describe pod pod3-1
    echo "------------------"
    kubectl describe pod pod3-2
    echo "------------------"
    kubectl describe pod pod1-1
    echo "------------------"
    kubectl describe pod pod1-2
    echo "------------------"

    kubectl logs pod-ext
    echo "------------------"
    kubectl logs pod3-1
    echo "------------------"
    kubectl logs pod3-2
    echo "------------------"
    kubectl logs pod1-1
    echo "------------------"
    kubectl logs pod1-2
    echo "------------------"

    date

    # Return failure if fail variable is set to 1
    if [ $fail -eq 1 ]; then
        echo "Marking the test as 'FAIL'"
        exit 1
    fi
    ;;
clean)
    minikube delete
    ;;
*)
    echo " $0 [command]
Available Commands:
  up               Starts a local kubernetes cluster and prepare disk for rook
  down             Stops a running local kubernetes cluster
  clean            Deletes a local kubernetes cluster
  ssh              Log into or run a command on a minikube machine with SSH
  copy-image       copy kadalu-operator docker image
  kadalu_operator  start kadalu operator
  test_kadalu      test kadalu storage
" >&2
    ;;
esac
