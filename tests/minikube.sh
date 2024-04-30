#!/bin/bash -e

# Format via shfmt -> shfmt -i 2 -ci -w tests/minikube.sh

# Based on ideas from https://github.com/rook/rook/blob/master/tests/scripts/minikube.sh
fail=0

ARCH=$(uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|')

function check_test_fail() {
  if [ $fail -eq 1 ]; then
    echo "Marking the test as 'FAIL'"
    _log_msgs
    exit 1
  fi
}

function _log_msgs() {
  local lines=100
  if [[ $fail -eq 1 || $COMMIT_MSG =~ 'full log' ]]; then
    lines=1000
  fi
  kubectl get kds --all-namespaces
  kubectl get sc --all-namespaces
  kubectl get pvc --all-namespaces
  for p in $(kubectl -n kadalu get pods -o name --field-selector=status.phase==Running); do
    echo "====================== Start $p ======================"
    kubectl logs -nkadalu --all-containers=true --tail=$lines $p
    kubectl -nkadalu describe $p
    echo "======================= End $p ======================="
  done
}

function wait_for_kadalu_pods() {
  # make sure operator, csi and server pods are all in ready state

  local k="kubectl -nkadalu "
  local local_timeout=${1:-200}
  local end_time=$(($(date +%s) + $local_timeout))

  # wait for kadalu pods creation
  while [[ 
    $($k get pod --ignore-not-found -o name -l name=kadalu | wc -l) -eq 0 ||
    $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=kadalu-csi-provisioner | wc -l) -eq 0 ||
    $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=kadalu-csi-nodeplugin | wc -l) -eq 0 ||
    $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=server | wc -l) -eq 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Kadalu pods are not created && fail=1 && return
    sleep 2
  done

  # check for operator
  $k wait --for=condition=ready pod -l name=kadalu --timeout=${local_timeout}s || {
    echo Kadalu Operator is not up within ${local_timeout}s && fail=1 && return
  }
  echo Kadalu Operator is in Ready state

  # check for csi provisioner
  $k wait --for=condition=ready pod -l app.kubernetes.io/name=kadalu-csi-provisioner --timeout=${local_timeout}s || {
    echo Kadalu CSI Provisioner is not up within ${local_timeout}s && fail=1 && return
  }
  echo Kadalu CSI Provisioner is in Ready state

  # check for csi nodeplugin
  $k wait --for=condition=ready pod -l app.kubernetes.io/name=kadalu-csi-nodeplugin --timeout=${local_timeout}s || {
    echo Kadalu CSI NodePlugin is not up within ${local_timeout}s && fail=1 && return
  }
  echo Kadalu CSI Nodeplugin is in Ready state

  # check for kadalu server
  $k wait --for=condition=ready pod -l app.kubernetes.io/name=server --timeout=${local_timeout}s || {
    echo Kadalu Server pods are not up within ${local_timeout}s && fail=1 && return
  }
  echo Kadalu Server pods are in Ready state

  check_test_fail
}

function get_pvc_and_check() {

  local yaml_file=$1
  local log_text=$2
  local pool_name=$3
  local pod_count=$4
  local time_limit=$5
  local end_time=$(($(date +%s) + $time_limit))

  local k="kubectl "

  echo "Running sample test app ${log_text} yaml from repo "
  kubectl apply -f ${yaml_file}

  # lower case the type of pool, compatible with bash >= v4
  local label="${log_text,,}"

  echo Waiting for sample pods creation with label $label
  while [[ $($k get pod -l type=${label} -o name | wc -l) -eq 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Sample pods are not created with label $label && fail=1 && return
    sleep 2
  done

  # check for pod completion status
  # for kubectl >= v1.23 -> k wait --for=jsonpath='{.status.phase}'=Succeeded pod -l type=${label}
  # status should be Succeeded for all app pods
  end_time=$(($(date +%s) + $time_limit))
  while [[ $($k get pod -l type=${label} -ojsonpath={'.items[].status.phase'} | grep -cv Succeeded) -ne 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Sample pods for pool type "${log_text}" are not in complete state within ${time_limit}s && fail=1 && return
    sleep 2
  done

  echo Sample pods of type $log_text are in Complete state

  # expand PVCs
  local original='200Mi'
  local final='300Mi'

  echo Expanding PVCs from $log_text pool type
  sed "s/$original/$final/g" ${yaml_file} | kubectl apply -f -

  # wait for pods to restart
  sleep 60
  end_time=$(($(date +%s) + $time_limit))
  while [[ $($k get pod -l type=${label} -ojsonpath={'.items[].status.phase'} | grep -cv Succeeded) -ne 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Sample pods for pool type "${log_text}" are not in complete state within ${time_limit}s after PVC expand && fail=1 && return
    sleep 2
  done

  end_time=$(($(date +%s) + $time_limit))
  while [[ $(kubectl get pvc -ojsonpath={'.items[].status.capacity.storage'} | grep -c $original) -ne 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Not all PVCs are expanded from $original to $final && fail=1 && return
    sleep 2
  done

  # delete app pods after above validation
  for p in $(kubectl get pods -o name -l type=${label}); do
    [[ $fail -eq 1 ]] && kubectl describe $p
    [[ $fail -eq 0 ]] && kubectl logs $p
    kubectl delete $p --force
  done

  # Display metrics output
  display_metrics

  # delete PVCs
  for p in $(kubectl get pvc -o name -l type=${label}); do
    name=$(kubectl get $p -ojsonpath={'.spec.volumeName'})
    # check for presence of PVC as previous PVC deletion shouldn't delete current PVC
    local json_file=$(kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/info/ -mindepth 4 -maxdepth 4 -name "*$name.json" -printf '.' | wc -c)
    local pvc_dir=$(kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/ -mindepth 4 -maxdepth 4 -name "*$name" -not -path "/mnt/$pool_name/.glusterfs/*" -not -path "/mnt/$pool_name/info/*" -printf '.' | wc -c
    )
    if [[ $json_file -ne 1 || $pvc_dir -ne 1 ]]; then
      fail=1 && echo Not able to verify existence of PVC $name
    fi

    [[ $fail -eq 1 ]] && kubectl describe $p
    kubectl delete $p
  done

  # there should be no leaf dir left after PVC delete since we aren't testing `pvReclaimPolicy` yet
  local json_files=$(kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/info/ -mindepth 2 -maxdepth 4 -printf '.' | wc -c)
  local pvc_dirs=$(kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/ -mindepth 2 -maxdepth 4 -not -path "/mnt/$pool_name/.glusterfs/*" -not -path "/mnt/$pool_name/info/*" -printf '.' | wc -c)

  if [[ $json_files -ne 0 || $pvc_dirs -ne 0 ]]; then
    echo Not all PVCs are cleaned up properly
    fail=1
    kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/info/ -mindepth 2 -maxdepth 4
    kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/ -mindepth 2 -maxdepth 4 -not -path "/mnt/$pool_name/.glusterfs/*" -not -path "/mnt/$pool_name/info/*"
  fi

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
  docker save "${build_image}" |
    (eval "$(minikube docker-env --shell bash)" &&
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
    # exit 1
  fi
  # Download kubectl, which is a requirement for using minikube.
  echo "Installing kubectl. Version: ${KUBE_VERSION}"
  curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/"${KUBE_VERSION}"/bin/linux/${ARCH}/kubectl && chmod +x kubectl && mv kubectl /usr/local/bin/
}

function run_io() {

  # Deploy io-app deployment with 2 replicas
  kubectl apply -f tests/test-io/io-app.yaml

  # Compressed image is ~25MB and so it shouldn't take much time to reach ready state
  kubectl wait --for=condition=ready pod -l app=io-app --timeout=60s || fail=1
  if [ $fail == 1 ]; then
    return 0
  fi

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

  check_test_fail
}

function run_sanity() {

  # Deploy and run CSI Sanity tests
  kubectl apply -f tests/test-csi/sanity-app.yaml
  kubectl wait --for=condition=ready pod -l app=sanity-app --timeout=15s || {
    echo CSI Sanity app is not ready within 15s && fail=1 && return
  }

  exp_pass=33

  # Set expand vol size to 10MB
  kubectl exec sanity-app -i -- sh -c 'csi-sanity -ginkgo.v --csi.endpoint $CSI_ENDPOINT -ginkgo.skip pagination -csi.testvolumesize 10485760 -csi.testvolumeexpandsize 10485760' | tee /tmp/sanity-result.txt

  # Make sure no more failures than above stats
  act_pass=$(grep -Po '(\d+)(?= Passed)' /tmp/sanity-result.txt 2>/dev/null || echo 0)
  [ $act_pass -ge $exp_pass ] || fail=1
  echo Sanity [Pass %]: Expected: $exp_pass and Actual: $act_pass

  check_test_fail
}

function verify_storage_options() {
  echo "List of storage-class"
  kubectl get sc -nkadalu
  for p in $(kubectl -n kadalu get pods -o name); do
    if [[ $p == *"nodeplugin"* ]]; then
      kubectl exec -i -nkadalu $p -c 'kadalu-nodeplugin' -- bash -c 'grep -e "data-self-heal off" -e "nl-cache off" /kadalu/volfiles/* | cat'
    fi
  done
}

function display_metrics() {

  echo "Displaying Kadalu metrics"
  kubectl exec -i -nkadalu deploy/operator -- python -c 'import requests; import json; print(json.dumps(requests.get("http://localhost:8050/metrics.json").json(), indent=2))'

  echo "Displaying Kadalu Prometheus metrics"
  kubectl exec -i -nkadalu deploy/operator -- python -c 'import requests; print(requests.get("http://localhost:8050/metrics").text)'

}

function deploy_kadalu_resources() {
  echo "Deploying kadalu operator and csi driver"

  # pick the operator file from repo
  sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml

  # set verbose field
  # TODO: Use helm values file
  sed -i -e 's/"no"/"yes"/g' manifests/kadalu-operator.yaml

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
  kubectl apply -f /tmp/kadalu-storage.yaml

}

function deploy_app_pods() {

  # type: Replica3
  get_pvc_and_check examples/sample-test-app3.yaml "Replica3" "storage-pool-3" 6 180
  check_test_fail

  # type: Replica1
  get_pvc_and_check examples/sample-test-app1.yaml "Replica1" "storage-pool-1" 4 120
  check_test_fail

  # type: Disperse
  get_pvc_and_check examples/sample-test-app4.yaml "Disperse" "storage-pool-4" 4 120
  check_test_fail

  # type: Replica2
  # get_pvc_and_check examples/sample-test-app2.yaml "Replica2" "storage-pool-2" 4 120

  # type: External-non-native
  # get_pvc_and_check examples/sample-external-storage.yaml "External (PV)" 1 60

  # type: External-native
  # get_pvc_and_check examples/sample-external-kadalu-storage.yaml "External (Kadalu)" 2 90
}

function modify_pool() {
  cp tests/storage-add.yaml /tmp/kadalu-storage.yaml
  sed -i -e "s/DISK/${DISK}/g" /tmp/kadalu-storage.yaml
  sed -i -e "s/node: minikube/node: ${HOSTNAME}/g" /tmp/kadalu-storage.yaml
  sed -i -e "s/dir3.2/dir3.2_modified/g" /tmp/kadalu-storage.yaml
  kubectl apply -f /tmp/kadalu-storage.yaml
}

# configure minikube
MINIKUBE_VERSION=${MINIKUBE_VERSION:-"v1.15.1"}
KUBE_VERSION=${KUBE_VERSION:-"v1.20.0"}
COMMIT_MSG=${COMMIT_MSG:-""}
MEMORY=${MEMORY:-"3000"}
VM_DRIVER=${VM_DRIVER:-"none"}
# configure image repo
KADALU_IMAGE_REPO=${KADALU_IMAGE_REPO:-"docker.io/kadalu"}
K8S_IMAGE_REPO=${K8S_IMAGE_REPO:-"quay.io/k8scsi"}

# feature-gates for kube
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
    # if driver  is 'none' install kubectl with KUBE_VERSION
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
      minikube ssh "sudo mkdir -p /mnt/${DISK};sudo rm -rf /mnt/${DISK}/*; sudo truncate -s 4g /mnt/${DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1,4.1,4.2,4.3,5.1,5.2,5.3,5.4,5.5,5.6,5.7,5.8,5.9}; sudo mkdir -p /mnt/${DISK}/{dir3.2,dir3.2_modified,pvc}"
    else
      sudo mkdir -p /mnt/${DISK}
      sudo rm -rf /mnt/${DISK}/*
      sudo truncate -s 4g /mnt/${DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1,4.1,4.2,4.3,5.1,5.2,5.3,5.4,5.5,5.6,5.7,5.8,5.9}
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

    # list docker images
    docker images

    # deploys kadalu operator, csi driver and storage pools
    deploy_kadalu_resources

    # validates all kadalu resource pods are up or not
    wait_for_kadalu_pods

    ;;

  test_kadalu)

    # deploy and validate app pods on storage pools and expand PVCs created as part of 'kadalu_operator' case
    deploy_app_pods

    # modifies existing storage pool to check for changes in kadalu resources
    modify_pool

    # validates all kadalu resource pods are up or not after modifying pools
    wait_for_kadalu_pods 400

    # Run minimal IO test
    run_io

    # Run CSI Sanity tests
    run_sanity

    # Test Storage-Options
    # verify_storage_options

    # check for test failure
    check_test_fail

    # log required containers logs to stdout
    _log_msgs

    ;;

  cli_tests)
    output=$(kubectl get nodes -o=name)
    # output will be in format 'node/hostname'. We need 'hostname'
    HOSTNAME=$(basename $output)
    echo "Hostname is ${HOSTNAME}"
    bash tests/kubectl_kadalu_tests.sh "$DISK" "${HOSTNAME}"
    wait_for_kadalu_pods
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
