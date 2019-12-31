# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.4.0] - 2019-12-31
### Added
- Many improvements to tests give more confidence to use Kadalu.
- Analytics improvements to understand the deployment better.
- Enhancement to support Kadalu storage on top of existing PVC
- Support for using external Gluster Volumes with K8s using Kadalu
- Code improvements and a couple of fixes to Pylint errors
- Kadalu kubectl plugin(`pip3 install kubectl-kadalu`) is
  introduced. This plugin helps to define Kadalu storage without the
  hassle of YAML files.
- Fixed hang issue while terminating the server pods.
- Added sidecar container to capture logs from the mount processes
  in CSI pods.
- `kadalu-quotad` is now available as pypi package to use with
  external Gluster Volumes.
- Deploy attacher as a container in provisioner statefulset instead of
  deploying it as a pod

## [0.3.0] - 2019-11-26
### Added
- Improved documentation. (Thanks to @papanito)
- Enhanced to handle invalid Pod names when k8s node name is used as part of pod name.
- Added more test cases to cover Replica 3 Volume use cases.
- Fixed a crash during Gluster volume mount in CSI pods.
- Operator is enhanced to start self heal daemon when Replica 3 volume is created.

## [0.2.0] - 2019-10-25
### Added
- Improvements to Volfile templates by removing distribute graph in
  case of no distribute Volume.
- Added Security Context Constraints to support Openshift deployment.
- Improved Tracking to understand the workload better.
- New `make` command for release management.

## [0.1.0] - 2019-07-30
### Added
- Kadalu Operator to install and manage CSI and Server pods.
- CSI driver supports provisioning ReadWriteOnce and ReadWriteMany volumes.
- Added xfs Quota support.
- Fedora 30 and Gluster 6.3 based container images.
- CSI drivers enhanced to generate client Volfiles using ConfigMap info.
- Server processes enhanced to generate brick Volfiles using ConfigMap info.
- Sample app to use ReadWriteMany or ReadWriteOnce PVs.
- Kadalu Operator is enhanced to accept raw device and format as required.
- Added Asciinema based demo link.
- Logging and Analytics support added.
- End-to-end testing using Minikube and Travis-ci.

[Unreleased]: https://github.com/kadalu/kadalu/compare/0.4.0...HEAD
[0.1.0]: https://github.com/kadalu/kadalu/compare/e434f25...0.1.0
[0.2.0]: https://github.com/kadalu/kadalu/compare/0.1.0...0.2.0
[0.3.0]: https://github.com/kadalu/kadalu/compare/0.2.0...0.3.0
[0.4.0]: https://github.com/kadalu/kadalu/compare/0.3.0...0.4.0
