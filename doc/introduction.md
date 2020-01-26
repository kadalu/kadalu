# Introduction

Kadalu project started with a goal of keeping minimum layers to provide Persistent Volumes in k8s eco system. kadalu uses 'GlusterFS' as soul to provide storage, but strips off 'gluster' project's management layer.

The focus of the project is simplicity and stability. We believe simple things can solve things better, instead of complicating already complicated eco-system.

kaDalu project is a result of multiple years of observing the growth
of kubernetes ecosystem, and how storage evovled with kubernetes.

The developers of the project, who were also maintainers of GlusterFS
project, saw multiple attempts to get glusterfs's container story right.
The very early attempt was **heketi** project, which provided API interface
from k8s world to the CLI based gluster management world.

Gluster Project also tried to make glusterd2 (also called as GD2) project,
which was a management tool written in Golang, to replace existing management
process, `glusterd`. It didn't succeed in becoming reality as `glusterd` was
written for standalone system, and by adding all the feature it provided,
`glusterd2` project also became bulky, and didn't solve either of the
usecases (standalone, containers) properly.

When we revisited the gluster's management layer's responsibilities, and why
these were handled by glusterd, there were many things we could see parallels
with kubernetes ecosystem. We realized to serve persistent volumes in
kubernetes, using glusterfs, we don't need a management layer, but the
operator + CSI combination is good enough.

This project is the solution which came out of the discussions, where we
tried to simplify glusterfs deployments, and how users can see storage.
