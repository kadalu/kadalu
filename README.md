# kaDalu

[![Operator Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg?label=DockerPulls%20Operator)](https://img.shields.io/docker/pulls/kadalu/kadalu-operator.svg)
[![Server Docker Pulls](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg?label=DockerPulls%20Server)](https://img.shields.io/docker/pulls/kadalu/kadalu-server.svg)
![Devel](https://github.com/kadalu/kadalu/actions/workflows/on-pr-merge.yml/badge.svg)
![Release](https://github.com/kadalu/kadalu/actions/workflows/on-release-tag.yml/badge.svg)

## What is Kadalu ?

[Kadalu](https://kadalu.io) is a project to provide Persistent Storage in container ecosystem (like kubernetes, openshift, RKE, etc etc). Kadalu operator deploys CSI pods, and **gluster storage** pods as per the config. You would get your PVs served through APIs implemented in CSI.

## Get Started

Getting started is made easy to copy paste the below commands.

```console
curl -fsSL https://github.com/kadalu/kadalu/releases/latest/download/install.sh | sudo bash -x
kubectl-kadalu version
kubectl kadalu install --type=$K8S_DIST
```

Where `K8S_DIST` can be one of below values and `kubernetes` being the default:
- kubernetes
- openshift
- rke
- microk8s

The above will deploy the latest version of kadalu operator and CSI pods. Once done, you can provide storage to kadalu operator to manage.

```
$ kubectl kadalu storage-add storage-pool-1 --device kube1:/dev/sdc
```

Note that, in above command, `kube1` is the node which is providing `/dev/sdc` as a storage to kadalu. In your setup, this may be different.

If you made some errors in setup, and want to start fresh, check this [cleanup script](extras/scripts/cleanup), and run it to remove kadalu namespace completely.

```
curl -s https://raw.githubusercontent.com/kadalu/kadalu/devel/extras/scripts/cleanup | bash
```


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

For Kadalu Versions >= 0.8.5 helm chart is broken into subcharts, refer below for installation:
```
# Takes values as mentioned above
K8S_DIST=kubernetes
curl -sL https://github.com/kadalu/kadalu/releases/latest/download/kadalu-helm-chart.tgz -o /tmp/kadalu-helm-chart.tgz

# First install operator
helm install operator --namespace kadalu --create-namespace /tmp/kadalu-helm-chart.tgz --set operator.enabled=true --set global.kubernetesDistro=$K8S_DIST

# Incase of Kadalu upgrade verify pod eviction and no usage of Kadalu PVCs, for fresh installation just proceed after operator deployment
helm install csi-nodeplugin --namespace kadalu /tmp/kadalu-helm-chart.tgz --set csi-nodeplugin.enabled=true --set global.kubernetesDistro=$K8S_DIST
```

NOTE: We are still evolving with Helm chart based development, and happy to get contributions on the same.

## Platform supports

We support x86_64 (amd64) by default (all releases, `devel` and `latest` tags), and from release 0.8.3 tag arm64 and arm/v7 is supported.

For any other platforms, we need users to confirm it works by building images locally. Once it works, we can include it in our automated scripts. You can confirm the build by command `make release` after checkout of the repository in the respective platform.


## How to pronounce kadalu ?

One is free to pronounce 'kaDalu' as they wish. Below is a sample of how we pronounce it!

[<img src="https://raw.githubusercontent.com/kadalu/kadalu/devel/extras/assets/speaker.svg" width="64"/>](https://raw.githubusercontent.com/kadalu/kadalu/devel/extras/assets/kadalu_01.wav)


>
>**Request:** If you like the project, give a github star :-)
>

