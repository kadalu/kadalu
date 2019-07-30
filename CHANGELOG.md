# Changelog
All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/aravindavk/kadalu/compare/0.1.0...HEAD
[0.1.0]: https://github.com/aravindavk/kadalu/compare/e434f25...0.1.0
