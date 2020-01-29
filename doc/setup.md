# Setup

### Pre-Requisites

- Kubernetes 1.13.0 + version
- The host should support xfs (`mkfs.xfs`)
  - On some systems this might require installation of xfsprogs package
- The `mount -t xfs` with `-oprjquota` should work

### Setup

Install Kadalu kubectl plugin using,

```console
$ pip3 install kubectl-kadalu
```

Deploy KaDalu Operator using,

```console
$ kubectl kadalu install
```

In the case of OpenShift, deploy Kadalu Operator using,

```console
$ oc kadalu install --type=openshift
```

**Note:** Security Context Constraints can be applied only by admins, Run `oc login -u system:admin` to login as admin
