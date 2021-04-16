# Deploying a Web server

Create a Persistent Volume Claim (PVC).

```yaml
# File: webserver-pvc.yaml
---
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: webapp-pv
spec:
  storageClassName: kadalu.replica1
  accessModes:
    - ReadWriteMany
  resources:
    requests:
      storage: 500M
```

```console
$ kubectl apply -f webserver-pvc.yaml
persistentvolumeclaim/webapp-pv created
```

Verify the status of the PVC using,

```console
$ kubectl get pvc
NAME        STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS      AGE
webapp-pv   Bound    pvc-c0cbeb6f-5ad4-11e9-a5c7-525400b12ca0   477Mi      RWX            kadalu.replica1   7s
```

Now deploy a nginx pod by specifying the PVC name created above.

```yaml
# File: webserver-app.yaml
---
kind: Pod
apiVersion: v1
metadata:
  name: webapp
spec:
  containers:
    - name: web-nginx
      image: nginx:alpine
      ports:
        - containerPort: 80
          name: "http-server"
      volumeMounts:
        - mountPath: /usr/share/nginx/html
          name: webapp-storage
  volumes:
    - name: webapp-storage
      persistentVolumeClaim:
       claimName: webapp-pv
```

```console
$ kubectl apply -f webserver-app.yaml
pod/webapp created
```

Verify the status of the pod using,

```console
$ kubectl get pods
NAME        READY   STATUS    RESTARTS   AGE
webapp      1/1     Running   0          53s
```

Login into webapp pod and verify the mounted directory and create a
`index.html` file.

```console
$ kubectl exec -it webapp /bin/sh
$
$ df /usr/share/nginx/html/ -h
Filesystem                Size    Used  Available  Use%  Mounted on
/kadalu/vol...client.vol  476.8M  4.8M  472.1M     1%    /usr/share/nginx/html
$
$ echo "Hello World!" > /usr/share/nginx/html/index.html

$ exit
```

Get the IP of that pod by running,

```console
$ kubectl get pods -owide
NAME           READY   STATUS    RESTARTS   AGE     IP            NODE
webapp         1/1     Running   0          6m46s   172.17.0.10   minikube
```

Now run `curl` command to see the response from nginx server.

```console
$ curl http://172.17.0.10
Hello World!
```
