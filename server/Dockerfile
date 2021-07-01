ARG builder_version="latest"

FROM kadalu/builder:${builder_version} as builder

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

COPY server-requirements.txt /tmp/

RUN python3 -m pip install -r /tmp/server-requirements.txt

FROM ubuntu:20.04 as prod

ENV DEBIAN_FRONTEND=noninteractive
ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"
COPY --from=builder /opt /opt

# actual application to be copied here
# using already installed packages from builder for faster build time
COPY --from=builder /kadalu /kadalu

RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends python3 xfsprogs libtirpc3 sqlite3 && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

# copy pyxattr installed in pypi_source image
COPY --from=builder /usr/local/lib/python3.8/dist-packages /kadalu/lib/python3.8/site-packages/

RUN mkdir -p /kadalu/templates /kadalu/volfiles
RUN mkdir -p /var/run/gluster /var/log/glusterfs

COPY lib/kadalulib.py        /kadalu/kadalulib.py
COPY server/server.py        /kadalu/server.py
COPY server/glusterfsd.py    /kadalu/glusterfsd.py
COPY server/shd.py           /kadalu/shd.py
COPY server/mount-glustervol /usr/bin/mount-glustervol
COPY lib/startup.sh          /kadalu/startup.sh
COPY server/stop-server.sh   /kadalu/stop-server.sh

# Copy Volfile templates
COPY templates/Replica1.client.vol.j2 /kadalu/templates/
COPY templates/Replica2.client.vol.j2 /kadalu/templates/
COPY templates/Replica3.client.vol.j2 /kadalu/templates/
COPY templates/Disperse.client.vol.j2 /kadalu/templates/
COPY templates/Replica2.shd.vol.j2    /kadalu/templates/
COPY templates/Replica3.shd.vol.j2    /kadalu/templates/
COPY templates/Disperse.shd.vol.j2    /kadalu/templates/
COPY templates/brick.vol.j2           /kadalu/templates/

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

ENTRYPOINT ["python3", "/kadalu/server.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
