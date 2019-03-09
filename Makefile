.PHONY: help build-grpc

NODE?=kube1
BRICK?=/exports/data

help:
	@echo "    make build-grpc        - To generate grpc Python Code"
	@echo "    make build-containers  - To create server, csi and Operator containers"
	@echo "    make gen-manifest      - To generate manifest files to deploy"

build-grpc:
	python3 -m grpc_tools.protoc -I./csi/protos --python_out=csi --grpc_python_out=csi ./csi/protos/csi.proto

build-containers:
	bash build.sh

gen-manifest:
	@echo "Generating manifest files for node=${NODE} brick=${BRICK},"
	@echo "run the following commands"
	@echo
	@python3 extras/scripts/gen_manifest.py ${NODE} ${BRICK}
