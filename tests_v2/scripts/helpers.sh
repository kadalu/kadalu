function check_test_fail() {
    local fail=$1
    if [ $fail -eq 1 ]; then
        echo "Marking the test as 'FAIL'"
        _log_msgs $fail
        exit 1
    fi
}

function _log_msgs() {
    local fail=$1
    local lines=100
    if [[ $fail -eq 1 || $COMMIT_MSG =~ 'full log' ]]; then
        lines=1000
    fi
    kubectl get kds --all-namespaces
    kubectl get sc --all-namespaces
    kubectl get pvc --all-namespaces
    for p in $(kubectl -n kadalu get pods -o name); do
        echo "====================== Start $p ======================"
        kubectl logs -nkadalu --all-containers=true --tail=$lines $p
        kubectl -nkadalu describe $p
        echo "======================= End $p ======================="
    done
}
