# Kadalu Storage Config

Storage configuration is core of the kadalu.io project. This config file provides details of which devices provide PVs, and what type (Replica1/Replica3 or other). Kadalu operator reads this config file, and starts the relevant gluster server pods exporting the storage provided in the config.

The features of kadalu project comes from options in storage-config file. In this document we will provide details of each options possible in config file.

## Config file format.

Let us look into below sample config file.

```yaml
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
 # This will be used as name of PV Hosting Volume
  name: storage1
spec:
  type: Replica1
  storage:
    - node: kube1
      device: /dev/vdc
```

For now,
* `apiVersion` will always be having value of `kadalu-operator.storage/v1alpha1`.
* `kind` will always be having value of `KadaluStorage`. kadalu operator only understands config of this **kind**.
* `metadata` is required, and should have an entry for 'name', which will be used as 'gluster's volume name and pod names.
* `spec` field should be required, and should have `type` field.

The above 3 fields will be common for config files for all different modes.


## Native mode

In this mode, the storage is provided from inside of the kubernetes cluster. Lets look at how native mode can be configured in each these options.

### Type

Native mode is available with 3 `type` options. They are `Replica1`, `Replica2` and another `Replica3`.

* 'Replica1'

In this mode, Gluster will be started without high availability, i.e without replicate module. It will use just one storage, from which the RWX and RWO PVs will be carved out. This storage will be exposed by a gluster server pod, which gets spawned by kadalu operator.

```
$ kubectl kadalu storage-add storage-pool1 --type=Replica1 \
    --device kube-nodename1:/dev/vdc
```

To create a PVC from this storage, you need to provide `storageClassName` option as `kadalu.replica1`.


* 'Replica2'

In this mode, Gluster will be started with high availability, with 'tie-breaker' (or thin-arbiter in gluster speak) option. It will use 2 storage options, from which the RWX and RWO PVs will be carved out. This storage will be exposed by a gluster server pod, which gets spawned by kadalu operator. The `tiebreaker` node has to be managed outside, and if the user doesn't want to host it, kadalu provides a free service for the same, which can be consumed by not providing any `tiebreaker` option :-)

```
...
spec:
  type: Replica2
  storage:
    - ...
    - ...
  tiebreaker:
    node: ...
    path: ...
...
```

To create a PVC from this storage, you need to provide `storageClassName` option as `kadalu.replica2`.

* 'Replica3'

In this mode, Gluster will started with high availability, ie, replicate module. It will require 3 storage options to be provided, and each storage will be one gluster server process pod running as pod.

```
$ kubectl kadalu storage-add storage-pool1 --type=Replica3 \
    --device kube-nodename1:/dev/vdc \
    --device kube-nodename2:/dev/vdc \
    --device kube-nodename3:/dev/vdc \
```

To create a PVC from this storage, you need to provide `storageClassName` option as `kadalu.replica3`.


### Storage

The native mode storage can be provided by many different types in kadalu. Lets look into each of those, with samples.


#### Storage from Device

In this case, a device (`/dev/sd*` or similar), attached to a node in k8s cluster is provided as storage. The device is exported into the gluster server pod, and is formatted and mounted into specific brick path.

The sample command looks like below:

```
$ kubectl kadalu storage-add storage-pool1 \
    --device kube-nodename:/dev/vdc
```

Note that both `node` and `device` fields are required. A device info without a node doesn't contain all the required information for kadalu operator to start the brick process.

According to us, this is most common way of providing the storage to kadalu.

Also, if `device` option has a file as option, the same file will be formatted and used as device too. This is particularly helpful as a testing option, where from same backend multiple devices needs to be carved out. Our CI/CD tests use this approach.


#### Storage from path

In this case, a directory path (/mnt/mount/path or similar) is exported as a brick from a node in the cluster as storage for gluster server process. This is particularly useful when a larger device is mounted and shared with other applications too.

Note that path option is valid only if the file system on the given path is xfs, and is mounted with `prjquota` mount option. path option is helpful for those who want to try kadalu in an existing setup. When path option is provided, kadalu operator doesn't try to format and mount, but uses the path as export path for kadalu storage volume.

The sample command looks like below:

```
$ kubectl kadalu storage-add storage-pool1 \
    --path kube-nodename:/mnt/mount/export-path
```

Again here, both `node` and `path` are required fields. kadalu operator won't have all required information to start gluster server pods without these two fields.


#### Storage from another PVC

This is an interesting option, and makes sense specifically in a cloud environment, where a virtual storage device would be available as PVC in k8s cluster. kadalu can use a PVC, which is not bound to any 'node' as the storage, and provide multiple smaller PVCs through kadalu storageclass.

In this case, a PVC is exposed to kadalu's server pod as storage through `volumes` option of pod config. With that the given PVC exposed into the server pods, we expose the given storage through gluster.

The sample config looks like below:

```
$ kubectl kadalu storage-add storage-pool1 \
    --pvc pvc-name-in-namespace
```

Note that this PVC should be available in 'kadalu' namespace. Also there is no need of mentioning `node` field for this storage. k8s itself will start pod in relevant node in cluster.


## External mode

In this mode, storage will be provided by gluster servers not managed by kadalu operator. Note that in this case, the gluster server can be running inside or outside k8s cluster.

The external mode can be specified with `type` as `External`. And when the type is External, the field it expects is `details`. Lets look at a sample, and then describe each of the options it takes.


```
$ kubectl kadalu storage-add storage-pool1 \
    --external gluster_host:/gluster_volname
```

Above,

* 'gluster_host': This option takes one hostname or IP address, which is accessible from the k8s cluster.
* 'gluster_volname': Gluster volume name to be used as kadalu host storage volume. We prefer it to be a new volume created for kadalu.


Notice that to create PVC from External Storage config, you need to provide `storageClassName` option as `kadalu.external.{{ config-name }}`. In above case, it becomes **`kadalu.external.ext-config`**.


### How it works

kadalu operator doesn't start any storage pods when 'External' type is used, but creates a `StorageClass` particular to this config, so when a PVC is created, the information is passed to the CSI drivers. The host-volume is mounted as below:

```
mount -t glusterfs {{ gluster_host }}:/{{ gluster_volname }} -o{{gluster_options}} /mount/point
```

Other than this, the CSI volume's behavior would be same for both Native mode, and External mode.


### External Storage for non-kadalu mode.

This is a hidden option provided in kadalu to access a gluster volume as a whole as PV. This is particularly useful if one wants to use an already existing Gluster volume as a PV (for example, a gluster volume created by heketi). We don't recommend this for normal usage, as this mode would have scale limitations, and also would add more k8s resources likes StorageClass.

This option is not provided using storage config, but admin/user has to create a StorageClass themselves with external gluster information. The example config file added for CI/CD gives an idea about options. Note that the options provided here looks same as whats given in storage config, but when kadalu operator creates the StorageClass, it adds another field `kadalu-format: true`. Refer the [external-storage document](./external-gluster-storage.md) for more information on this mode.
