# Unless there is a failure or COMMIT_MSG contains 'full log' just log last 100 lines
lines=100
if [[ $FAILED = "1" || $COMMIT_MSG =~ 'full log' ]]; then
    lines=1000
fi

for p in $(kubectl -n kadalu get pods -o name); do
    echo "====================== Start $p ======================"
    kubectl logs -nkadalu --all-containers=true --tail=$lines $p
    echo "======================= End $p ======================="
done

date
