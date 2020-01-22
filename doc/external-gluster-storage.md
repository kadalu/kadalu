# Use external gluster volume as PV in kadalu

If you are having your storage nodes outside of kubernetes cluster, you
can still use kadalu. We call the `kind` of this setup as 'External' mainly
because, the storage server processes are not managed by kadalu operator
in this case.

## Using external gluster in kadalu native way

In this mode, we expect gluster volume to be created and is in 'Started' state.
kadalu storage config takes one of the node IP/hostname, and gluster volume name
to use it as the storage for PVs. The PVs would be provided as subdirectories,
similar to how a PV is created in kadalu native way.

The best example for this is, what we use in our CI. Checkout this
[sample yaml file](../examples/sample-external-kadalu-storage.yaml).

Please edit 'gluster_host' and 'gluster_volname' parameters in config section.

You can also setup the external storage through our `kubectl kadalu` CLI.

```console
kubectl kadalu storage-add store-name --external gluster.kadalu.io:/kadalu
```

After this, just use `kadalu.external.store-name` (note that 'store-name' is
name used for `storage-add`) in PVC yaml, like below:

```
...
spec:
  storageClassName: kadalu.external.store-name
  ...
```

Note that, if you have an existing gluster setup inside the k8s cluster, you can
treat that also as 'External' and use kadalu to manage it. All you need to provide
is pre-created gluster volume name for the config.


## Using external storage directly

In this mode, 1 Gluster Volume would be 1 PV. Something very similar to how heketi
project allocates PVs. We don't encourage using this mode, nor recommend it in a
new setup. This mode is provided just as an option for those who are consuming
gluster volumes in this mode. This helps to use the PVs used in other deployments
to be still consumed.

In this mode, you don't need storage config, but all you need is to have a sample like
[`examples/sample-external-storage.yaml`](../examples/sample-external-storage.yaml).

Please edit 'gluster_host' and 'gluster_volname' parameters in Storage Class.

Then run `kubectl create -f ./examples/sample-external-storage.yaml`

Note that in this mode, there would be as many 'StorageClass' as number of PVs, but
that is not avoidable at present because we can't pass user driven input from PV claim
yaml.

