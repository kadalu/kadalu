# KaDalu

[![Build Status](https://travis-ci.org/aravindavk/kadalu.svg?branch=master)](https://travis-ci.org/aravindavk/kadalu)
[![Operator Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg?label=DockerPulls%20Operator)](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg)
[![Server Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg?label=DockerPulls%20Server)](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg)

**Note 1:** kaDalu project is still in its infancy, not yet ready for production
  use.

**Note 2:** If you are using 'minikube' to try out kaDalu, then please use
`--vm-driver=none` option. In our testing, we found issues specific to CSI pods
when we used `kvm2` driver.

## Get Started

Deploy KaDalu Operator using,

```
kubectl create -f https://raw.githubusercontent.com/aravindavk/kadalu/master/manifests/kadalu-operator.yaml
```

KaDalu Operator listens to Storage setup configuration changes and
starts the required pods. For example,

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

Now request kadalu-operator to setup storage using,

```
$ kubectl create -f storage-config.yaml
```

Operator will start the storage export pods as required. And, in 2 steps,
your storage system is up and running.

Check the status of Pods using,

```
$ kubectl get pods -nkadalu
NAME                             READY   STATUS    RESTARTS   AGE
server-storage-pool-1-kube1-0    1/1     Running   0          84s
csi-attacher-0                   2/2     Running   0          30m
csi-nodeplugin-5hfms             2/2     Running   0          30m
csi-nodeplugin-924cc             2/2     Running   0          30m
csi-nodeplugin-cbjl9             2/2     Running   0          30m
csi-provisioner-0                3/3     Running   0          30m
operator-6dfb65dcdd-r664t        1/1     Running   0          30m
```


[![asciicast](https://asciinema.org/a/259949.svg)](https://asciinema.org/a/259949)


## CSI to claim Persistent Volumes (PVC/PV)

Now we are ready to create Persistent volumes and use them in
application Pods.

Create PVC using,

```
$ kubectl create -f examples/sample-pvc.yaml
persistentvolumeclaim/pv1 created
```

and check the status of PVC using,

```
$ kubectl get pvc
NAME   STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS     AGE
pv1    Bound    pvc-8cbe80f1-428f-11e9-b31e-525400f59aef   1Gi        RWO            kadalu.replica1  42s
```

Now, this PVC is ready to be consumed in your application pod. You can see the
sample usage of PVC in an application pod by below:

```
$ kubectl create -f examples/sample-app.yaml
pod1 created
```

[![asciicast](https://asciinema.org/a/259951.svg)](https://asciinema.org/a/259951)

## NOTE

We are tracking the number of downloads based on 'docker pull' stats, and also
through google analytics. [Issue #16](issues/16) gives detail of what is added
to code w.r.to tracking.

## Talks and Blog posts

1. [Blog] [Gluster’s management in k8s](https://medium.com/@tumballi/glusters-management-in-k8s-13020a561962)
2. [Blog] [Gluster and Kubernetes - Portmap](https://aravindavk.in/blog/gluster-and-k8s-portmap/)
3. [Talk] [DevConf India - Rethinking Gluster Management using k8s](https://devconfin19.sched.com/event/RVPw/rethinking-gluster-management-using-k8s) ([slides](doc/rethinking-gluster-management-using-k8s.pdf))
4. [Demo] Asciinema recording - [Kadalu Setup](https://asciinema.org/a/259949)
5. [Demo] Asciinema recording - [KaDalu CSI to claim Persistent Volumes](https://asciinema.org/a/259951)
