FROM bash

COPY script.sh /kadalu/script.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu Logger App container"
LABEL name="kadalu-logger-app"
LABEL Summary="KaDalu Logger App"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="org.kadalu.gluster"
LABEL version="${version}"

ENTRYPOINT ["bash", "/kadalu/script.sh"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["/usr/local/bin/bash"]
