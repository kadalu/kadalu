# Troubelshooting

This page is a collection for some common problems and their solution

## not all pods are started - `error when creating "/kadalu/templates/csi-driver-object.yaml"`

Kadalu-oerator spins upseveral pods like `csi-provisioner` or `csi-nodeplugin`. In case you don't see them expect the `operator`-pod check the log of the pod.

```console
$ kubectl get pods -n kadalu
NAME                        READY   STATUS    RESTARTS   AGE
operator-68649f4bb6-zq7fp   1/1     Running   0          126m
```

```
...
Traceback (most recent call last):
  File "/kadalu/main.py", line 475, in <module>
    main()
  File "/kadalu/main.py", line 458, in main
    deploy_csi_pods(core_v1_client)
  File "/kadalu/main.py", line 394, in deploy_csi_pods
    execute(KUBECTL_CMD, "create", "-f", filename)
  File "/kadalu/kadalulib.py", line 60, in execute
    raise CommandException(proc.returncode, out.strip(), err.strip())
kadalulib.CommandException: [1] b'' b'Error from server (AlreadyExists): error when creating "/kadalu/templates/csi-driver-object.yaml": csidrivers.storage.k8s.io "kadalu" already exists'
```

If the log complains about ` error when creating "/kadalu/templates/csi-driver-object.yaml"` you might delete the `CSIDriver` as follows

```console
$ kubectl delete CSIDriver kadalu
```

> **Note**: Use the [cleanup script](https://github.com/kadalu/kadalu/blob/master/extras/scripts/cleanup) to properly cleanup kadalu.

## Storage cannot be created - `Failed to create file system	 fstype=xfs device=/dev/md3`

If storage cannot be created, check the logs. In case of the following error

```
+ pid=0
+ cmd=/usr/bin/python3
+ script=/kadalu/server.py
+ trap 'kill ${!}; term_handler' SIGTERM
+ pid=6
+ true
+ /usr/bin/python3 /kadalu/server.py
+ wait 7
+ tail -f /dev/null
[2020-01-06 13:21:41,200] ERROR [glusterfsd - 107:create_and_mount_brick] - Failed to create file system fstype=xfs device=/dev/md3
```

... you might check your disk config and ensure that there are no partitions and especially no partition table on the disk. The following command may be handy to delete the partition table

```console
$ wipefs -a -t dos -f /dev/md3/
```
