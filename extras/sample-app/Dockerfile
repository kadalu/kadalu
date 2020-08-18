FROM bash

COPY script.sh /kadalu/script.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu sample App container"
LABEL name="kadalu-sample-app"
LABEL Summary="KaDalu Sample App"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["bash", "/kadalu/script.sh"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["/usr/local/bin/bash"]
