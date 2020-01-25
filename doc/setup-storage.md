# Setup Storage

Prepare your configuration file.

KaDalu Operator listens to Storage setup configuration changes and starts the required pods. For example,

```yaml
# File: storage-config.yaml
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
 # This will be used as name of PV Hosting Volume
  name: storage-pool-1
spec:
  type: Replica1
  storage:
    - node: kube1      # node name as shown in `kubectl get nodes`
      device: /dev/vdc # Device to provide storage to all PVs
```

More config options can be found [here](doc/storage-config-options.md)

Now request kadalu-operator to setup storage using,

```console
$ kubectl create -f storage-config.yaml
```

Operator will start the storage export pods as required. And, in 2 steps,
your storage system is up and running.

Check the status of Pods using,

```console
$ kubectl get pods -nkadalu
NAME                             READY   STATUS    RESTARTS   AGE
server-storage-pool-1-kube1-0    1/1     Running   0          84s
csi-nodeplugin-5hfms             2/2     Running   0          30m
csi-nodeplugin-924cc             2/2     Running   0          30m
csi-nodeplugin-cbjl9             2/2     Running   0          30m
csi-provisioner-0                3/3     Running   0          30m
operator-6dfb65dcdd-r664t        1/1     Running   0          30m
```

[![asciicast](https://asciinema.org/a/259949.svg)](https://asciinema.org/a/259949)
