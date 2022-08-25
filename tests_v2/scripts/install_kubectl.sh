#!/bin/bash
ARCH=$1
KUBE_VERSION=$2

if type kubectl >/dev/null 2>&1; then
    version=$(kubectl version --client | grep "${KUBE_VERSION}")
    if [[ "x${version}" != "x" ]]; then
        echo "kubectl already installed with ${KUBE_VERSION}"
        exit 0
    fi
    echo "installed kubectl version ${version} is not matching requested version ${KUBE_VERSION}"
    # exit 1
fi
# Download kubectl, which is a requirement for using minikube.
echo "Installing kubectl. Version: ${KUBE_VERSION}"
echo "URL: https://storage.googleapis.com/kubernetes-release/release/"${KUBE_VERSION}"/bin/linux/${ARCH}/kubectl"
curl -Lo kubectl https://storage.googleapis.com/kubernetes-release/release/"${KUBE_VERSION}"/bin/linux/${ARCH}/kubectl && chmod +x kubectl && mv kubectl /usr/local/bin/
