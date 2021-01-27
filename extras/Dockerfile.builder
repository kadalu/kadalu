FROM ubuntu:20.04

ARG branch="series_0"

ENV GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS 8
ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/kadalu
ENV PATH="$VIRTUAL_ENV/bin:/opt/sbin:/opt/bin:$PATH"

RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends python3 curl xfsprogs net-tools telnet wget e2fsprogs \
    python3-pip sqlite build-essential g++ python3-dev flex bison openssl libssl-dev libtirpc-dev liburcu-dev \
    libfuse-dev libuuid1 uuid-dev acl-dev libtool automake autoconf git pkg-config libxml2-dev python3-venv && \
    python3 -m pip install --upgrade pip && \
    python3 -m pip install --upgrade setuptools && \
    git clone --depth 1 https://github.com/kadalu/glusterfs --branch ${branch} --single-branch glusterfs && \
    (cd glusterfs && ./autogen.sh && ./configure --prefix=/opt --enable-gnfs && make install && cd ..) && \
    curl -L https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'`/kubectl -o /usr/bin/kubectl && \
    chmod +x /usr/bin/kubectl &&  python3 -m venv $VIRTUAL_ENV && \
    cd /kadalu && pip install glustercli grpcio kubernetes==11.0.0 \
    jinja2 requests datetime xxhash googleapis-common-protos pyxattr && \
    apt-get autoremove --purge -y gcc python3-dev build-essential python3-pip g++ curl libfuse-dev libxml2-dev automake git sqlite wget && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

# Debugging, Comment the above line and
# uncomment below line
ENTRYPOINT ["tail", "-f", "/dev/null"]
