# Try Kadalu

We believe the success of a project depends on  how easy it is for a developer
or an user to try out the project, get a hang of it.

As part of that, we have decided the overall install process of the storage
system should be 2 step process.

1. Get the operator installed, which sets up required configmap, CSI drivers,
   and CRD details.
2. Provide inventory (ie, machine:disk combination) to the system, so it can
   setup storage subsystem on it.

In the initial versions, we would like to keep the 2nd step manual, ie, admin
has to provide details of storage. Later, we can enhance it to pick the
storage based on the tag etc. If it is cloud, with required auth keys,
it can setup the Storage within operator itself.

## Give it a try with 'minikube'

[`minikube`](https://kubernetes.io/docs/setup/minikube/) is a good way to get a hang of k8s for beginners. If you already have a k8s setup available to test out, skip this step, and goto [Next step](#try-kadalu)

You can follow ['Install minikube'](https://kubernetes.io/docs/tasks/tools/install-minikube/) document to setup minikube. Please note that if you are using `minikube version` below 1.17.0, use `--vm-driver=none` option. More on this issue is recorded at [kadalu/issue#351](https://github.com/kadalu/kadalu/issues/351).

## Try kadalu

For testing, login to minikube and create a virtual device as below.

```bash
$ cd /mnt/vda1/
$ sudo truncate -s 10G storage-pool-1.disk.img
```

After this follow our [Homepage](https://github.com/kadalu/kadalu). You are good to get started.

## Further considerations

### What do we do when we have more storage nodes?

We understand many examples given are for setting up it on 1 node, 1 device. When you have more storage you need to export, then just export more storage in the multiple of Replica count.

For example:

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
    - node: kube1        # node name as shown in `kubectl get nodes`
      device: /dev/vdc
    - node: kube2
      device: /dev/vdd
    - node: kube3
      device: /dev/vdc
```

NOTE: If you are using kadalu versions below 0.8.0, then please refer to document on 0.7.7 version.

### how to configure kadalu to have at least one mirroring data in case of some crash?

The answer we have is, providing kadalu-config using 3 nodes, and using gluster replicate module (replica 3). The sample looks something like below:

```yaml
# File: storage-config.yaml
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
  # This will be used as name of PV Hosting Volume
  name: storage-replica-pool-1
spec:
  type: Replica3  # Notice that this field tells kadalu operator to use replicate module.
  storage:
    - node: kube1      # node name as shown in `kubectl get nodes`
      device: /dev/vdc # Device to provide storage to all PV
    - node: kube2      # node name as shown in `kubectl get nodes`
      device: /dev/vdd # Device to provide storage to all PV
    - node: kube3      # node name as shown in `kubectl get nodes`
      device: /dev/vdc # Device to provide storage to all PV
---
```

With this, there will be 3 bricks, and kadalu CSI driver will mount the corresponding volume and provide data.

**NOTE**: There can be both replica1 and replica3 type volume co-existing in the system. Note that while claiming the PV, you just need to provide `storageClassName: kadalu.replica1` or `storageClassName: kadalu.replica3` to use the relevant option.

### On data recovery

As we use glusterfs as storage backend, without any sharding/striping/disperse mode, the data remains as is, on your backend storage. Just that each PV would be a subdirectory on your storage. So, no need to panic.

### On upgrade

As long as glusterfs promises to keep the backend layout same, and continue to provide storage after upgrade, we don't see any issue with upgrade. Currently one known issue is that our operator is not checking for heal pending count while upgrading storage pods.


### Gluster and Kadalu

We have compiled a list of things [here](./gluster-and-kadalu.md)
