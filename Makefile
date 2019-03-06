.PHONY: help build-grpc

help:
	@echo "    make build-grpc  - To generate grpc Python Code"

build-grpc:
	python3 -m grpc_tools.protoc -I./csi/protos --python_out=csi --grpc_python_out=csi ./csi/protos/csi.proto
