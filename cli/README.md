# Kadalu kubectl plugin

Clone this repository and install,

```
$ cd kadalu/cli
$ sudo python3 setup.py install
```

## Usage:

### Add Storage

Add storage by specifying raw devices,

```
$ kubectl kadalu storage-add storage-pool-1 \
    --device kube1.example.com:/dev/vdc
```

In case of Replica 3 volume,

```
$ kubectl kadalu storage-add storage-pool-2 \
    --type Replica3
    --device kube1.example.com:/dev/vdc
    --device kube2.example.com:/dev/vdc
    --device kube3.example.com:/dev/vdc
```

To specify storage directory instead of device,

```
$ kubectl kadalu storage-add storage-pool-1 \
    --path kube1.example.com:/export/data1
```

To use available `pvc` as Kadalu storage,

```
$ kubectl kadalu storage-add storage-pool-3 \
    --pvc azure-disk-1
```
