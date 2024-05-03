#!/bin/bash -e
# Format via shfmt -> shfmt -i 2 -ci -w tests/tests.sh

K3D_VERSION=${K3D_VERSION:-"v5.6.3"}
KUBE_IMG=${KUBE_IMG:-"rancher/k3s:v1.29.4-k3s1"}

CLUSTER_NAME=test
NODE_NAME=k3d-${CLUSTER_NAME}-server-0

fail=0

DISK=test
PVC=$(
  cat <<EOF
---
apiVersion: v1
kind: PersistentVolume
metadata:
  name: local-pv
  labels:
    type: local
spec:
  storageClassName: manual
  capacity:
    storage: 1Gi
  accessModes:
  - ReadWriteMany
  hostPath:
    path: "/mnt/$DISK/pvc"
---
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: local-pvc
  namespace: kadalu
spec:
  storageClassName: manual
  accessModes:
  - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
---
EOF
)

function _install_cli_pkg() {
  make cli-build || (echo "CLI Installation failed" && exit 1)
}

function _setup_k3d() {
  # NOTE: GH Runner provides a total of 15GB SSD storage
  mkdir -p /mnt/${DISK}

  # for Replica 1 testing
  truncate -s 1g /mnt/${DISK}/file1.{1,2,3}

  # for Replica 2 testing
  # truncate -s 1g /mnt/${DISK}/file2.{1,2}

  # for Replica 3 testing
  truncate -s 1g /mnt/${DISK}/file3.1
  mkdir -p /mnt/${DISK}/dir3.2
  mkdir -p /mnt/${DISK}/dir3.2_modified
  mkdir -p /mnt/${DISK}/pvc

  # for Disperse testing
  truncate -s 1g /mnt/${DISK}/file4.{1,2,3}

  # install k3d binary, no-op if same version already exists
  curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | TAG=${K3D_VERSION} bash
  cfg=$(mktemp)

  # Use local docker as a pull through registry
  cat <<EOF >"$cfg"
apiVersion: k3d.io/v1alpha5
kind: Simple
registries:
  create:
    image: ligfx/k3d-registry-dockerd:v0.4
    proxy:
      remoteURL: "*"
    volumes:
      - /var/run/docker.sock:/var/run/docker.sock
EOF

  mkdir -p /tmp/k3d/kubelet/pods
  k3d cluster create ${CLUSTER_NAME} --config "$cfg" --image ${KUBE_IMG} \
    -v /dev:/dev \
    -v /tmp/k3d/kubelet/pods:/var/lib/kubelet/pods:shared \
    -v /mnt/${DISK}:/mnt/${DISK}:shared \
    --k3s-arg "--disable=local-storage@server:*" --verbose || (echo "Failed to create k3d cluster" && exit 1)

  kubectl cluster-info
}

function _teardown_k3d() {
  k3d cluster rm $CLUSTER_NAME
}

function _check_test_fail() {
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
    local pvc_dir=$(
      kubectl exec -i sts/kadalu-csi-provisioner -c kadalu-provisioner -nkadalu -- /usr/bin/find /mnt/$pool_name/ -mindepth 4 -maxdepth 4 -name "*$name" -not -path "/mnt/$pool_name/.glusterfs/*" -not -path "/mnt/$pool_name/info/*" -printf '.' | wc -c
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

  _check_test_fail
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

  _check_test_fail
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

  _check_test_fail
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
  echo "Deploying kadalu operator"

  # Install operator
  cli/build/kubectl-kadalu install --local-yaml manifests/kadalu-operator.yaml

  # Create local PVC
  echo "$PVC" | kubectl apply -f -

  # Replica 3
  cli/build/kubectl-kadalu storage-add storage-pool-3 --script-mode --type Replica3 \
    --device ${NODE_NAME}:/mnt/${DISK}/file3.1 --path ${NODE_NAME}:/mnt/${DISK}/dir3.2 --pvc local-pvc

  # Replica 1
  cli/build/kubectl-kadalu storage-add storage-pool-1 --script-mode --type Replica1 \
    --device ${NODE_NAME}:/mnt/${DISK}/file1.1 --device ${NODE_NAME}:/mnt/${DISK}/file1.2 --device ${NODE_NAME}:/mnt/${DISK}/file1.3

  # Disperse
  cli/build/kubectl-kadalu storage-add storage-pool-4 --script-mode --type Disperse \
    --data 2 --redundancy 1 --device ${NODE_NAME}:/mnt/${DISK}/file4.1 --device ${NODE_NAME}:/mnt/${DISK}/file4.2 \
    --device ${NODE_NAME}:/mnt/${DISK}/file4.3

  # Replica 2 (untested)
  # cli/build/kubectl-kadalu storage-add storage-pool-2 --script-mode --type Replica2 \
  # --device ${NODE_NAME}:/mnt/${DISK}/file2.1 --device ${NODE_NAME}:/mnt/${DISK}/file2.2 || return 1

  # External non native (untested)
  # cli/build/kubectl-kadalu storage-add ext-config --script-mode --external gluster1.kadalu.io:/kadalu --single-pv-per-pool

  # External native (untested)
  # cli/build/kubectl-kadalu storage-add ext-config --script-mode --external gluster1.kadalu.io:/kadalu
}

function deploy_app_pods() {

  # type: Replica3
  get_pvc_and_check examples/sample-test-app3.yaml "Replica3" "storage-pool-3" 6 180
  _check_test_fail

  # type: Replica1
  get_pvc_and_check examples/sample-test-app1.yaml "Replica1" "storage-pool-1" 4 120
  _check_test_fail

  # type: Disperse
  get_pvc_and_check examples/sample-test-app4.yaml "Disperse" "storage-pool-4" 4 120
  _check_test_fail

  # type: Replica2
  # get_pvc_and_check examples/sample-test-app2.yaml "Replica2" "storage-pool-2" 4 120
  # _check_test_fail

  # type: External-non-native
  # get_pvc_and_check examples/sample-external-storage.yaml "External (PV)" 1 60
  # _check_test_fail

  # type: External-native
  # get_pvc_and_check examples/sample-external-kadalu-storage.yaml "External (Kadalu)" 2 90
  # _check_test_fail
}

function modify_pool() {
  # changes the path of Replica 3 pool to test self heal
  cli/build/kubectl-kadalu storage-add storage-pool-3 --script-mode --type Replica3 \
    --device ${NODE_NAME}:/mnt/${DISK}/file3.1 --path ${NODE_NAME}:/mnt/${DISK}/dir3.2_modified --pvc local-pvc
}

function main() {
  # list docker images
  docker images

  # make kubectl_kadalu binary
  _install_cli_pkg

  # install k3d
  _setup_k3d

  # deploys kadalu operator, storage pools
  deploy_kadalu_resources

  # validates all kadalu resource pods are up or not
  wait_for_kadalu_pods
  _check_test_fail

  # deploy and validate app pods on storage pools and expand PVCs created as part of 'kadalu_operator' case
  deploy_app_pods

  # modifies existing storage pool to check for changes in kadalu resources
  modify_pool

  # validates all kadalu resource pods are up or not after modifying pools
  wait_for_kadalu_pods 400
  _check_test_fail

  # Run minimal IO test
  run_io

  # Run CSI Sanity tests
  run_sanity

  # Test Storage-Options
  # verify_storage_options

  # check for test failure
  _check_test_fail

  # log required containers logs to stdout
  _log_msgs

  # delete k3d cluster
  _teardown_k3d
}

main
