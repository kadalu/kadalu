# Setup

### Pre-Requisites

- Kubernetes 1.13.0 + version
- The host should support xfs (`mkfs.xfs`)
  - On some systems this might require installation of xfsprogs package
- The `mount -t xfs` with `-oprjquota` should work

### Setup

Deploy KaDalu Operator using,

```console
$ kubectl create -f https://raw.githubusercontent.com/kadalu/kadalu/master/manifests/kadalu-operator.yaml
```

In the case of OpenShift, deploy Kadalu Operator using,

```console
$ oc create -f https://raw.githubusercontent.com/kadalu/kadalu/master/manifests/kadalu-operator-openshift.yaml
```

**Note:** Security Context Constraints can be applied only by admins, Run `oc login -u system:admin` to login as admin
