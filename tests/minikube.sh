#!/bin/bash -e

#Based on ideas from https://github.com/rook/rook/blob/master/tests/scripts/minikube.sh
fail=0

ARCH=`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'`
function wait_till_pods_start() {
    # give it some time

    cnt=0
    local_timeout=200
    while true; do
	cnt=$((cnt + 1))
	sleep 2
	ret=$(kubectl get pods -nkadalu -o wide | grep 'Running' | wc -l)
	if [[ $ret -ge 11 ]]; then
	    echo "Successful after $cnt seconds"
	    break
	fi
	if [[ $cnt -eq ${local_timeout} ]]; then
	    kubectl get pods -o wide
	    echo "giving up after ${local_timeout} seconds"
	    fail=1
	    break
	fi
	if [[ $((cnt % 15)) -eq 0 ]]; then
	    echo "$cnt: Waiting for pods to come up..."
	fi
    done

    kubectl get sc
    kubectl get pods -nkadalu -o wide
    # Return failure if fail variable is set to 1
    if [ $fail -eq 1 ]; then
	echo "Marking the test as 'FAIL'"
	for p in $(kubectl -n kadalu get pods -o name); do
	    echo "====================== Start $p ======================"
	    kubectl -nkadalu --all-containers=true --tail 300 logs $p
	    kubectl -nkadalu describe $p
	    echo "======================= End $p ======================="
	done
	exit 1
    fi
}
function get_pvc_and_check() {
    yaml_file=$1
    log_text=$2
    pod_count=$3
    time_limit=$4

    echo "Running sample test app ${log_text} yaml from repo "
    kubectl apply -f ${yaml_file}

    cnt=0
    result=0
    while true; do
	cnt=$((cnt + 1))
	sleep 1
	ret=$(kubectl get pods -o wide | grep 'Completed' | wc -l)
	if [[ $ret -eq ${pod_count} ]]; then
	    echo "Successful after $cnt seconds"
	    break
	fi
	if [[ $cnt -eq ${time_limit} ]]; then
	    kubectl get pvc
	    kubectl get pods -nkadalu -o wide
	    kubectl get pods -o wide
	    echo "exiting after ${time_limit} seconds"
	    result=1
	    fail=1
	    break
	fi
	if [[ $((cnt % 25)) -eq 0 ]]; then
	    echo "$cnt: Waiting for pods to come up..."
	fi
    done
    kubectl get pvc
    kubectl get pods -o wide

    #Delete the pods/pvc
    for p in $(kubectl get pods -o name); do
	[[ $result -eq 1 ]] && kubectl describe $p
	[[ $result -eq 0 ]] && kubectl logs $p
	kubectl delete $p
    done

    for p in $(kubectl get pvc -o name); do
	[[ $result -eq 1 ]] && kubectl describe $p
	kubectl delete $p
    done
}

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
	    #exit 1
	fi
	echo "minikube already installed with ${version}"
	return 0
    fi

    echo "Installing minikube. Version: ${MINIKUBE_VERSION}"
    curl -Lo minikube https://storage.googleapis.com/minikube/releases/"${MINIKUBE_VERSION}"/minikube-linux-${ARCH} && chmod +x minikube && mv minikube /usr/local/bin/
}

function install_kubectl() {
    if type kubectl >/dev/null 2>&1; then
	local version
	version=$(kubectl version --client | grep "${KUBE_VERSION}")
	if [[ "x${version}" != "x" ]]; then
	    echo "kubectl already installed with ${KUBE_VERSION}"
	    return 0
	fi
	echo "installed kubectl version ${version} is not matching requested version ${KUBE_VERSION}"
	#exit 1
    fi
    # Download kubectl, which is a requirement for using minikube.
    echo "Installing kubectl. Version: ${KUBE_VERSION}"
    curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/"${KUBE_VERSION}"/bin/linux/${ARCH}/kubectl && chmod +x kubectl && mv kubectl /usr/local/bin/
}

function run_io(){

  # Deploy io-app deployment with 2 replicas
  kubectl apply -f tests/test-io/io-app.yaml

  # Compressed image is ~25MB and so it shouldn't take more than 30s to reach ready state
  kubectl wait --for=condition=ready pod -l app=io-app --timeout=30s

  # Store pod names
  pods=($(kubectl get pods -l app=io-app -o jsonpath={'..metadata.name'}))

  echo Run IO from first pod [~30s]
  # 9 types of IO operations are performed
  kubectl exec -i ${pods[0]} -- sh -c 'cd /mnt/alpha; mkdir -p io-1; for j in create rename chmod chown chgrp symlink hardlink truncate setxattr create; \
  do crefi --multi -n 5 -b 5 -d 5 --max=10K --min=500 --random -t text -T=3 --fop=$j io-1/ 2>/dev/null; done'

  echo Run IO from second pod [~30s]
  kubectl exec -i ${pods[1]} -- sh -c 'cd /mnt/alpha; mkdir -p io-2; for j in create rename chmod chown chgrp symlink hardlink truncate setxattr create; \
  do crefi --multi -n 5 -b 5 -d 5 --max=10K --min=500 --random -t text -T=3 --fop=$j io-2/ 2>/dev/null; done'

  echo Collecting arequal-checksum from pods under io-pod deployment
  first_sum=$(kubectl exec -i ${pods[0]} -- sh -c 'arequal-checksum /mnt/alpha') && echo "$first_sum"
  second_sum=$(kubectl exec -i ${pods[1]} -- sh -c 'arequal-checksum /mnt/alpha') && echo "$second_sum"

  echo Validate checksum between first and second pod [Empty for checksum match]
  diff <(echo "$first_sum") <(echo "$second_sum") || fail=1

  return 0
}

# configure minikube
MINIKUBE_VERSION=${MINIKUBE_VERSION:-"v1.15.1"}
KUBE_VERSION=${KUBE_VERSION:-"v1.20.0"}
COMMIT_MSG=${COMMIT_MSG:-""}
MEMORY=${MEMORY:-"3000"}
VM_DRIVER=${VM_DRIVER:-"none"}
#configure image repo
KADALU_IMAGE_REPO=${KADALU_IMAGE_REPO:-"docker.io/kadalu"}
K8S_IMAGE_REPO=${K8S_IMAGE_REPO:-"quay.io/k8scsi"}

#feature-gates for kube
K8S_FEATURE_GATES=${K8S_FEATURE_GATES:-"BlockVolume=true,CSIBlockVolume=true,VolumeSnapshotDataSource=true,CSIDriverRegistry=true"}

DISK="sda1"
if [[ "${VM_DRIVER}" == "kvm2" ]]; then
    # use vda1 instead of sda1 when running with the libvirt driver
    DISK="vda1"
fi

case "${1:-}" in
up)
    echo "here"
    install_minikube || echo "failure"
    #if driver  is 'none' install kubectl with KUBE_VERSION
    if [[ "${VM_DRIVER}" == "none" ]]; then
	mkdir -p "$HOME"/.kube "$HOME"/.minikube
	install_kubectl || echo "failure to install kubectl"
    fi

    echo "starting minikube with kubeadm bootstrapper"
    minikube start --memory="${MEMORY}" -b kubeadm --kubernetes-version="${KUBE_VERSION}" --vm-driver="${VM_DRIVER}" --feature-gates="${K8S_FEATURE_GATES}"

    # environment
    if [[ "${VM_DRIVER}" != "none" ]]; then
	wait_for_ssh
	# shellcheck disable=SC2086
	minikube ssh "sudo mkdir -p /mnt/${DISK}; sudo truncate -s 4g /mnt/${DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1}; sudo mkdir -p /mnt/${DISK}/{dir3.2,dir3.2_modified,pvc}"
    else
	sudo mkdir -p /mnt/${DISK}
	sudo truncate -s 4g /mnt/${DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1}
	sudo mkdir -p /mnt/${DISK}/dir3.2
	sudo mkdir -p /mnt/${DISK}/dir3.2_modified
	sudo mkdir -p /mnt/${DISK}/pvc
    fi

    # Dump Cluster Info
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

    if [[ ! "$COMMIT_MSG" =~ 'helm skip' ]]; then

        # As per https://github.com/actions/virtual-environments/blob/main/images/linux/Ubuntu2004-README.md
        # `helm` is already part of github runner
        for distro in kubernetes rke microk8s openshift
        do
            if [ "$distro" != "kubernetes" ]; then
                export operator="kadalu-operator-$distro"
            else
                export operator="kadalu-operator"
            fi
            export verbose="yes" dist=$distro
            echo Validating helm template for "'$distro'" against "'$operator'" [Empty for no diff]
            echo

            # Helm templates will not have 'kind: Namespace' so need to skip first 6 lines from operator manifest
            if [ "$distro" == "openshift" ]; then
                # Helm follows a specific order while installing/uninstalling (https://github.com/helm/helm/blob/release-3.0/pkg/releaseutil/kind_sorter.go#L27)
                # resources and it doesn't contain OpenShift 'SecurityContextConstraints' kind, so need to sort lines before 'diff'
                diff <(helm template --namespace kadalu helm/kadalu --set-string kubernetesDistro=$distro,verbose=$verbose | grep -v '#' | sort) \
                    <(grep -v '#' manifests/"$operator.yaml" | tail -n +6 | sort ) --ignore-blank-lines
            else
                diff <(helm template --namespace kadalu helm/kadalu --set-string kubernetesDistro=$distro,verbose=$verbose | grep -v '#') \
                    <(grep -v '#' manifests/"$operator.yaml" | tail -n +6) --ignore-blank-lines
            fi
        done
        unset operator verbose dist

    fi

    echo "Starting the kadalu Operator"

    # pick the operator file from repo
    sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml
    kubectl apply -f manifests/kadalu-operator.yaml

    sleep 1
    # Start storage
    output=$(kubectl get nodes -o=name)
    # output will be in format 'node/hostname'. We need 'hostname'
    HOSTNAME=$(basename $output)
    echo "Hostname is ${HOSTNAME}"
    cp tests/storage-add.yaml /tmp/kadalu-storage.yaml
    sed -i -e "s/DISK/${DISK}/g" /tmp/kadalu-storage.yaml
    sed -i -e "s/node: minikube/node: ${HOSTNAME}/g" /tmp/kadalu-storage.yaml

    # Prepare PVC also as a storage
    sed -i -e "s/DISK/${DISK}/g" tests/get-minikube-pvc.yaml
    kubectl apply -f tests/get-minikube-pvc.yaml

    # Generally it needs some time for operator to get started, give it time, so some logs are reduced in tests
    sleep 15;
    kubectl apply -f /tmp/kadalu-storage.yaml

    wait_till_pods_start
    ;;

test_kadalu)
    date

    get_pvc_and_check examples/sample-test-app3.yaml "Replica3" 2 90

    get_pvc_and_check examples/sample-test-app1.yaml "Replica1" 2 90
    
    #get_pvc_and_check examples/sample-external-storage.yaml "External (PV)" 1 60

    #get_pvc_and_check examples/sample-external-kadalu-storage.yaml "External (Kadalu)" 2 90

    cp tests/storage-add.yaml /tmp/kadalu-storage.yaml
    sed -i -e "s/DISK/${DISK}/g" /tmp/kadalu-storage.yaml
    sed -i -e "s/node: minikube/node: ${HOSTNAME}/g" /tmp/kadalu-storage.yaml
    sed -i -e "s/dir3.2/dir3.2_modified/g" /tmp/kadalu-storage.yaml
    kubectl apply -f /tmp/kadalu-storage.yaml

    sleep 5;
    echo "After modification"
    wait_till_pods_start

    #get_pvc_and_check examples/sample-test-app2.yaml "Replica2" 2 60

    # Run minimal IO test
    run_io

    # Deploy and run CSI Sanity tests
    kubectl apply -f tests/test-csi/sanity-app.yaml
    kubectl wait --for=condition=ready pod -l app=sanity-app --timeout=15s

    # Intention is to slowly fix Sanity tests which are failing
    # Current stats: Total: 73, Pass: 7, Fail: 26, Skipped (With features not implemented yet): 40
    # TODO (by intern?): Fix 30-40% of sanity tests between each CSI Spec refresh (current Spec v1.2)
    exp_pass=7
    kubectl exec sanity-app -i -- sh -c 'csi-sanity -ginkgo.v --csi.endpoint $CSI_ENDPOINT -ginkgo.skip pagination' | tee /tmp/sanity-result.txt

    # Make sure no more failures than above stats
    act_pass=$(grep -Po '(\d+)(?= Passed)' /tmp/sanity-result.txt 2>/dev/null || echo 0)
    [ $act_pass -ge $exp_pass ] || fail=1
    echo Sanity [Pass %]: Expected: $exp_pass and Actual: $act_pass

    # Log everything so we are sure if things are as expected
    for p in $(kubectl -n kadalu get pods -o name); do
	echo "====================== Start $p ======================"
	kubectl -nkadalu --all-containers=true --tail 1000 logs $p
	echo "======================= End $p ======================="
    done

    date

    # Return failure if fail variable is set to 1
    if [ $fail -eq 1 ]; then
	echo "Marking the test as 'FAIL'"
	exit 1
    else
	echo "Tests SUCCESSFUL"
    fi

    ;;

cli_tests)
    output=$(kubectl get nodes -o=name)    
    # output will be in format 'node/hostname'. We need 'hostname'
    HOSTNAME=$(basename $output)
    echo "Hostname is ${HOSTNAME}"
    bash tests/kubectl_kadalu_tests.sh "$DISK" "${HOSTNAME}"
    wait_till_pods_start
    ;;

clean)
    minikube delete
    ;;
*)
    echo " $0 [command]
Available Commands:
  up               Starts a local kubernetes cluster and prepare disks for gluster
  down             Stops a running local kubernetes cluster
  clean            Deletes a local kubernetes cluster
  ssh              Log into or run a command on a minikube machine with SSH
  copy-image       copy kadalu-operator docker image
  kadalu_operator  start kadalu operator
  test_kadalu      test kadalu storage
" >&2
    ;;
esac
