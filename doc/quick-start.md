# Quick Start

Deploy KaDalu Operator using,

```console
$ kubectl create -f https://kadalu.io/operator-latest.yaml
```

In the case of OpenShift, deploy Kadalu Operator using,

```console
$ oc create -f https://kadalu.io/operator-openshift-latest.yaml
```

**Note**: Security Context Constraints can be applied only by admins, Run `oc login -u system:admin` to login as admin

Prepare your configuration file.

KaDalu Operator listens to Storage setup configuration changes and starts the required pods. For example,

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
        device: /dev/vdc  # Device to provide storage to all PVs
```

Now request kadalu-operator to setup storage using,

```console
$ kubectl create -f storage-config.yaml
```

Operator will start the storage export pods as required. And, in 2 steps, your storage system is up and running.

Check the status of Pods using,

```console
$ kubectl get pods -n kadalu
NAME                             READY   STATUS    RESTARTS   AGE
server-storage-pool-1-kube1-0    1/1     Running   0          84s
csi-attacher-0                   2/2     Running   0          30m
csi-nodeplugin-5hfms             2/2     Running   0          30m
csi-nodeplugin-924cc             2/2     Running   0          30m
csi-nodeplugin-cbjl9             2/2     Running   0          30m
csi-provisioner-0                3/3     Running   0          30m
operator-6dfb65dcdd-r664t        1/1     Running   0          30m
```

## CSI to claim Persistent Volumes (PVC/PV)

Now we are ready to create Persistent volumes and use them in application Pods.

```yaml
# File: sample-pvc.yaml
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pv1
spec:
  storageClassName: kadalu.replica1
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 1Gi
```

Create PVC using,

```console
$ kubectl create -f sample-pvc.yaml
persistentvolumeclaim/pv1 created
```

and check the status of PVC using,

```console
$ kubectl get pvc
NAME   STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS     AGE
pv1    Bound    pvc-8cbe80f1-428f-11e9-b31e-525400f59aef   1Gi        RWO            kadalu.replica1  42s
```

Now, this PVC is ready to be consumed in your application pod. You can see the sample usage of PVC in an application pod by below:

```yaml
# File: sample-app.yaml
---
apiVersion: v1
kind: Pod
metadata:
  name: pod1
  labels:
    app: sample-app
spec:
  containers:
  - name: sample-app
    image: docker.io/kadalu/sample-pv-check-app:latest
    imagePullPolicy: IfNotPresent
    volumeMounts:
    - mountPath: "/mnt/pv"
      name: csivol
  volumes:
  - name: csivol
    persistentVolumeClaim:
      claimName: pv1
  restartPolicy: OnFailure
```

```console
$ kubectl create -f sample-app.yaml
pod1 created
```
