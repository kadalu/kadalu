FROM golang:alpine3.13 as build

# Highest csi-sanity version that tests CSI Spec v1.2.0
ENV VERSION="v3.1.1"
ENV SANITYTGZ="$VERSION.tar.gz"
ENV CGO_ENABLED=0

RUN apk add --no-cache make && wget -q https://github.com/kubernetes-csi/csi-test/archive/$SANITYTGZ
RUN tar xvf $SANITYTGZ && cd csi-test-"${VERSION/v/}" && make -C cmd/csi-sanity/ && cp cmd/csi-sanity/csi-sanity /opt/

FROM busybox:stable as prod

# Version supplied at build time
ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="CSI Sanity container for testing KaDalu driver"
LABEL name="kadalu-csi-sanity"
LABEL Summary="KaDalu Driver CSI Sanity"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

COPY --from=build /opt/csi-sanity /usr/local/sbin/csi-sanity
CMD ["sh"]

