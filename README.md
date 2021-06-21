# kaDalu

[![TravisCI](https://travis-ci.com/kadalu/kadalu.svg?branch=devel)](https://travis-ci.com/kadalu/kadalu)
[![Operator Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg?label=DockerPulls%20Operator)](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg)
[![Server Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg?label=DockerPulls%20Server)](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg)
[![BuildX](https://github.com/kadalu/kadalu/workflows/buildx/badge.svg)](https://github.com/kadalu/kadalu/actions?query=workflow%3Abuildx)

## What is Kadalu ?

[Kadalu](https://kadalu.io) is a project which started as an idea to make glusterfs's deployment and management simpler in kubernetes. The project contains operator to deploy CSI pods, and gluster storage nodes. All of gluster management is done natively in kubernetes without glusterfs's `glusterd` and `gluster` CLI tools.

Try it in few minutes to understand more!

## Documentation

Start with our [Quick Start Guide](doc/quick-start.adoc). More documentation is at [`doc/` folder](doc/).

If you made some errors in setup, and want to start fresh, check this [cleanup script](extras/scripts/cleanup), and run it to remove kadalu namespace completely.

Links to blogs and news updates are provided in [our website](https://kadalu.io).

## Talks and Blog posts

1. [Blog] [Gluster’s management in k8s](https://medium.com/@tumballi/glusters-management-in-k8s-13020a561962)
2. [Blog] [Gluster and Kubernetes - Portmap](https://aravindavk.in/blog/gluster-and-k8s-portmap/)
3. [Talk] [DevConf India - Rethinking Gluster Management using k8s](https://devconfin19.sched.com/event/RVPw/rethinking-gluster-management-using-k8s) ([Check slides here](doc/rethinking-gluster-management-using-k8s.pdf))
4. [Demo] Asciinema recording - [Kadalu Setup](https://asciinema.org/a/259949)
5. [Demo] Asciinema recording - [KaDalu CSI to claim Persistent Volumes](https://asciinema.org/a/259951)
6. [Blog] [kaDalu - Ocean of opportunities](https://medium.com/@tumballi/kadalu-ocean-of-potential-in-k8s-storage-a07be1b8b961?source=friends_link&sk=d2499bc1e7433fd18c93c34c796e1a11&utm_source=github)

For more blog posts, see [kadalu.io/blog](https://kadalu.io/blog)


## Reach out

1. Best is opening an [issue in github.](https://github.com/kadalu/kadalu/issues)
2. Reach to us on [Slack](https://join.slack.com/t/kadalu/shared_invite/enQtNzg1ODQ0MDA5NTM2LWMzMTc5ZTJmMjk4MzI0YWVhOGFlZTJjZjY5MDNkZWI0Y2VjMDBlNzVkZmI1NWViN2U3MDNlNDJhNjE5OTBlOGU) (Note, there would be no history) - https://kadalu.slack.com


## Contributing

We would like your contributions to come as feedbacks, testing, development etc. See [CONTRIBUTING](CONTRIBUTING.md) for more details.

If you are interested in financial donation to the project, or to the developers, you can do so at our [opencollective](https://opencollective.com/kadalu) page. (We like github sponsors too, but its still in waiting list for an org in India).


## Helm support

`helm install kadalu --namespace kadalu --create-namespace https://github.com/kadalu/kadalu/releases/latest/download/kadalu-helm-chart.tgz --set-string kubernetesDistro=$K8S_DIST`

Where `K8S_DIST` can be one of below values:
- kubernetes
- openshift
- rke
- microk8s

If `--set-string` isn't supplied `kubernetes` will be used as default.

NOTE: We are still evolving with Helm chart based development, and happy to get contributions on the same.


## Platform supports

We support x86_64 (amd64) by default (all releases, `devel` and `latest` tags), and in release 0.7.7 tag arm64 and arm/v7 is supported. If you want to try arm64 or arm/v7 in latest form try below command to start the operator

`kubectl apply -f https://raw.githubusercontent.com/kadalu/kadalu/arm/manifests/kadalu-operator.yaml`

For any other platforms, we need users to confirm it works by building images locally. Once it works, we can include it in our automated scripts. You can confirm the build by command `make release` after checkout of the repository in the respective platform.


## How to pronounce kadalu ?

One is free to pronounce 'kaDalu' as they wish. Below is a sample of how we pronounce it!

[<img src="https://raw.githubusercontent.com/kadalu/kadalu/devel/extras/assets/speaker.svg" width="64"/>](https://raw.githubusercontent.com/kadalu/kadalu/devel/extras/assets/kadalu_01.wav)


## Stargazers over time

[![Stargazers over time](https://starchart.cc/kadalu/kadalu.svg)](https://starchart.cc/kadalu/kadalu)

>
>**Note 1:** If you like the project, give a github star :-)
>

