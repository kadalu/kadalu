# Base Dockerfile in https://github.com/Docker-Hub-frolvlad/docker-alpine-python3
FROM frolvlad/alpine-python3 AS compile
RUN apk add --no-cache gcc musl-dev git python3-dev && mkdir /opt/bin
RUN wget https://raw.githubusercontent.com/avati/arequal/master/arequal-checksum.c
RUN wget https://raw.githubusercontent.com/avati/arequal/master/arequal-run.sh -P /opt/bin/
RUN sed -i 's/bash/sh/' /opt/bin/arequal-run.sh
RUN gcc -o /opt/bin/arequal-checksum arequal-checksum.c && chmod +x /opt/bin/arequal*
RUN python3 -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"
RUN pip install git+https://github.com/vijaykumar-koppad/Crefi.git@7c17a353d19666f230100e92141b49c29546e870

FROM frolvlad/alpine-python3 AS prod

# Version supplied at build time
ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="IO container, runs Crefi and validates IO with arequal"
LABEL name="kadalu-test-io"
LABEL Summary="Kadalu IO container for CI"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

RUN apk add --no-cache rsync
COPY --from=compile /opt /opt

ENV PATH="/opt/venv/bin:/opt/bin:$PATH"
CMD ["sh"]
