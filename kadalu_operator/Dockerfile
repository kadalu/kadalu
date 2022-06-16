ARG builder_version="latest"

FROM kadalu/builder:${builder_version} as builder

ENV PATH="/kadalu/bin:/opt/bin:/opt/sbin:$PATH"

COPY operator-requirements.txt /tmp/

RUN python3 -m pip install -r /tmp/operator-requirements.txt --no-cache-dir && \
    grep -Po '^[\w\.-]*(?=)' /tmp/operator-requirements.txt | xargs -I pkg python3 -m pip show pkg | grep -P '^(Name|Version|Location)'

FROM python:3.10-slim-bullseye as prod

ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update -yq && \
    apt-get -y clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/kadalu/bin:$PATH"

# kubectl binary
COPY --from=builder /usr/bin/kubectl /usr/bin/kubectl

# actual application to be copied here
# using already installed packages from builder for faster build time
COPY --from=builder /kadalu /kadalu

# venv in 'buster' img links python3 executable to '/usr/bin/python3'
# but in 'python:slim' it's at '/usr/local/bin/python3'
RUN ln -sfn /usr/local/bin/python3 /kadalu/bin/python3

RUN mkdir -p /kadalu/manifests

COPY templates/services.yaml.j2             /kadalu/templates/services.yaml.j2
COPY templates/server.yaml.j2               /kadalu/templates/server.yaml.j2
COPY templates/csi.yaml.j2                  /kadalu/templates/csi.yaml.j2
COPY templates/csi-driver-object.yaml.j2    /kadalu/templates/csi-driver-object.yaml.j2
COPY templates/csi-driver-object-v1.yaml.j2    /kadalu/templates/csi-driver-object-v1.yaml.j2
COPY templates/configmap.yaml.j2               /kadalu/templates/configmap.yaml.j2
COPY templates/storageclass-kadalu.custom.yaml.j2    /kadalu/templates/storageclass-kadalu.custom.yaml.j2
COPY templates/external-storageclass.yaml.j2         /kadalu/templates/external-storageclass.yaml.j2
COPY lib/kadalulib.py                       /kadalu/kadalulib.py
COPY cli/kubectl_kadalu/utils.py            /kadalu/utils.py
COPY kadalu_operator/main.py                       /kadalu/
COPY kadalu_operator/start.py                      /kadalu/
COPY kadalu_operator/metrics.py                    /kadalu/
COPY kadalu_operator/exporter.py                   /kadalu/
COPY cli/build/kubectl-kadalu               /usr/bin/kubectl-kadalu
COPY lib/startup.sh                         /kadalu/startup.sh

RUN chmod +x /kadalu/startup.sh

ARG version="(unknown)"
# Container build time (date -u '+%Y-%m-%dT%H:%M:%S.%NZ')
ARG builddate="(unknown)"

LABEL build-date="${builddate}"
LABEL io.k8s.description="KaDalu Operator"
LABEL name="kadalu-operator"
LABEL Summary="KaDalu Operator"
LABEL vcs-type="git"
LABEL vcs-url="https://github.com/kadalu/kadalu"
LABEL vendor="kadalu"
LABEL version="${version}"

ENTRYPOINT ["python3", "/kadalu/start.py"]

# Debugging, Comment the above line and
# uncomment below line
# ENTRYPOINT ["tail", "-f", "/dev/null"]
