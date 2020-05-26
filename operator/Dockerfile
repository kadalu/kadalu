FROM kadalu/kadalu-base

# Always have the latest stable kubectl
RUN curl -L https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'`/kubectl -o /usr/bin/kubectl

RUN chmod +x /usr/bin/kubectl

# Install Python GRPC library and copy all CSI related files
RUN python3 -m pip install kubernetes
RUN mkdir -p /kadalu/manifests

COPY templates/services.yaml.j2      /kadalu/templates/services.yaml.j2
COPY templates/server.yaml.j2        /kadalu/templates/server.yaml.j2
COPY templates/csi.yaml.j2           /kadalu/templates/csi.yaml.j2
COPY templates/csi-driver-crd.yaml.j2  /kadalu/templates/csi-driver-crd.yaml.j2
COPY templates/csi-driver-object.yaml.j2  /kadalu/templates/csi-driver-object.yaml.j2
COPY templates/configmap.yaml.j2     /kadalu/templates/configmap.yaml.j2
COPY templates/storageclass-kadalu.yaml.j2  /kadalu/templates/storageclass-kadalu.yaml.j2
COPY templates/storageclass-kadalu.replica1.yaml.j2  /kadalu/templates/storageclass-kadalu.replica1.yaml.j2
COPY templates/storageclass-kadalu.replica2.yaml.j2  /kadalu/templates/storageclass-kadalu.replica2.yaml.j2
COPY templates/storageclass-kadalu.replica3.yaml.j2  /kadalu/templates/storageclass-kadalu.replica3.yaml.j2
COPY templates/external-storageclass.yaml.j2  /kadalu/templates/external-storageclass.yaml.j2
COPY lib/kadalulib.py                /kadalu/kadalulib.py
COPY operator/main.py                /kadalu/
COPY lib/startup.sh                  /kadalu/startup.sh

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
