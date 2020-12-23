FROM ubuntu:20.04

# Always have the latest stable kubectl

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install --no-install-recommends --yes python3 && \
    apt-get install -y xfsprogs net-tools telnet wget e2fsprogs python3-pip sqlite && \
    apt-get install -y gcc python3-dev && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools && \
    python3 -m pip install jinja2 requests datetime xxhash && \
    apt-get install -y curl && \
    curl -L https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'`/kubectl -o /usr/bin/kubectl && \
    chmod +x /usr/bin/kubectl && \
    python3 -m pip install kubernetes==11.0.0 && \
    apt-get autoremove --purge -y gcc python3-dev && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /kadalu/manifests

COPY templates/services.yaml.j2             /kadalu/templates/services.yaml.j2
COPY templates/server.yaml.j2               /kadalu/templates/server.yaml.j2
COPY templates/csi.yaml.j2                  /kadalu/templates/csi.yaml.j2
COPY templates/csi-driver-crd.yaml.j2       /kadalu/templates/csi-driver-crd.yaml.j2
COPY templates/csi-driver-object.yaml.j2    /kadalu/templates/csi-driver-object.yaml.j2
COPY templates/configmap.yaml.j2            /kadalu/templates/configmap.yaml.j2
COPY templates/storageclass-kadalu.yaml.j2  /kadalu/templates/storageclass-kadalu.yaml.j2
COPY templates/storageclass-kadalu.replica1.yaml.j2  /kadalu/templates/storageclass-kadalu.replica1.yaml.j2
COPY templates/storageclass-kadalu.replica2.yaml.j2  /kadalu/templates/storageclass-kadalu.replica2.yaml.j2
COPY templates/storageclass-kadalu.replica3.yaml.j2  /kadalu/templates/storageclass-kadalu.replica3.yaml.j2
COPY templates/external-storageclass.yaml.j2         /kadalu/templates/external-storageclass.yaml.j2
COPY lib/kadalulib.py                       /kadalu/kadalulib.py
COPY cli/kubectl_kadalu/utils.py            /kadalu/utils.py
COPY operator/main.py                       /kadalu/
COPY cli/build/kubectl-kadalu               /usr/bin/kubectl-kadalu
COPY lib/startup.sh                         /kadalu/startup.sh

RUN chmod +x /kadalu/startup.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu Operator"
LABEL name="kadalu-operator"
LABEL Summary="KaDalu Operator"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["/kadalu/startup.sh", "/usr/bin/python3", "/kadalu/main.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
