. "./tests_v2/scripts/helpers.sh"

k="kubectl -nkadalu "
local_timeout=${1:-200}
end_time=$(($(date +%s) + $local_timeout))

# wait for kadalu pods creation
while [[ \
         $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=kadalu-csi-provisioner | wc -l) -eq 0 || \
             $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=kadalu-csi-nodeplugin | wc -l) -eq 0 ]] \
      ; do
    [[ $end_time -lt $(date +%s) ]] && echo Kadalu CSI pods are not created && check_test_fail 1
    sleep 2
done

# check for csi provisioner
kubectl -n kadalu wait --for=condition=ready pod -l app.kubernetes.io/name=kadalu-csi-provisioner --timeout=${local_timeout}s || {
    echo Kadalu CSI Provisioner is not up within ${local_timeout}s && check_test_fail 1
}
echo Kadalu CSI Provisioner is in Ready state
kubectl -n kadalu get pods -l app.kubernetes.io/name=kadalu-csi-provisioner

# check for csi nodeplugin
kubectl -n kadalu wait --for=condition=ready pod -l app.kubernetes.io/name=kadalu-csi-nodeplugin --timeout=${local_timeout}s || {
    echo Kadalu CSI NodePlugin is not up within ${local_timeout}s && check_test_fail 1
}
echo Kadalu CSI Nodeplugin is in Ready state
kubectl -n kadalu get pods -l app.kubernetes.io/name=kadalu-csi-nodeplugin
