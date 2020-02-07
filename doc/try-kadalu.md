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

You can follow ['Install minikube'](https://kubernetes.io/docs/tasks/tools/install-minikube/) document to setup minikube. Please note that right now (k8s - 1.14.0) there seems to be some issues with default 'minikube', and hence please use only `--vm-driver=none` option.

To get your minikube host (can be VM image too) setup,, please follow link [here.](https://docs.docker.com/install/linux/docker-ce/fedora/) which lists all the required steps to get started.

## Try kadalu

For testing, login to minikube and create a virtual device as below.

```bash
$ cd /mnt/vda1/
$ sudo truncate -s 10G storage-pool-1.disk.img
```

After this follow our [Homepage](https://github.com/kadalu/kadalu). You are good to get started.

## Further considerations

### What do we do when we have more nodes?

Kadalu's design principles are with couple of assumptions: (ie, In the early development phase).

- The PVC size requirements are going to be lesser than one available disk of any node.
- No need to change settings once Gluster is running (in most of the cases).

With that assumption, lets look into what happens when you have more node. For easier to understand reasons, I am assuming `kadalu.replica1` mode, so there is 1 brick process per a disk (or available storage, like EBS, RAID device, SAN Array etc).

Now, the examples given are for setting up it on 1 node, 1 device. When you have more storage you need to export, then just export more storage with multiple storage config definitions.

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
    - node: kube1      # node name as shown in `kubectl get nodes`
      device: /dev/vdc # Device to provide storage to all PV
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
  # This will be used as name of PV Hosting Volume
  name: storage-pool-2 # **Notice** the name change here
spec:
  type: Replica1
  storage:
    - node: kube2      # node name as shown in `kubectl get nodes`
      device: /dev/vdd # Device to provide storage to all PV
---
apiVersion: kadalu-operator.storage/v1alpha1
kind: KadaluStorage
metadata:
  # This will be used as name of PV Hosting Volume
  name: storage-pool-3 # **Notice** the name change here
spec:
  type: Replica1
  storage:
    - node: kube3       # node name as shown in `kubectl get nodes`
      device: /dev/vdc # Device to provide storage to all PV
```

Note that you just need to provide one more config with different name to host a brick process. Our CSI driver will automatically understand there are 3 volumes which it can connect to, and depending on the available space, will provide storage in one of the gluster volume.

The newer configs can be given at any time, and CSI driver will understand the existence of new storage, (through kadalu operator), and will be consumed when more PV requests come by.

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

Also note that, there can be both replica1 and replica3 type volume co-existing in the system. Note that while claiming the PV, you just need to provide `storageClassName: kadalu.replica1` or `storageClassName: kadalu.replica3` to use the relevant option.

### On data recovery

As we use glusterfs as storage backend, without any sharding/striping/disperse mode, the data remains as is, on your backend storage. Just that each PV would be a subdirectory on your storage. So, no need to panic.

### On upgrade

As long as glusterfs promises to keep the backend layout same, and continue to provide storage after upgrade, we don't see any issue with upgrade. Currently our operator is not checking for newer versions and upgrading itself, but just killing the brick pod when new version is available should fetch new pod and start it back all fine.

### Gluster and Kadalu

We have compiled a list of things [here](./gluster-and-kadalu.md)
