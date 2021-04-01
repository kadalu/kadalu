FROM kadalu/builder:latest as builder

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

RUN python3 -m pip install googleapis-common-protos

FROM ubuntu:20.04 as prod
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends attr python3 libtirpc3 bash ssh&& \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

# copy glusterfs installed in /opt
COPY --from=builder /opt /opt

# actual application to be copied here
# using already installed packages from builder for faster build time
COPY --from=builder /kadalu /kadalu

# copy grpcio installed in pypi_source image
COPY --from=kadalu/pypi_source:latest /usr/local/lib/python3.8/dist-packages /kadalu/lib/python3.8/site-packages/

RUN mkdir -p /kadalu/volfiles /kadalu/templates
RUN mkdir -p /var/log/glusterfs /var/run/gluster

COPY lib/kadalulib.py          /kadalu/
COPY csi/controllerserver.py   /kadalu/
COPY csi/csi_pb2_grpc.py       /kadalu/
COPY csi/csi_pb2.py            /kadalu/
COPY csi/identityserver.py     /kadalu/
COPY csi/main.py               /kadalu/
COPY csi/start.py              /kadalu/
COPY csi/exporter.py           /kadalu/
COPY csi/nodeserver.py         /kadalu/
COPY csi/volumeutils.py        /kadalu/
COPY lib/startup.sh            /kadalu/
COPY csi/quota-crawler.sh      /kadalu/
COPY csi/heal-info.sh          /kadalu/

COPY templates/Replica1.client.vol.j2 /kadalu/templates/
COPY templates/Replica2.client.vol.j2 /kadalu/templates/
COPY templates/Replica3.client.vol.j2 /kadalu/templates/
COPY templates/Disperse.client.vol.j2 /kadalu/templates/

RUN chmod +x /kadalu/startup.sh
RUN chmod +x /kadalu/heal-info.sh

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

ENTRYPOINT ["python3", "/kadalu/start.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
