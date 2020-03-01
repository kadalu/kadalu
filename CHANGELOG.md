# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.6.0] - 2020-03-01
### Added
- Replica 2 support added using the Thin arbiter feature of GlusterFS
- Fixed issue showing the wrong status of server Pod as "Running"
  instead of the actual error.
- Fixed Gluster remount failure, when connectivity with storage pods
  goes down, and `df` command doesn't show the Gluster mount.
- CSI provisioner is enhanced to choose available storages randomly to
  avoid retrying with the same storage pool if that is down. This
  method also helps to utilize all the available storage pool for
  PVs.
- Fixed permissions issue when app pods try to use mounted PVs with a
  non-root user.
- Kadalu base container image upgraded to Fedora 31 and Gluster
  version in server and CSI container images to 7.3.
- Fixed issue in kubectl kadalu plugin while parsing arguments related
  to external storage and Tiebreaker node.

## [0.5.0] - 2020-01-30
### Added
- Documentation updated for the new features introduced in
  0.4.0(Kubectl plugin, External storage, and Storage configurations)
- Cleanup script enhanced to handle CSIDriver object, which was
  introduced in the latest version of Kubernetes.
- Troubleshooting documentation is added.
- Introduced Thread lock while updating the info file and while
  mounting the Storage pool to avoid race conditions when PV claim and
  pod create done in parallel.
- All Pylint tests are now passing.
- Upgraded Kadalu Server container images to Gluster latest
  release(7.x)
- Fixed Python compatibility issue in Kadalu Kubectl plugin.
- Introduced "install" subcommand in kubectl-kadalu
- Added support for external gluster storage in kubectl-kadalu

## [0.4.0] - 2019-12-31
### Added
- Enhancement to support Kadalu storage on top of existing PVC
- Support for using external Gluster Volumes with K8s using Kadalu
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
- Added tests to cover different Volume types(Replica1 and Replica3). Each PV claim size in tests made different so that it can be easily debugged.


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

[Unreleased]: https://github.com/kadalu/kadalu/compare/0.6.0...HEAD
[0.1.0]: https://github.com/kadalu/kadalu/compare/e434f25...0.1.0
[0.2.0]: https://github.com/kadalu/kadalu/compare/0.1.0...0.2.0
[0.3.0]: https://github.com/kadalu/kadalu/compare/0.2.0...0.3.0
[0.4.0]: https://github.com/kadalu/kadalu/compare/0.3.0...0.4.0
[0.5.0]: https://github.com/kadalu/kadalu/compare/0.4.0...0.5.0
[0.6.0]: https://github.com/kadalu/kadalu/compare/0.5.0...0.6.0
