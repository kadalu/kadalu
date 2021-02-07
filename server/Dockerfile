FROM ubuntu:20.04

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq && \
    apt install software-properties-common -y && \
    apt-add-repository -y ppa:gluster/glusterfs-8 && \
    apt-get update -yq && \
    apt-get install --no-install-recommends -y python3.8 xfsprogs \
    net-tools telnet wget e2fsprogs python3-pip sqlite gcc python3-dev \
    python3-pyxattr glusterfs-server libffi-dev libssl-dev \
    build-essential && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools && \
    python3 -m pip install jinja2 datetime xxhash prometheus-client && \
    (python3 -m pip install glustercli || true && echo "External storage Quota feature may not work") && \
    apt-get autoremove --purge -y gcc build-essential python3-pip python3-dev libffi-dev libssl-dev build-essential && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

RUN mkdir -p /kadalu/templates /kadalu/volfiles
RUN mkdir -p /var/run/gluster /var/log/glusterfs

COPY lib/kadalulib.py        /kadalu/kadalulib.py
COPY server/server.py        /kadalu/server.py
COPY server/glusterfsd.py    /kadalu/glusterfsd.py
COPY server/kadalu_quotad/quotad.py       /kadalu/quotad.py
COPY server/kadalu_quotad/glusterutils.py /kadalu/glusterutils.py
COPY server/shd.py           /kadalu/shd.py
COPY server/mount-glustervol /usr/bin/mount-glustervol
COPY lib/startup.sh          /kadalu/startup.sh
COPY server/stop-server.sh   /kadalu/stop-server.sh

# Copy Volfile templates
COPY templates/Replica1.client.vol.j2 /kadalu/templates/
COPY templates/Replica2.client.vol.j2 /kadalu/templates/
COPY templates/Replica3.client.vol.j2 /kadalu/templates/
COPY templates/Replica1.brick0.vol.j2 /kadalu/templates/
COPY templates/Replica2.brick0.vol.j2 /kadalu/templates/
COPY templates/Replica2.brick1.vol.j2 /kadalu/templates/
COPY templates/Replica2.shd.vol.j2    /kadalu/templates/
COPY templates/Replica3.brick0.vol.j2 /kadalu/templates/
COPY templates/Replica3.brick1.vol.j2 /kadalu/templates/
COPY templates/Replica3.brick2.vol.j2 /kadalu/templates/
COPY templates/Replica3.shd.vol.j2    /kadalu/templates/

RUN chmod +x /usr/bin/mount-glustervol
RUN chmod +x /kadalu/startup.sh
RUN chmod +x /kadalu/stop-server.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu container(glusterfsd or glustershd)"
LABEL name="kadalu-server"
LABEL Summary="KaDalu Server"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["/usr/bin/python3", "/kadalu/server.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
