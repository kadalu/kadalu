cnt=0
fail=0
local_timeout=${1:-200}
while true; do
    cnt=$((cnt + 1))
    sleep 2
    ret=$(kubectl get pods -nkadalu -o wide | grep 'Running' | wc -l)
    if [[ $ret -ge 12 ]]; then
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
