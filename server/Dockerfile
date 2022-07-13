ARG builder_version="latest"

FROM kadalu/builder:${builder_version} as builder

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

COPY requirements/server-requirements.txt /tmp/

RUN python3 -m pip install -r /tmp/server-requirements.txt --no-cache-dir && \
    grep -Po '^[\w\.-]*(?=)' /tmp/server-requirements.txt | xargs -I pkg python3 -m pip show pkg | grep -P '^(Name|Version|Location)'

FROM python:3.10-slim-bullseye as prod

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"
COPY --from=builder /opt /opt

# actual application to be copied here
# using already installed packages from builder for faster build time
COPY --from=builder /kadalu /kadalu

# venv in 'buster' img links python3 executable to '/usr/bin/python3'
# but in 'python:slim' it's at '/usr/local/bin/python3'
RUN ln -sfn /usr/local/bin/python3 /kadalu/bin/python3

RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends attr xfsprogs libtirpc3 sqlite3 liburcu6 curl && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

RUN curl -fsSL https://github.com/kadalu/moana/releases/latest/download/kadalu-`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'` -o /tmp/kadalu
RUN curl -fsSL https://github.com/kadalu/moana/releases/latest/download/mount.kadalu -o /tmp/mount.kadalu

RUN install /tmp/kadalu /usr/sbin/kadalu
RUN install /tmp/mount.kadalu /sbin/mount.kadalu

RUN mkdir -p /kadalu/templates /kadalu/volfiles
RUN mkdir -p /var/run/gluster /var/log/glusterfs

COPY lib/kadalulib.py        /kadalu/kadalulib.py
COPY server/server.py        /kadalu/server.py
COPY server/storage_unit_utils.py    /kadalu/storage_unit_utils.py
COPY lib/startup.sh          /kadalu/startup.sh
COPY server/stop-server.sh   /kadalu/stop-server.sh
COPY server/exporter.py      /kadalu/exporter.py

RUN chmod +x /kadalu/startup.sh
RUN chmod +x /kadalu/stop-server.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu container (Storage Unit)"
LABEL name="kadalu-server"
LABEL Summary="KaDalu Server"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["python3", "/kadalu/server.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
