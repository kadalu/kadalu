FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
ENV GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS 8

RUN apt-get update -yq && \
    apt-get install --no-install-recommends -y python3.8 xfsprogs \
    net-tools telnet wget e2fsprogs python3-pip sqlite python3-dev \
    glusterfs-client build-essential gcc g++ && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools && \
    python3 -m pip install jinja2 requests datetime xxhash \
    grpcio googleapis-common-protos && \
    apt-get autoremove --purge -y gcc g++ build-essential python3-dev python3-pip && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /kadalu/volfiles /kadalu/templates
RUN mkdir -p /var/log/glusterfs /var/run/gluster

COPY lib/kadalulib.py          /kadalu/
COPY csi/controllerserver.py   /kadalu/
COPY csi/csi_pb2_grpc.py       /kadalu/
COPY csi/csi_pb2.py            /kadalu/
COPY csi/identityserver.py     /kadalu/
COPY csi/main.py               /kadalu/
COPY csi/nodeserver.py         /kadalu/
COPY csi/volumeutils.py        /kadalu/
COPY lib/startup.sh            /kadalu/

COPY templates/Replica1.client.vol.j2 /kadalu/templates/
COPY templates/Replica2.client.vol.j2 /kadalu/templates/
COPY templates/Replica3.client.vol.j2 /kadalu/templates/

RUN chmod +x /kadalu/startup.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu CSI driver"
LABEL name="kadalu-csi"
LABEL Summary="KaDalu CSI driver"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["/kadalu/startup.sh", "/usr/bin/python3", "/kadalu/main.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
