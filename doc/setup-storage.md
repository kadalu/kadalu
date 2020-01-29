# Setup Storage


Identify the devices available from nodes and run the following command to add storage to Kadalu.

```console
$ kubectl kadalu storage-add storage-pool-1 \
    --device kube1:/dev/vdc
```

Run `kubectl kadalu storage-add --help` to see all the available options

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
