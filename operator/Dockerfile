FROM docker.io/fedora:29

COPY extras/kubernetes.repo /etc/yum.repos.d/kubernetes.repo

RUN yum install -y kubectl

RUN yum update -y && \
    yum -y install procps-ng kubectl && \
    yum clean all -y && \
    rm -rf /var/cache/yum

# Install Python GRPC library and copy all CSI related files
RUN python3 -m pip install kubernetes jinja2
RUN mkdir -p /kadalu/manifests

COPY manifests/05-services.yaml.j2      /kadalu/manifests/services.yaml.j2
COPY manifests/02-server.yaml.j2        /kadalu/manifests/server.yaml.j2
COPY manifests/03-csi.yaml.j2           /kadalu/manifests/csi.yaml.j2
COPY manifests/01-configmap.yaml.j2     /kadalu/manifests/configmap.yaml.j2
COPY manifests/04-storageclass.yaml.j2  /kadalu/manifests/storageclass.yaml.j2

COPY operator/main.py          /kadalu/

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu Operator"
LABEL name="kadalu-operator"
LABEL Summary="KaDalu Operator"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/aravindavk/kadalu"
LABEL vendor="kadalu.gluster"
LABEL version="${version}"

ENTRYPOINT ["/usr/bin/python3", "/kadalu/main.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
