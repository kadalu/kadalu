#! /bin/bash

set -e -o pipefail

DOCKER_USER="${DOCKER_USER:-kadalu}"
KADALU_VERSION="${KADALU_VERSION}"

RUNTIME_CMD=${RUNTIME_CMD:-docker}
# Use buildx for docker to simulate release script in github workflow
# Requires Docker >=v19.03
PLATFORM=$(uname -m | sed 's|aarch64|arm64|' | sed 's|x86_64|amd64|' | sed 's|armv7l|arm/v7|')
build="buildx build --no-cache --platform linux/$PLATFORM --load"
if [[ "${RUNTIME_CMD}" == "buildah" ]]; then
        build="bud"
fi

# This sets the version variable to (hopefully) a semver compatible string. We
# expect released versions to have a tag of vX.Y.Z (with Y & Z optional), so we
# only look for those tags. For version info on non-release commits, we want to
# include the git commit info as a "build" suffix ("+stuff" at the end). There
# is also special casing here for when no tags match.
VERSION_GLOB="[0-9]*"
# Get the nearest "version" tag if one exists. If not, this returns the full
# git hash
NEAREST_TAG="$(git describe --always --tags --match "$VERSION_GLOB" --abbrev=0)"
# Full output of git describe for us to parse: TAG-<N>-g<hash>-<dirty>
FULL_DESCRIBE="$(git describe --always --tags --match "$VERSION_GLOB" --dirty)"
# If full matches against nearest, we found a valid tag earlier
if [[ $FULL_DESCRIBE =~ ${NEAREST_TAG}-(.*) ]]; then
        # Build suffix is the last part of describe w/ "-" replaced by "."
        VERSION="$NEAREST_TAG+${BASH_REMATCH[1]//-/.}"
else
        # We didn't find a valid tag, so assume version 0 and everything ends up
        # in build suffix.
        VERSION="0.0.0+g${FULL_DESCRIBE//-/.}"
fi

BUILDDATE="$(date -u '+%Y-%m-%dT%H:%M:%S.%NZ')"

build_args=()
build_args+=(--build-arg "version=$VERSION")
build_args+=(--build-arg "builddate=$BUILDDATE")

# Print Docker version
echo "=== $RUNTIME_CMD version ==="
$RUNTIME_CMD version

function build_container()
{
    IMAGE_NAME=$1
    DOCKERFILE=$2
    VER=$3
    $RUNTIME_CMD $build \
                 -t "${DOCKER_USER}/${IMAGE_NAME}:${VER}" \
                 "${build_args[@]}" \
                 --network host \
                 -f "$DOCKERFILE" \
                 --target prod \
                 . || exit 1
}

if [ "x${KADALU_VERSION}" = "x" ]; then
    KADALU_VERSION=${VERSION}
fi

CONTAINERS_FOR=${CONTAINERS_FOR:-"DEVELOPMENT"}

if [[ "$CONTAINERS_FOR" == "TESTING" ]]; then
  echo "Building test containers"

  # Test IO container to be used in CI
  build_container "test-io" "tests/test-io/Dockerfile" ${KADALU_VERSION}

  # Test CSI Sanity container to be used in CI
  build_container "test-csi" "tests/test-csi/Dockerfile" ${KADALU_VERSION}

  exit 0
fi

echo "Building base builder image - This may take a while"

$RUNTIME_CMD $build \
	     -t "${DOCKER_USER}/builder:latest" "${build_args[@]}" \
	     --network host -f extras/Dockerfile.builder .

echo "Building kadalu-server with version tag as ${VERSION}";
build_container "kadalu-server" "server/Dockerfile" ${KADALU_VERSION}

echo "Building kadalu-csi with version tag as ${VERSION}";
build_container "kadalu-csi" "csi/Dockerfile" ${KADALU_VERSION}

echo "Building kadalu-operator with version tag as ${VERSION}";
build_container "kadalu-operator" "kadalu_operator/Dockerfile" ${KADALU_VERSION}
