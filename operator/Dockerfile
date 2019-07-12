FROM docker.io/fedora:30

COPY extras/kubernetes.repo /etc/yum.repos.d/kubernetes.repo

RUN yum install -y kubectl

RUN yum update -y && \
    yum -y install procps-ng kubectl && \
    yum clean all -y && \
    rm -rf /var/cache/yum

# Install Python GRPC library and copy all CSI related files
RUN python3 -m pip install kubernetes jinja2 xxhash
RUN mkdir -p /kadalu/manifests

COPY templates/services.yaml.j2      /kadalu/templates/services.yaml.j2
COPY templates/server.yaml.j2        /kadalu/templates/server.yaml.j2
COPY templates/csi.yaml.j2           /kadalu/templates/csi.yaml.j2
COPY templates/configmap.yaml.j2     /kadalu/templates/configmap.yaml.j2
COPY templates/storageclass.yaml.j2  /kadalu/templates/storageclass.yaml.j2
COPY lib/kadalulib.py                /kadalu/kadalulib.py
COPY operator/main.py                /kadalu/

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
