FROM docker.io/{{ base_image }}:{{ image_tag }}

RUN yum install -y git
ADD http://artifacts.ci.centos.org/gluster/nightly/master.repo  /etc/yum.repos.d/glusterfs-nightly.repo
RUN yum update -y && \
    yum -y install glusterfs-fuse && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    rpm -qa | grep gluster | tee /gluster-rpm-versions.txt

# Install Python GRPC library
RUN python3 csi/setup.py install

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="{{ builddate }}"
LABEL io.k8s.description="GlusterCS CSI driver"
LABEL name="{{ name }}"
LABEL Summary="GlusterCS CSI driver"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/gluster/glustercs"
LABEL vendor="gluster.org"
LABEL version="${version}"

ENTRYPOINT ["/usr/bin/{{ name }}"]
