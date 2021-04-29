.PHONY: help build-grpc build-containers gen-manifest pylint prepare-release release

DOCKER_USER?=kadalu
KADALU_VERSION?=devel
KADALU_LATEST?=latest

help:
	@echo "    make build-grpc        - To generate grpc Python Code"
	@echo "    make build-containers  - To create server, csi and Operator containers"
	@echo "    make test-containers   - To create test-io, test-csi image used in CI"
	@echo "    make gen-manifest      - To generate manifest files to deploy"
	@echo "    make pylint            - To validate all Python code with Pylint"
	@echo "    make prepare-release   - Generate Manifest file and build containers for specific version and latest"
	@echo "    make release           - Publish the built container images"
	@echo "    make prepare-release-manifests - Prepare release manifest files"
	@echo "    make cli-build         - Build CLI binary"
	@echo "    make helm-chart        - Create a tgz archive of Helm chart"

build-grpc:
	python3 -m grpc_tools.protoc -I./csi/protos --python_out=csi --grpc_python_out=csi ./csi/protos/csi.proto

build-containers: cli-build
	DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} bash build.sh

# test-containers will be called on setting an environment variable 'CONTAINERS_FOR' as part of CI
test-containers:
	DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} bash build.sh

gen-manifest:
	@echo "Generating manifest files, run the following commands"
	@echo
	@mkdir -p manifests
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator.yaml
	@echo "kubectl apply -f manifests/kadalu-operator.yaml"
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		K8S_DIST=openshift                                   \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator-openshift.yaml
	@echo
	@echo "In the case of OpenShift, deploy Kadalu Operator by running "
	@echo "the following command"
	@echo
	@echo "Note: Security Context Constraints can be applied only by admins, "
	@echo 'Run `oc login -u system:admin` to login as admin'
	@echo
	@echo "oc create -f manifests/kadalu-operator-openshift.yaml"

	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		K8S_DIST=microk8s                                    \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator-microk8s.yaml
	@echo
	@echo "In the case of MicroK8s, deploy Kadalu Operator by running "
	@echo "the following command"
	@echo
	@echo "kubectl apply -f manifests/kadalu-operator-microk8s.yaml"

	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		K8S_DIST=rke                                    \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator-rke.yaml
	@echo
	@echo "In the case of Rancher (RKE), deploy Kadalu Operator by running "
	@echo "the following command"
	@echo
	@echo "kubectl apply -f manifests/kadalu-operator-rke.yaml"

pylint:
	@cp lib/kadalulib.py csi/
	@cp lib/kadalulib.py server/
	@cp lib/kadalulib.py operator/
	@cp cli/kubectl_kadalu/utils.py operator/
	@cp server/kadalu_quotad/quotad.py server/kadalu_quotad/glusterutils.py server/
	@pylint --disable=W0511 -s n lib/kadalulib.py
	@pylint --disable=W0511 -s n server/glusterfsd.py
	@pylint --disable W0511,W0603 -s n server/quotad.py
	@pylint --disable=W0511 -s n server/server.py
	@pylint --disable=W0511 -s n server/shd.py
	@pylint -s n server/glusterutils.py
	@pylint --disable=W0511,R0911,W0603 -s n csi/controllerserver.py
	@pylint --disable=W0511 -s n csi/identityserver.py
	@pylint --disable=W0511 -s n csi/main.py
	@pylint --disable=W0511 -s n csi/nodeserver.py
	@pylint --disable=W0511,C0302 -s n csi/volumeutils.py
	@pylint --disable=W0511 -s n operator/main.py
	@pylint --disable=W0511 -s n extras/scripts/gen_manifest.py
	@rm csi/kadalulib.py
	@rm server/kadalulib.py
	@rm operator/kadalulib.py
	@rm operator/utils.py
	@rm server/quotad.py
	@rm server/glusterutils.py
	@cd cli && make gen-version pylint pytest --keep-going

ifeq ($(KADALU_VERSION), latest)
prepare-release-manifests:
	@echo "KADALU_VERSION can't be latest for release"
else
prepare-release-manifests:
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		$(MAKE) gen-manifest
	@echo "Generated manifest file. Version: ${KADALU_VERSION}"
endif

ifeq ($(KADALU_VERSION), latest)
prepare-release: prepare-release-manifests
	@echo "KADALU_VERSION can't be latest for release"
else
prepare-release: prepare-release-manifests
	@echo "Building containers(Version: ${KADALU_VERSION}).."
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		$(MAKE) build-containers
endif

cli-build:
	cd cli && VERSION=${KADALU_VERSION} $(MAKE) release

pypi-build:
	@cp lib/kadalulib.py server/kadalu_quotad/
	echo ${KADALU_VERSION} > server/VERSION
	cd server; rm -rf dist; python3 setup.py sdist;

helm-chart:
	@echo "Creating tgz archive of helm chart(Version: ${KADALU_VERSION}).."
	cd helm; sed -i -e "s/0.0.0-0/${KADALU_VERSION}/" kadalu/Chart.yaml; tar -czf kadalu-helm-chart.tgz kadalu

ifeq ($(TWINE_PASSWORD),)
pypi-upload: pypi-build
	cd server; twine upload --username kadalu dist/*
else
pypi-upload: pypi-build
	cd server; twine upload --username kadalu -p ${TWINE_PASSWORD} dist/*

endif

ifeq ($(KADALU_VERSION), latest)
release: prepare-release
else
release: prepare-release pypi-upload cli-build helm-chart
	docker tag ${DOCKER_USER}/kadalu-operator:${KADALU_VERSION} ${DOCKER_USER}/kadalu-operator:${KADALU_LATEST}
	docker tag ${DOCKER_USER}/kadalu-csi:${KADALU_VERSION} ${DOCKER_USER}/kadalu-csi:${KADALU_LATEST}
	docker tag ${DOCKER_USER}/kadalu-server:${KADALU_VERSION} ${DOCKER_USER}/kadalu-server:${KADALU_LATEST}
	docker push ${DOCKER_USER}/kadalu-operator:${KADALU_VERSION}
	docker push ${DOCKER_USER}/kadalu-csi:${KADALU_VERSION}
	docker push ${DOCKER_USER}/kadalu-server:${KADALU_VERSION}
	docker push ${DOCKER_USER}/kadalu-operator:${KADALU_LATEST}
	docker push ${DOCKER_USER}/kadalu-csi:${KADALU_LATEST}
	docker push ${DOCKER_USER}/kadalu-server:${KADALU_LATEST}
endif
