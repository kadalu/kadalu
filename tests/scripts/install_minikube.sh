ARCH=`uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|'`
MINIKUBE_VERSION=${MINIKUBE_VERSION:-"v1.22.0"}

if type minikube >/dev/null 2>&1; then
    version=$(minikube version)
    read -ra version <<<"${version}"
    version=${version[2]}
    if [[ "${version}" != "${MINIKUBE_VERSION}" ]]; then
	echo "installed minikube version ${version} is not matching requested version ${MINIKUBE_VERSION}"
	exit 1
    fi
    echo "minikube already installed with ${version}"
    exit 0
fi

echo "Installing minikube. Version: ${MINIKUBE_VERSION}"
curl -Lo minikube https://storage.googleapis.com/minikube/releases/"${MINIKUBE_VERSION}"/minikube-linux-${ARCH} && chmod +x minikube && mv minikube /usr/local/bin/
