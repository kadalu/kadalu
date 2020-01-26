# Deploying Minio

Generate and download the `minio-deployment.yaml` file from the [minio
website](https://min.io/download#/kubernetes)

Update `storageClassName` as `storageClassName: kadalu.replica1` and
update the unit of size. For example, `storage: 2G`

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: minio-pv-claim
  labels:
    app: minio-storage-claim
spec:
  accessModes:
    - ReadWriteOnce
  resources:
    requests:
      storage: 2G
  storageClassName: kadalu.replica1
```

Now deploy the Minio by running,

```console
$ kubectl create -f minio-deployment.yaml
persistentvolumeclaim/minio-pv-claim created
deployment.extensions/minio-deployment created
service/minio-service created
```

Verify the status of the PVC using,

```console
$ kubectl get pvc
NAME             STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
minio-pv-claim   Bound    pvc-004c14f7-0f35-471d-b551-0de351af09f8   2Gi        RWO            kadalu.replica1   25s
```

Verify the status of the pod using,

```console
NAME                               READY   STATUS    RESTARTS   AGE
minio-deployment-77d65cb56-mnx9t   1/1     Running   0          81s
```

Get the IP of that pod by running,

```console
$ kubectl get pods -owide
NAME                               READY   STATUS    RESTARTS   AGE     IP           NODE       NOMINATED NODE   READINESS GATES
minio-deployment-77d65cb56-mnx9t   1/1     Running   0          2m16s   172.17.0.9   minikube   <none>           <none>
```

Get the node port by running,

```console
$ kubectl describe service minio-service | grep NodePort
NodePort:                 <unset>  31119/TCP
```

Now access minio here http://172.17.0.9:31119/minio/login

If the node IP is not externally accessible, then use port forwarding as
below.

```console
$ kubectl port-forward svc/minio-service --address 0.0.0.0 8000:9000
```

Now access minio from your laptop using
http://\<ip-of-node\>:8000/minio/login

**Note**: Use Access Key and Secret Key during login as specified while generating
minio-deployment.yaml file.

Content of `minio-deployment.yaml` for reference.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  # This name uniquely identifies the PVC. Will be used in deployment below.
  name: minio-pv-claim
  labels:
    app: minio-storage-claim
spec:
  # Read more about access modes here: https://kubernetes.io/docs/user-guide/persistent-volumes/#access-modes
  accessModes:
    - ReadWriteOnce
  resources:
    # This is the request for storage. Should be available in the cluster.
    requests:
      storage: 2G
  # Uncomment and add storageClass specific to your requirements below. Read more https://kubernetes.io/docs/concepts/storage/persistent-volumes/#class-1
  storageClassName: kadalu.replica1
---
apiVersion: extensions/v1beta1
kind: Deployment
metadata:
  # This name uniquely identifies the Deployment
  name: minio-deployment
spec:
  strategy:
    type: Recreate
  template:
    metadata:
      labels:
        # Label is used as selector in the service.
        app: minio
    spec:
      # Refer to the PVC created earlier
      volumes:
      - name: storage
        persistentVolumeClaim:
          # Name of the PVC created earlier
          claimName: minio-pv-claim
      containers:
      - name: minio
        # Pulls the default MinIO image from Docker Hub
        image: minio/minio
        args:
        - server
        - /storage
        env:
        # MinIO access key and secret key
        - name: MINIO_ACCESS_KEY
          value: "admin"
        - name: MINIO_SECRET_KEY
          value: "adminsecret"
        ports:
        - containerPort: 9000
        # Mount the volume into the pod
        volumeMounts:
        - name: storage # must match the volume name, above
          mountPath: "/storage"
---
apiVersion: v1
kind: Service
metadata:
  name: minio-service
spec:
  type: LoadBalancer
  ports:
    - port: 9000
      targetPort: 9000
      protocol: TCP
  selector:
    app: minio
```
