# KaDalu

[![TravisCI](https://travis-ci.com/kadalu/kadalu.svg?branch=master)](https://travis-ci.com/kadalu/kadalu)
[![Operator Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg?label=DockerPulls%20Operator)](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg)
[![Server Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg?label=DockerPulls%20Server)](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg)
[![BuildX](https://github.com/kadalu/kadalu/workflows/buildx/badge.svg)](https://github.com/kadalu/kadalu/actions?query=workflow%3Abuildx)


### Stargazers over time

[![Stargazers over time](https://starchart.cc/kadalu/kadalu.svg)](https://starchart.cc/kadalu/kadalu)

>
>**Note 1:** If you like the project, give a github star :-)
>

# Kadalu Documentation

See [Documentation](doc/)

## How to pronounce kadalu ?

One is free to pronounce 'kaDalu' as they wish. Below is a sample of how we pronounce it!

[<img src="https://raw.githubusercontent.com/kadalu/kadalu/master/extras/assets/speaker.svg" width="64"/>](https://raw.githubusercontent.com/kadalu/kadalu/master/extras/assets/kadalu_01.wav)


## Talks and Blog posts

1. [Blog] [Gluster’s management in k8s](https://medium.com/@tumballi/glusters-management-in-k8s-13020a561962)
2. [Blog] [Gluster and Kubernetes - Portmap](https://aravindavk.in/blog/gluster-and-k8s-portmap/)
3. [Talk] [DevConf India - Rethinking Gluster Management using k8s](https://devconfin19.sched.com/event/RVPw/rethinking-gluster-management-using-k8s) ([slides](doc/rethinking-gluster-management-using-k8s.pdf))
4. [Demo] Asciinema recording - [Kadalu Setup](https://asciinema.org/a/259949)
5. [Demo] Asciinema recording - [KaDalu CSI to claim Persistent Volumes](https://asciinema.org/a/259951)
6. [Blog] [kaDalu - Ocean of opportunities](https://medium.com/@tumballi/kadalu-ocean-of-potential-in-k8s-storage-a07be1b8b961?source=friends_link&sk=d2499bc1e7433fd18c93c34c796e1a11&utm_source=github)

For more blog posts, see [kadalu.io/blog](https://kadalu.io/blog)

## Reach out to some of the developers

You can reach to the developers using certain ways.

1. Best is opening an [issue in github.](https://github.com/kadalu/kadalu/issues)
2. Reach to us on [Slack](https://join.slack.com/t/kadalu/shared_invite/enQtNzg1ODQ0MDA5NTM2LWMzMTc5ZTJmMjk4MzI0YWVhOGFlZTJjZjY5MDNkZWI0Y2VjMDBlNzVkZmI1NWViN2U3MDNlNDJhNjE5OTBlOGU) (Note, there would be no history) - https://kadalu.slack.com

## CONTRIBUTING

See [CONTRIBUTING](CONTRIBUTING.md)

## ARM support

The release versions and 'latest' versions are not yet ARM ready! But we have an image for `linux/arm64`,`linux/arm/v7` platform support!

Start the operator with `kubectl create -f https://raw.githubusercontent.com/kadalu/kadalu/master/manifests/kadalu-operator-master.yaml` to get started! Once we have few users confirming it works, will tag it in a release!


## NOTE

We are tracking the number of downloads based on 'docker pull' stats, and also
through google analytics. [This Commit](https://github.com/kadalu/kadalu/commit/cbc83fd751bf0221e22b61bd6ebad4af40e38275) gives detail of what is added to code w.r.to tracking.
