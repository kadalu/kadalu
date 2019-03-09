FROM docker.io/fedora:29

COPY extras/release6-fedora.repo /etc/yum.repos.d/glusterfs-6-rc0.repo

RUN yum update -y && \
    yum -y install python3-pyxattr procps-ng glusterfs-server xfsprogs && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    rpm -qa | grep gluster | tee /gluster-rpm-versions.txt

COPY server/server.py /usr/bin/kadalu-server
COPY server/mount-glustervol /usr/bin/mount-glustervol

RUN chmod +x /usr/bin/kadalu-server
RUN chmod +x /usr/bin/mount-glustervol

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu container(glusterfsd or glustershd)"
LABEL name="kadalu-server"
LABEL Summary="KaDalu Server"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/aravindavk/kadalu"
LABEL vendor="kadalu.gluster"
LABEL version="${version}"

# TODO: Add fsd parameters
ENTRYPOINT ["/usr/bin/kadalu-server"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
