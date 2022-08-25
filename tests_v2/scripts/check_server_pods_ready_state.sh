. "./tests_v2/scripts/helpers.sh"

k="kubectl -nkadalu "
local_timeout=${1:-200}
end_time=$(($(date +%s) + $local_timeout))

# wait for kadalu pods creation
while [[ $($k get pod --ignore-not-found -o name -l app.kubernetes.io/name=server | wc -l) -eq 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Kadalu server pods are not created && check_test_fail 1
    sleep 2
done

kubectl -n kadalu wait --for=condition=ready pod -l app.kubernetes.io/name=server --timeout=${local_timeout}s || {
    echo Kadalu Server pods are not up within ${local_timeout}s && check_test_fail 1
}
echo Kadalu Server pods are in Ready state
kubectl -n kadalu get pods -l app.kubernetes.io/name=server
