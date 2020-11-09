# Use external gluster volume as PV in kadalu

You can still use kadalu even when you have your storage nodes outside
of the kubernetes (k8s) cluster. We describe this `kind` of setup as
'External'. Such a description is intended to indicate that the storage
server processes are not managed by kadalu operator.

## Using external gluster in kadalu native way

In this mode, we expect gluster volume to be created and is in 'Started' state.
kadalu storage config takes one of the node IP/hostname, and gluster volume name
to use it as the storage for PVs. The PVs would be provided as subdirectories -
this is similar to how a PV is created in kadalu native way.

In order for resources.requests.storage requests to be honored please read [the server documentation](../server/README.md).

The best example for this is, what we use in our CI. Checkout this
sample yaml file

```yaml
# file: external-config.yaml
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
  name: ext-config
spec:
  type: External
  details:
    - gluster_host: gluster1.kadalu.io
      gluster_volname: kadalu
      gluster_options: log-level=DEBUG


# file: pvc-from-external-gluster.yaml
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pv-ext-kadalu
spec:
  # Add 'kadalu.external.' to name from KadaluStorage kind
  storageClassName: kadalu.external.ext-config
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      # This needs to be set using 'kadalu-quotad'
      storage: 500Mi

```

Please edit 'gluster_host' and 'gluster_volname' parameters in config section.

You can also setup the external storage through our `kubectl kadalu` CLI.

```console
$ kubectl kadalu storage-add store-name --external gluster.kadalu.io:/kadalu
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
treat that also as 'External' and use kadalu to manage it. In this case, you
will need to provide the pre-created gluster volume name for the config.


## Using external storage directly

In this mode, 1 Gluster Volume would be 1 PV. Something very similar to how heketi
project allocates PVs. We don't encourage using this mode, nor recommend it in a
new setup. This mode is provided just as an option for those who are consuming
gluster volumes in this mode. This helps to use the PVs used in other deployments
to be still consumed.

In this mode, you don't need storage config, but all you need is to have a sample
like below

```yaml
# file: external-gluster-as-pv.yaml
---
kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: kadalu.external.pv-ext # Keep changing the name for different volumes
provisioner: kadalu
parameters:
  hostvol_type: "External"
  gluster_host: gluster1.kadalu.io   # Change to your gluster host
  gluster_volname: test              # Change to existing gluster volume
  gluster_options: log-level=DEBUG   # Comma separated options

---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pv-ext
spec:
  storageClassName: kadalu.external.pv-ext
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 200Mi # This gets ignored in this case.
```

Please edit 'gluster_host' and 'gluster_volname' parameters in Storage Class.

Then run `kubectl apply -f ./external-gluster-as-pv.yaml`

Note that in this mode, there would be as many 'StorageClass' as number of PVs, but
that is not avoidable at present because we can't pass user driven input from PV claim
yaml.
