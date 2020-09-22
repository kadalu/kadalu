# CSI to claim Persistent Volumes (PVC/PV)

Now we are ready to create Persistent volumes and use them in application Pods.

Create PVC using,
```yaml
# file: sample-pvc.yaml
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: pv1
spec:
  storageClassName: kadalu.replica1
  accessModes:
    - ReadWriteOnce # You can also provide 'ReadWriteMany' here
  resources:
    requests:
      storage: 1Gi
```

```console
$ kubectl apply -f ./sample-pvc.yaml
persistentvolumeclaim/pv1 created
```

and check the status of PVC using,

```console
$ kubectl get pvc
NAME   STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS     AGE
pv1    Bound    pvc-8cbe80f1-428f-11e9-b31e-525400f59aef   1Gi        RWO            kadalu.replica1  42s
```

Now, this PVC is ready to be consumed in your application pod. You can see the
sample usage of PVC in an application pod by below:

```yaml
# file: sample-app.yaml
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
$ kubectl apply -f ./sample-app.yaml
pod1 created
```

[![asciicast](https://asciinema.org/a/259951.svg)](https://asciinema.org/a/259951)
