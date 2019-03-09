#!/usr/bin/python3
from concurrent import futures
import time
import logging

import grpc

import csi_pb2_grpc
from utils import get_csi_endpoint
from identityserver import IdentityServer
from controllerserver import ControllerServer
from nodeserver import NodeServer


_ONE_DAY_IN_SECONDS = 60 * 60 * 24


def main():
    logging.basicConfig()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_ControllerServicer_to_server(ControllerServer(), server)
    csi_pb2_grpc.add_NodeServicer_to_server(NodeServer(), server)
    csi_pb2_grpc.add_IdentityServicer_to_server(IdentityServer(), server)

    server.add_insecure_port(get_csi_endpoint())
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
