.PHONY: help build-grpc build-containers gen-manifest pylint prepare-release release

DOCKER_USER?=kadalu
KADALU_VERSION?=latest
KADALU_LATEST?=latest

help:
	@echo "    make build-grpc        - To generate grpc Python Code"
	@echo "    make build-containers  - To create server, csi and Operator containers"
	@echo "    make gen-manifest      - To generate manifest files to deploy"
	@echo "    make pylint            - To validate all Python code with Pylint"
	@echo "    make prepare-release   - Generate Manifest file and build containers for specific version and latest"
	@echo "    make release           - Publish the built container images"

build-grpc:
	python3 -m grpc_tools.protoc -I./csi/protos --python_out=csi --grpc_python_out=csi ./csi/protos/csi.proto

build-containers:
	DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} bash build.sh

gen-manifest:
	@echo "Generating manifest files, run the following commands"
	@echo
	@mkdir -p manifests
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator.yaml
	@echo "kubectl create -f manifests/kadalu-operator.yaml"
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		OPENSHIFT=1                                          \
		python3 extras/scripts/gen_manifest.py manifests/kadalu-operator-openshift.yaml
	@echo
	@echo "In the case of OpenShift, deploy Kadalu Operator by running "
	@echo "the following command"
	@echo
	@echo "Note: Security Context Constraints can be applied only by admins, "
	@echo 'Run `oc login -u system:admin` to login as admin'
	@echo
	@echo "oc create -f manifests/kadalu-operator-openshift.yaml"

pylint:
	@cp lib/kadalulib.py csi/
	@cp lib/kadalulib.py server/
	@cp lib/kadalulib.py operator/
	@cp server/kadalu_quotad/quotad.py server/
	@pylint --disable=W0511 -s n lib/kadalulib.py
	@pylint --disable=W0511 -s n server/glusterfsd.py
	@pylint --disable=W0511 -s n server/quotad.py
	@pylint --disable=W0511 -s n server/server.py
	@pylint --disable=W0511 -s n server/shd.py
	@pylint --disable=W0511 -s n csi/controllerserver.py
	@pylint --disable=W0511 -s n csi/identityserver.py
	@pylint --disable=W0511 -s n csi/main.py
	@pylint --disable=W0511 -s n csi/nodeserver.py
	@pylint --disable=W0511 -s n csi/volumeutils.py
	@pylint --disable=W0511 -s n operator/main.py
	@pylint --disable=W0511 -s n extras/scripts/gen_manifest.py
	@pylint --disable=W0511,W0611 -s n cli/kubectl_kadalu/main.py
	@pylint --disable=W0511 -s n cli/kubectl_kadalu/utils.py
	@pylint --disable=W0511 -s n cli/kubectl_kadalu/storage_add.py
	@pylint --disable=W0511 -s n cli/kubectl_kadalu/install.py
	@rm csi/kadalulib.py
	@rm server/kadalulib.py
	@rm operator/kadalulib.py
	@rm server/quotad.py

ifeq ($(KADALU_VERSION), latest)
prepare-release:
	@echo "KADALU_VERSION can't be latest for release"
else
prepare-release:
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		$(MAKE) gen-manifest
	@cp manifests/kadalu-operator.yaml \
		manifests/kadalu-operator-${KADALU_VERSION}.yaml
	@cp manifests/kadalu-operator-openshift.yaml \
		manifests/kadalu-operator-openshift-${KADALU_VERSION}.yaml
	@echo "Generated manifest file. Version: ${KADALU_VERSION}"
	@echo "Building containers(Version: ${KADALU_VERSION}).."
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		$(MAKE) build-containers
endif

pypi-build:
	echo ${KADALU_VERSION} > cli/VERSION
	cd cli; rm -rf dist; python3 setup.py sdist;
	@cp lib/kadalulib.py server/kadalu_quotad/
	echo ${KADALU_VERSION} > server/VERSION
	cd server; rm -rf dist; python3 setup.py sdist;

ifeq ($(TWINE_PASSWORD),)
pypi-upload: pypi-build
	cd cli; twine upload --username kadalu dist/*
	cd server; twine upload --username kadalu dist/*
else
pypi-upload: pypi-build
	cd cli; twine upload --username kadalu -p ${TWINE_PASSWORD} dist/*
	cd server; twine upload --username kadalu -p ${TWINE_PASSWORD} dist/*

endif

ifeq ($(KADALU_VERSION), latest)
release: prepare-release
else
release: prepare-release pypi-upload
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
