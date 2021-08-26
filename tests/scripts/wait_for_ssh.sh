tries=100
while ((tries > 0)); do
    if minikube ssh echo connected &>/dev/null; then
	return 0
    fi
    tries=$((tries - 1))
    sleep 0.1
done
echo ERROR: ssh did not come up >&2
exit 1
