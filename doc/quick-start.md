# Quick Start

Install Kadalu kubectl plugin using,

```console
$ sudo pip3 install kubectl-kadalu
```
Note: need `sudo` for installing a binary in `/usr/local/bin`


Deploy KaDalu Operator using,

```console
$ kubectl kadalu install
```

In the case of OpenShift, deploy Kadalu Operator using,

```console
$ oc kadalu install --type=openshift
```

**Note**: Security Context Constraints can be applied only by admins, Run `oc login -u system:admin` to login as admin

Identify the devices available from nodes and run the following command to add storage to Kadalu.

NOTE: if your host is running RHEL/CentOS 7.x series or Ubuntu/Debian older than 18.04, you may need to do below tasks before adding storage to kadalu.

```
# On CentOS7.x/Ubuntu-16.04
sudo wipefs -a -t dos -f /dev/sdc
sudo mkfs.xfs /dev/sdc
```

Once the device is ready, add it to kadalu pool.

```console
$ kubectl kadalu storage-add storage-pool-1 \
    --device kube1:/dev/sdc
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
