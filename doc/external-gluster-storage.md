# Use external gluster volume as PV in kadalu

If you are having your storage nodes outside of kubernetes cluster, you
can still use kadalu.

All you need is to have a sample like [`examples/sample-external-storage.yaml`](../examples/sample-external-storage.yaml).

Please edit 'gluster_host' and 'gluster_volname' parameters in Storage Class.


Then run `kubectl create -f ./examples/sample-external-storage.yaml`

