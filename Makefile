.PHONY: help build-grpc

DOCKER_USER?=kadalu
KADALU_VERSION?=latest


help:
	@echo "    make build-grpc        - To generate grpc Python Code"
	@echo "    make build-containers  - To create server, csi and Operator containers"
	@echo "    make gen-manifest      - To generate manifest files to deploy"
	@echo "    make pylint            - To validate all Python code with Pylint"

build-grpc:
	python3 -m grpc_tools.protoc -I./csi/protos --python_out=csi --grpc_python_out=csi ./csi/protos/csi.proto

build-containers:
	DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} bash build.sh

gen-manifest:
	@echo "Generating manifest files, run the following commands"
	@echo
	@mkdir -p manifests
	@DOCKER_USER=${DOCKER_USER} KADALU_VERSION=${KADALU_VERSION} \
		python3 extras/scripts/gen_manifest.py
	@cat templates/namespace.yaml > manifests/kadalu-operator.yaml
	@echo >> manifests/kadalu-operator.yaml
	@cat templates/operator.yaml >> manifests/kadalu-operator.yaml
	@echo >> manifests/kadalu-operator.yaml
	@echo "kubectl create -f manifests/kadalu-operator.yaml"

pylint:
	@cp lib/kadalulib.py csi/
	@cp lib/kadalulib.py server/
	@cp lib/kadalulib.py operator/
	-pylint-3 --disable=W0511 -s n lib/kadalulib.py
	-pylint-3 --disable=W0511 -s n server/glusterfsd.py
	-pylint-3 --disable=W0511 -s n server/quotad.py
	-pylint-3 --disable=W0511 -s n server/server.py
	-pylint-3 --disable=W0511 -s n csi/controllerserver.py
	-pylint-3 --disable=W0511 -s n csi/identityserver.py
	-pylint-3 --disable=W0511 -s n csi/main.py
	-pylint-3 --disable=W0511 -s n csi/nodeserver.py
	-pylint-3 --disable=W0511 -s n csi/volumeutils.py
	-pylint-3 --disable=W0511 -s n operator/main.py
	@rm csi/kadalulib.py
	@rm server/kadalulib.py
	@rm operator/kadalulib.py
