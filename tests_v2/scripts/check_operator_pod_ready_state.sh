. "./tests_v2/scripts/helpers.sh"

k="kubectl -nkadalu "
local_timeout=${1:-200}
end_time=$(($(date +%s) + $local_timeout))

# Check if atleast one Operator pod creation started
while [[ $($k get pod --ignore-not-found -o name -l name=kadalu | wc -l) -eq 0 ]]; do
    [[ $end_time -lt $(date +%s) ]] && echo Kadalu Operator pods are not created && check_test_fail 1
    sleep 2
done

# check for operator
$k wait --for=condition=ready pod -l name=kadalu --timeout=${local_timeout}s || {
    echo Kadalu Operator is not up within ${local_timeout}s && check_test_fail 1
}
echo Kadalu Operator is in Ready state
$k get pods -l name=kadalu
