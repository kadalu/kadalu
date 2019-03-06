FROM docker.io/{{ base_image }}:{{ image_tag }}

ADD http://artifacts.ci.centos.org/gluster/nightly/master.repo  /etc/yum.repos.d/glusterfs-nightly.repo
RUN yum update -y && \
    yum -y install glusterfs-server && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    rpm -qa | grep gluster | tee /gluster-rpm-versions.txt

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="{{ builddate }}"
LABEL io.k8s.description="Gluster Self-heal container"
LABEL name="{{ name }}"
LABEL Summary="GlusterShd"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/gluster/glustercs"
LABEL vendor="gluster.org"
LABEL version="${version}"

# TODO: Add shd parameters
ENTRYPOINT ["/usr/sbin/glusterfs"]
