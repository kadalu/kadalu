# KaDalu

[![Build Status](https://travis-ci.org/kadalu/kadalu.svg?branch=master)](https://travis-ci.org/kadalu/kadalu)
[![Operator Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg?label=DockerPulls%20Operator)](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg)
[![Server Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg?label=DockerPulls%20Server)](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg)

>
>**Note 1:** If you like the project, give a github star :-)
>

- [KaDalu](#kadalu)
  - [Introduction](#introduction)
  - [Get Started](#get-started)
    - [Pre-Requisites](#pre-requisites)
    - [Setup](#setup)
  - [CSI to claim Persistent Volumes (PVC/PV)](#csi-to-claim-persistent-volumes-pvcpv)
  - [NOTE](#note)
  - [Troubleshooting](#troubleshooting)
  - [Talks and Blog posts](#talks-and-blog-posts)
  - [Reach out to some of the developers](#reach-out-to-some-of-the-developers)

## Introduction

Kadalu project started with a goal of keeping minimum layers to provide Persistent Volumes in k8s eco system. kadalu uses 'GlusterFS' as soul to provide storage, but strips off 'gluster' project's management layer.

The focus of the project is simplicity and stability. We believe simple things can solve things better, instead of complicating already complicated eco-system.

## Get Started

### Pre-Requisites

- Kubernetes 1.13.0 + version
- The host should support xfs (`mkfs.xfs`)
- The `mount -t xfs` with `-oprjquota` should work

### Setup

1. Deploy KaDalu Operator using,

   ```console
   kubectl create -f https://raw.githubusercontent.com/kadalu/kadalu/master/manifests/kadalu-operator.yaml
   ```

   In the case of OpenShift, deploy Kadalu Operator using,

   ```console
   oc create -f https://raw.githubusercontent.com/kadalu/kadalu/master/manifests/kadalu-operator-openshift.yaml
   ```

   **Note:** Security Context Constraints can be applied only by admins,
Run `oc login -u system:admin` to login as admin

2.1 Prepare your configuration file.

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

You have more options for config file. Check them [here](doc/storage-config-options.md)

2.2 Now request kadalu-operator to setup storage using,

   ```console
   kubectl create -f storage-config.yaml
   ```

Operator will start the storage export pods as required. And, in 2 steps,
your storage system is up and running.

Check the status of Pods using,

```bash
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

## CSI to claim Persistent Volumes (PVC/PV)

Now we are ready to create Persistent volumes and use them in
application Pods.

Create PVC using,

```bash
$ kubectl create -f examples/sample-pvc.yaml
persistentvolumeclaim/pv1 created
```

and check the status of PVC using,

```bash
$ kubectl get pvc
NAME   STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS     AGE
pv1    Bound    pvc-8cbe80f1-428f-11e9-b31e-525400f59aef   1Gi        RWO            kadalu.replica1  42s
```

Now, this PVC is ready to be consumed in your application pod. You can see the
sample usage of PVC in an application pod by below:

```bash
$ kubectl create -f examples/sample-app.yaml
pod1 created
```

[![asciicast](https://asciinema.org/a/259951.svg)](https://asciinema.org/a/259951)

For more information checkout the [Try it out](./doc/README.md)

If you want 'External' Gluster Storage to be used as PV, checkout [this doc](./doc/external-gluster-storage.md)

## NOTE

We are tracking the number of downloads based on 'docker pull' stats, and also
through google analytics. [This Commit](https://github.com/kadalu/kadalu/commit/cbc83fd751bf0221e22b61bd6ebad4af40e38275) gives detail of what is added to code w.r.to tracking.

## Troubleshooting

see [Troubleshooting](./doc/troubleshooting.md)

## Talks and Blog posts

1. [Blog] [Gluster’s management in k8s](https://medium.com/@tumballi/glusters-management-in-k8s-13020a561962)
2. [Blog] [Gluster and Kubernetes - Portmap](https://aravindavk.in/blog/gluster-and-k8s-portmap/)
3. [Talk] [DevConf India - Rethinking Gluster Management using k8s](https://devconfin19.sched.com/event/RVPw/rethinking-gluster-management-using-k8s) ([slides](doc/rethinking-gluster-management-using-k8s.pdf))
4. [Demo] Asciinema recording - [Kadalu Setup](https://asciinema.org/a/259949)
5. [Demo] Asciinema recording - [KaDalu CSI to claim Persistent Volumes](https://asciinema.org/a/259951)
6. [Blog] [kaDalu - Ocean of opportunities](https://medium.com/@tumballi/kadalu-ocean-of-potential-in-k8s-storage-a07be1b8b961?source=friends_link&sk=d2499bc1e7433fd18c93c34c796e1a11&utm_source=github)

## Reach out to some of the developers

You can reach to the developers using certain ways.

1. Best is opening an [issue in github.](https://github.com/kadalu/kadalu/issues)
2. Reach to us on [Slack](https://join.slack.com/t/kadalu/shared_invite/enQtNzg1ODQ0MDA5NTM2LWMzMTc5ZTJmMjk4MzI0YWVhOGFlZTJjZjY5MDNkZWI0Y2VjMDBlNzVkZmI1NWViN2U3MDNlNDJhNjE5OTBlOGU) (Note, there would be no history) - https://kadalu.slack.com
