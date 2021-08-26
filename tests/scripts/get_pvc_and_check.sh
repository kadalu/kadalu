yaml_file=$1
log_text=$2
pod_count=$3
time_limit=$4
fail=0

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
