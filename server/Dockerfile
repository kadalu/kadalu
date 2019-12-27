FROM docker.io/fedora:30

RUN yum update -y && \
    yum -y install python3-pyxattr procps-ng glusterfs-server xfsprogs && \
    yum clean all -y && \
    rm -rf /var/cache/yum && \
    rpm -qa | grep gluster | tee /gluster-rpm-versions.txt

RUN python3 -m pip install jinja2 xxhash requests datetime

COPY lib/kadalulib.py        /kadalu/kadalulib.py
COPY server/server.py        /kadalu/server.py
COPY server/glusterfsd.py    /kadalu/glusterfsd.py
COPY server/quotad.py        /kadalu/quotad.py
COPY server/shd.py           /kadalu/shd.py
COPY server/mount-glustervol /usr/bin/mount-glustervol
COPY lib/startup.sh          /kadalu/startup.sh
COPY server/stop-server.sh   /kadalu/stop-server.sh

RUN mkdir -p /kadalu/templates /kadalu/volfiles

# Copy Volfile templates
COPY templates/Replica1.client.vol.j2 /kadalu/templates/
COPY templates/Replica3.client.vol.j2 /kadalu/templates/
COPY templates/Replica1.brick0.vol.j2 /kadalu/templates/
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
LABEL vendor="org.kadalu.gluster"
LABEL version="${version}"

ENTRYPOINT ["/kadalu/startup.sh", "/usr/bin/python3", "/kadalu/server.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
