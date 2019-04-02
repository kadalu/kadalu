# Try it out

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

[`minikube`]() is a good way to get a hang of k8s for beginners. If you already have a k8s setup available to test out, skip this step, and goto [Next step](./#try-kadalu)

You can follow ['Install minikube'](https://kubernetes.io/docs/tasks/tools/install-minikube/) document to setup minikube. Please note that right now (k8s - 1.14.0) there seems to be some issues with default 'minikube', and hence please use only `--vm-driver=none` option.

To get your minikube host (can be VM image too) setup,, pleasefollow link [here.](https://docs.docker.com/install/linux/docker-ce/fedora/) This provides all the required basic steps to get started.


## Try kadalu

For testing, login to minikube and create a virtual device as below.

```
$ cd /mnt/vda1/
$ sudo truncate -s 10G gvol1.disk.img
$ sudo mkfs.xfs gvol1.disk.img
$ sudo mkdir /mnt/data
$ sudo mount gvol1.disk.img /mnt/data
```

After this follow our [Homepage](https://github.com/aravindavk/kadalu). You are good to get started.


