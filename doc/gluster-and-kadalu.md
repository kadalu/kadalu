# How gluster and kadalu are related ?

The fundamental idea of the project is described [here](doc/rethinking-gluster-management-using-k8s.pdf)

Compared to `GlusterD` there are various points which we consider worth changing:

- Too many layers, hard to debug
- Duplication of task is bad, and can cause in-consistency
- K8s can provide added infrastructure like process management, cluster authentication, monitoring and centralized logging
- Running more than one process in a container defeats the purpose of microservices
- Currently, no ideal solution with Gluster for storage in k8s

Therefore kadalu does some things different:

|GlusterD|kaDalu|
|--------|------|
|Clustering / Peer Management|k8s|
|Volume Management|ConfigMap, `kubectl apply`|
|Brick process management|K8s’s pod management|
|Portmap for Bricks|Not required in new model|
|Service Management (brick, self-heal, etc)|Runs as another container in same pod.<br>So, managed by k8s as any other pod|
|Volfile for Bricks, self-heal etc|ConfigMap|
|Quota, Snapshot, Geo-Replication|CSI / SideCar containers|


### Implementation

* There is no need to have a `glusterd` running on the host.
