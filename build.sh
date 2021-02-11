#! /bin/bash

set -e -o pipefail

DOCKER_USER="${DOCKER_USER:-kadalu}"
KADALU_VERSION="${KADALU_VERSION}"

RUNTIME_CMD=${RUNTIME_CMD:-docker}
build="build"
if [[ "${RUNTIME_CMD}" == "buildah" ]]; then
        build="bud"
fi

# This sets the version variable to (hopefully) a semver compatible string. We
# expect released versions to have a tag of vX.Y.Z (with Y & Z optional), so we
# only look for those tags. For version info on non-release commits, we want to
# include the git commit info as a "build" suffix ("+stuff" at the end). There
# is also special casing here for when no tags match.
VERSION_GLOB="v[0-9]*"
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
                 . || exit 1
}

if [ "x${KADALU_VERSION}" = "x" ]; then
    KADALU_VERSION=${VERSION}
fi

echo "Building images kadalu-\$service:${VERSION}";

build_container "kadalu-server" "server/Dockerfile.frombuilder" ${KADALU_VERSION}
build_container "kadalu-csi" "csi/Dockerfile.frombuilder" ${KADALU_VERSION}
build_container "kadalu-operator" "operator/Dockerfile.frombuilder" ${KADALU_VERSION}
