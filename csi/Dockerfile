ARG builder_version="latest"

FROM kadalu/builder:${builder_version} as builder

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

COPY csi-requirements.txt /tmp/

RUN python3 -m pip install -r /tmp/csi-requirements.txt --no-cache-dir && \
    grep -Po '^[\w\.-]*(?=)' /tmp/csi-requirements.txt | xargs -I pkg python3 -m pip show pkg | grep -P '^(Name|Version|Location)'

FROM python:3.10-slim-bullseye as prod
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends sqlite3 xfsprogs attr libtirpc3 bash inotify-tools ssh liburcu6 && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

# copy glusterfs installed in /opt
COPY --from=builder /opt /opt

# actual application to be copied here
# using already installed packages from builder for faster build time
COPY --from=builder /kadalu /kadalu

# venv in 'buster' img links python3 executable to '/usr/bin/python3'
# but in 'python:slim' it's at '/usr/local/bin/python3'
RUN ln -sfn /usr/local/bin/python3 /kadalu/bin/python3

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
COPY csi/watch-vol-changes.sh  /kadalu/
COPY csi/heal-info.sh          /kadalu/
COPY csi/remove_archived_pv.py /kadalu/

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
