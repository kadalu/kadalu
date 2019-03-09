FROM docker.io/fedora:29

COPY extras/release6-fedora.repo /etc/yum.repos.d/glusterfs-6-rc0.repo

RUN yum update -y && \
    yum -y install procps-ng glusterfs-fuse xfsprogs && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    rpm -qa | grep gluster | tee /gluster-rpm-versions.txt

# Install Python GRPC library and copy all CSI related files
RUN python3 -m pip install grpcio googleapis-common-protos
RUN mkdir -p /kadalu-csi

COPY csi/controllerserver.py   /kadalu-csi/
COPY csi/csi_pb2_grpc.py       /kadalu-csi/
COPY csi/csi_pb2.py            /kadalu-csi/
COPY csi/identityserver.py     /kadalu-csi/
COPY csi/main.py               /kadalu-csi/
COPY csi/nodeserver.py         /kadalu-csi/
COPY csi/utils.py              /kadalu-csi/

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu CSI driver"
LABEL name="kadalu-csi"
LABEL Summary="KaDalu CSI driver"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/aravindavk/kadalu"
LABEL vendor="kadalu.gluster"
LABEL version="${version}"

ENTRYPOINT ["/usr/bin/python3", "/kadalu-csi/main.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
