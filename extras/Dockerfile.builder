FROM python:3.10-bullseye

ARG branch="series_1"

ENV GRPC_PYTHON_BUILD_EXT_COMPILER_JOBS 8
ENV DEBIAN_FRONTEND=noninteractive
ENV VIRTUAL_ENV=/kadalu
ENV PATH="$VIRTUAL_ENV/bin:/opt/sbin:/opt/bin:$PATH"

RUN apt-get update -yq && \
    apt-get install -y --no-install-recommends curl xfsprogs net-tools telnet wget e2fsprogs zlib1g-dev liburcu6\
    sqlite3 build-essential g++ flex bison openssl libssl-dev libtirpc-dev liburcu-dev \
    libfuse-dev libuuid1 uuid-dev acl-dev libtool automake autoconf git pkg-config \
    libffi-dev && \
    git clone --depth 1 https://github.com/kadalu/glusterfs --branch ${branch} --single-branch glusterfs && \
    (cd glusterfs && ./autogen.sh && ./configure --prefix=/opt >/dev/null && make install >/dev/null && cd ..) && \
    curl -L https://storage.googleapis.com/kubernetes-release/release/`curl -s https://storage.googleapis.com/kubernetes-release/release/stable.txt`/bin/linux/`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|' | sed 's|armv7l|arm|'`/kubectl -o /usr/bin/kubectl && \
    chmod +x /usr/bin/kubectl

COPY builder-requirements.txt /tmp/
RUN python3 -m venv $VIRTUAL_ENV && cd $VIRTUAL_ENV && sleep 1 && which python3 && which pip && \
    $VIRTUAL_ENV/bin/pip install -r /tmp/builder-requirements.txt --no-cache-dir && \
    grep -Po '^[\w\.-]*(?=)' /tmp/builder-requirements.txt | xargs -I pkg python3 -m pip show pkg | grep -P '^(Name|Version|Location)'

RUN sed -i "s/include-system-site-packages = false/include-system-site-packages = true/g" /kadalu/pyvenv.cfg

# Debugging, Comment the above line and
# uncomment below line
ENTRYPOINT ["tail", "-f", "/dev/null"]
