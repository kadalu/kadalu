# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

- Server: Use Kadalu Volgen library for volfile generation
- CSI: Fetch volfiles from brick processes in server using --volfile-server &
  remove storage options from mount flow.
- Server: Disbale default client volfile options
- CLI: Move healinfo to server pods, Trigger client-heal from csi pod.
- Server, CLI, Operator: Add feature for volume type Arbiter
- Operator, Server, CLI: Add feature of Storage Pool Options
- Fix NodeUnpublishVolume RPC idempotency
- Lib: Add INET6 to include IPV6 address family.
- cli: Add argument for namespace to support installation in other namespaces

## [0.9.0] - 2022-11-21

- Helm chart: fixed namespace management bug
- Mount FHS standardized kernel module directory
- Fix wrong calculations of `free_size_bytes`
- Bump kubernetes python package and use latest glusterfs build (with tcmalloc)
- Internally map `kadalu_format` to `single_pv_per_pool`
- Remove default tiebreaker node and add support for Replica2
- Implement logrotate to free-up used space from gluster logs
- Fix application of tolerations from Pool CR on glusterfs-server and
  nodeplugin pods
- Fix documentation related to using Kadalu metrics with OpenShift
  user-workload-monitoring feature

## [0.8.17] - 2022-10-17

- Update Python modules dependencies for all components
- Openshift documentation improvements

## [0.8.16] - 2022-09-01

- Use helm for generating devel manifests
- Harden RBAC permissions
- Support custom kubelet dir
- Container images can now be built directly from the repository without dependencies on previous build steps
- Enable and correctly handle tolerations supplied in KadaluStorage CR
- Multiple fixes around handling deletions and metrics (#879)

## [0.8.15] - 2022-06-16

- Enhance PV status command to check the Status from Provisioner pod instead of
  Server Pod to avoid errors when the Db file hashed to different distribute group
  other than first server Pod.
- Fix Monitoring/Prometheus labels for OCP setup.
- Fix the stale metrics from deleted Storage pools, PVs and other entities.
- Fix Quota crawler issues.
- Removed empty log lines from Quota crawler.
- Multiple CSI fixes around expanding Block vols, PVC deletion leftovers and fix broken Nomad deployments.

## [0.8.14] - 2022-04-16

- Added support for Private container registry
- Fixed Prometheus exporter issue while setting default values.

## [0.8.13] - 2022-03-29

- Container base images are upgraded as suggested by `docker scan` command.
- Krew repo index auto update issue fixed.
- Wrong binary path issue is fixed in the install helper script.
- Fixed the crash of Metrics API while accessing node_plugin metrics.

## [0.8.12] - 2022-03-21

- Krew repo index auto update issue fixed.

## [0.8.11] - 2022-03-21

- Krew repo index auto update issue fixed.
- Added support for removing Archived PVs.
- Fixed Prometheus metrics exporter path.
- Fixed metrics hang issue, when one or more Pods are offline/unreachable.

## [0.8.10] - 2022-02-03

- Krew repo auto update issue fixed.
- Install helper script added. Run single command to install the kubectl kadalu extension.
- Fixed External Volume mount issues.
- Updated the troubleshooting guide.
- Test infra improvements to reduce the test time.

## [0.8.9] - 2021-12-30

- Kadalu Kubectl extension is submitted to Krew! https://krew.sigs.k8s.io/plugins/
- Added documentation to use Kadalu with Krew
- Added support for Kubectl context via `--kubectl-context` option
- Added Upgrade documentation https://github.com/kadalu/kadalu/blob/devel/doc/upgrade.adoc
- Fixed metrics exporter issues
- Added alternative syntax for Storage add. Storage add syntax to help GlusterFS users.
- Fix Gluster mount options issues of external Volumes.
- Added framework to support Storage options(Gluster Volume options) via Storage classes.
- Fixed Mount reload notification on `kadalu-info` configMap update.
- Added a Validation to check existing Volume in `csi:ControllerExpandVolume`

## [0.8.8] - 2021-11-12

- Fixed issues with `kubectl kadalu healinfo` sub-command.
- Add additional information about the heal pending and other details to healinfo command.
- Fixed Kubernetes APIs comparison issue when minor version contains alpha numeric values.
- Fixed issue while handling memory and CPU metrics when not available in some setup(LXD/LXC).
- Updated documentation about External Volume cleanup before adding it to Kadalu.
- Added support for CSI Block volume.

## [0.8.7] - 2021-10-29

- Troubleshooting guide updated for GlusterFS directory quota(External).
- Documentation update to use Kadalu Storage(External) with Nomad.
- Documentation update with upgrade steps.
- Metrics APIs are redesigned. All the metrics related to Kadalu Pods are now accessible from Operator Pod.
- Fixed an issue related to reachable host check(External).
- Fixed an crash related to Connection error in Operator.
- Fixed excessive logging of SETFATTR errors.
- Added support for Kubernetes v1.22.
- Fixed EPERM issues in CSI Provisioner.
- Added support to print versions from all Pods of Kadalu namespace(`kubectl kadalu version`).
- Added support for Setting Gluster options while adding External Storage pool.
- Documentation update for `xfsprogs` requirements.

## [0.8.6] - 2021-09-09

- Mounted Block Volume support - Create a Storage Class with `pv_type: Block` and all the PVs from this Storage Class will be created as Block Volumes. Refer documentation for the examples.
- Fixed an issue related to setting Gluster Quota when external Volume is used.
- Fixed the Python packaging related issues with Arm build.

## [0.8.5] - 2021-08-23

- Added support for PV expansion provisioned from external Volumes.
- New Prometheus metrics added. `kadalu_storage_pv_capacity_bytes`, `kadalu_storage_pv_capacity_used_bytes` and `kadalu_storage_pv_capacity_free_bytes`
- Prometheus annotations added to automatically configure scraping.
- Fixed issue with Python dependencies in Arm builds.
- To avoid applications loosing access to the storage after upgrade, CSI node plugins are not upgraded as part of Operator and server pods upgrade.
- Fixed issues while setting external Quota when multiple hosts provided.

## [0.8.4] - 2021-07-27

- Fixed accounting issues related to Quota feature.
- Fixed issues while mounting the devices after creating fs
- Removed default storage classes created for each Volume types.
- Added one storage class for each Kadalu Storage.
- Operator: Added retry for Protocol error while watching the CRD.
- Fixed issue while deleting a Kadalu Storage when no Pvs present.

## [0.8.3] - 2021-06-21

- Improvements to the External GlusterFS Volumes support.
- Added support for Disperse Storage Type.
- Added support for archiving the PVCs on delete.
- kubectl-kadalu CLI enhanced to handle kadalu format.
- kubectl-kadalu CLI enhanced to handle PVCs archive.
- Fixed Armv7 kubectl binary issue.
- Added support for Volume ID in Storage config to
  enable reusing/migrating the Storage backend.
- Fixed issue with listing Storages and deleting external volumes
- Added support for decommisioning Storage units.
- Added support for Distributed Volumes for external.
  Volumes by enhancing quota integration over ssh.
- Enabled migration support from Replica1 to Replica2/3.

## [0.8.2] - 2021-05-02
### Added
- Enhanced provisioner to check free space before provisioning from External Storage.
- I/O tests added as part of CI.
- CSI Sanity tests added as part of CI.
- CSI "ValidateVolumeCapability" API is implemented.
- CSI "ListVolumes" API is implemented.
- Fixed an issue while creating a PV with same name but different size.
- Documentation format is changed to Asciidoc.

## [0.8.1] - 2021-03-12
### Added
- volfile: add 'read-fail-log' option to brick volfile.
- Fix issues related to container name changes in 0.8.0 release.
- Fix sqlite3 dependency issues in server container image.
- Mount all available volume before starting the CSI provisioner.
- Quotad is removed from the server image with the introduction of
  Simple Quota in 0.8.0 release.
- Enabled a few self-heal related options by default.

## [0.8.0] - 2021-03-02
### Added
- Introduced service monitor utility to manage multiple processes
  within the container.
- Prometheus exporter added to CSI driver.
- Documentation added for where to look for logs.
- New sub-command to `kubectl-kadalu` to fetch logs from
  all containers of Kadalu namespace.
- Use kadalu-storage (glusterfs fork of kadalu, which adds features like simple-quota etc).
- Changes in templates to accomodate distribute volumes
- Remove usage of -oprjquota on mount
- Use simple quota limit feature to set the quota
- Simplify the brick volfile generation, and make it uniform across
- Provide 'client-pid' to clients mounted in csi controller (for simple-quota)
- Fix the template files
- Include quota-crawler with provisioner
- Added support for self heal info into CLI - can be checked with `kubectl kadalu healinfo`
- Container images size optimizations.
- Fix the traceback when no hosting volumes are available.
- Helm charts are now part of tests and Release.
- cli: storage_list fix the issue due to container changes in server pod

## [0.7.7] - 2021-02-04
### Added
- Fixed an issue while doing `mkfs` while starting server pods.
- Fixed the crash when storage class name not specified with external Gluster volume.
- Fixed the device name parsing issues when device is specified using ID.
- GlusterFS version upgraded to `v8`.

## [0.7.6] - 2021-01-18
### Added
- Support added for Pods upgrade
- PV Resize support added.
- Kadalu Operator CRD version upgraded to `v1`
- Backup volfile servers option added for External
  Gluster volume configuration.
- Default log level is changed to `INFO`
- Arm64 and Armv7 support added to release scripts.

## [0.7.5] - 2020-12-23
### Added
- Fixed a few issues related automated build scripts.

## [0.7.4] - 2020-12-23
### Added
- Helm chart support added.
- [Breaking change](https://github.com/kadalu/kadalu/issues/380#issuecomment-749534332)
  related to mount dir introduced in k8s,
  Fixed by creating mount directory before doing bind mount.
- Fixed crash while running `storage-list` sub-command.
- Base image changed to Ubuntu(20.04)

## [0.7.3] - 2020-12-18
### Added
- Base image upgraded to Fedora 33
- Implemented Storage remove functionality via `kubectl-kadalu`
- Fix kubelet path related issues in RKE deployment.
- Fixed issue while marking failure when external Gluster
  volume is not reachable.

## [0.7.2] - 2020-11-23
### Added
- Updated `kubectl-kadalu` usage instructions.
- Removed Google analytics tracking.
- Added `--kubectl-cmd` argument to `kubectl-kadalu` to support
  variants like `k3s kubectl`.
- Fixed mount issues in GKE.
- Documentation updated to install kadalu Operator without
  using `kubectl-kadalu`(using yaml).
- Fixed xfs project id assignment overflow with Gluster's
  64bit inode numbers.
- Operator enhanced to check the external Gluster volume is reachable.
- Fixed an issue while handling JSON in Quotad.
- Replace Storage(Replace brick in GlusterFS) support added.
- Enhanced Quotad to fetch local brick paths of a Volume automatically.
- Included `kubectl-kadalu` in Operator container image. So that
  this command will be available via `kubectl exec`.
- Fixed a crash when hostvol_type is not specified while
  defining new Storage class.

## [0.7.1] - 2020-09-22
### Added
- Fixed issue while doing cleanup of backend directory after PV delete.
- Documentation updated for CentOS 7.x series.
- Intelligence added to download architecture specific `kubectl`
- PV Size accounting rewrite to fix false accounting.
- Microk8s support added.
- Fixed Storage Class override issue on Operator restart.
- Rancher (RKE) support added.
- Version sub-command added to `kubectl-kadalu`
- Single file deployment support added to `kubectl-kadalu`
- Storage add prompt, Script mode and Dry run options
  added to `kubectl-kadalu`
- `storage-list` sub-command added to `kubectl-kadalu`
- CSI proto files and sidecar containers updated to v1.2.0
- Improvements to Arm support and build scripts.
- Latest k8s integrated with CI.

## [0.7.0] - 2020-05-11
### Added
- New documentation added for Storage Classes
- Kadalu can be used as Local storage with the introduction of new
  Storage Class filter `node_affinity`.
- Experimental Arm support added with separate tag `master.`
- Python 2 support for Kadalu Kubectl extension
- Added support for Kubernetes 1.18
- Kadalu Server and CSI container images are upgraded to the latest
  stable release of Gluster(7.4).
- Fixed an issue of Server pods not starting due to long
  names. Removed hostname identifier from the Server pod names so that
  the Server pod name length will be well within limits. Use `kubectl
  get pods -n kadalu -o wide` to see the hostnames.

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

[Unreleased]: https://github.com/kadalu/kadalu/compare/0.9.0...HEAD
[0.1.0]: https://github.com/kadalu/kadalu/compare/e434f25...0.1.0
[0.2.0]: https://github.com/kadalu/kadalu/compare/0.1.0...0.2.0
[0.3.0]: https://github.com/kadalu/kadalu/compare/0.2.0...0.3.0
[0.4.0]: https://github.com/kadalu/kadalu/compare/0.3.0...0.4.0
[0.5.0]: https://github.com/kadalu/kadalu/compare/0.4.0...0.5.0
[0.6.0]: https://github.com/kadalu/kadalu/compare/0.5.0...0.6.0
[0.7.0]: https://github.com/kadalu/kadalu/compare/0.6.0...0.7.0
[0.7.1]: https://github.com/kadalu/kadalu/compare/0.7.0...0.7.1
[0.7.2]: https://github.com/kadalu/kadalu/compare/0.7.1...v0.7.2
[0.7.3]: https://github.com/kadalu/kadalu/compare/v0.7.2...0.7.3
[0.7.4]: https://github.com/kadalu/kadalu/compare/0.7.3...0.7.4
[0.7.5]: https://github.com/kadalu/kadalu/compare/0.7.4...0.7.5
[0.7.6]: https://github.com/kadalu/kadalu/compare/0.7.5...0.7.6
[0.7.7]: https://github.com/kadalu/kadalu/compare/0.7.6...0.7.7
[0.8.0]: https://github.com/kadalu/kadalu/compare/0.7.7...0.8.0
[0.8.1]: https://github.com/kadalu/kadalu/compare/0.8.0...0.8.1
[0.8.2]: https://github.com/kadalu/kadalu/compare/0.8.1...0.8.2
[0.8.3]: https://github.com/kadalu/kadalu/compare/0.8.2...0.8.3
[0.8.4]: https://github.com/kadalu/kadalu/compare/0.8.3...0.8.4
[0.8.5]: https://github.com/kadalu/kadalu/compare/0.8.4...0.8.5
[0.8.6]: https://github.com/kadalu/kadalu/compare/0.8.5...0.8.6
[0.8.7]: https://github.com/kadalu/kadalu/compare/0.8.6...0.8.7
[0.8.8]: https://github.com/kadalu/kadalu/compare/0.8.7...0.8.8
[0.8.9]: https://github.com/kadalu/kadalu/compare/0.8.8...0.8.9
[0.8.10]: https://github.com/kadalu/kadalu/compare/0.8.9...0.8.10
[0.8.11]: https://github.com/kadalu/kadalu/compare/0.8.10...0.8.11
[0.8.12]: https://github.com/kadalu/kadalu/compare/0.8.11...0.8.12
[0.8.13]: https://github.com/kadalu/kadalu/compare/0.8.12...0.8.13
[0.8.14]: https://github.com/kadalu/kadalu/compare/0.8.13...0.8.14
[0.8.15]: https://github.com/kadalu/kadalu/compare/0.8.14...0.8.15
[0.8.16]: https://github.com/kadalu/kadalu/compare/0.8.15...0.8.16
[0.8.17]: https://github.com/kadalu/kadalu/compare/0.8.16...0.8.17
[0.9.0]: https://github.com/kadalu/kadalu/compare/0.8.17...0.9.0
