# Kadalu kubectl plugin

## Install

Download the latest release with the command

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

Test to ensure the version you installed is up-to-date

```
$ kubectl-kadalu version
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

## Contributing

1. Fork it (<https://github.com/kadalu/kadalu/fork>)
2. Create your feature branch (`git checkout -b my-new-feature`)
3. `cd cli`
4. Make the required changes and run `python3 kubectl_kadalu`
5. Commit your changes (`git commit -am 'Add some feature'`)
4. Push to the branch (`git push origin my-new-feature`)
5. Create a new Pull Request

