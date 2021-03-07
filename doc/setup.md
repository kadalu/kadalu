# Setup

### Pre-Requisites

- Kubernetes 1.13.0 + version
- The host should support xfs (`mkfs.xfs`)
  - On some systems this might require installation of xfsprogs package

### Setup

Download the latest release of Kadalu Kubectl plugin using,

```
curl -LO https://github.com/kadalu/kadalu/releases/download/0.8.0/kubectl-kadalu
```

Make the kubectl binary executable.

```
chmod +x ./kubectl-kadalu
```

Move the binary in to your PATH.

```
sudo mv ./kubectl-kadalu /usr/local/bin/kubectl-kadalu
```

Note: In the case of Openshift,

```
sudo mv ./kubectl-kadalu /usr/local/bin/oc-kadalu
```

Test to ensure the version you installed is up-to-date

```
$ kubectl-kadalu version
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
