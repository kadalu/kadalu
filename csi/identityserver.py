from concurrent import futures
import time
import logging

import grpc

import csi_pb2
import csi_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24


DRIVER_NAME = "org.gluster.glusterfs"
DRIVER_VERSION = "0.1.0"


class IdentityServer(csi_pb2_grpc.IdentityServicer):

    def GetPluginInfo(self, request, context):
        return csi_pb2.GetPluginInfoResponse(
            name=DRIVER_NAME,
            vendor_version=DRIVER_VERSION
        )

    def GetPluginCapabilities(self, request, context):
        # TODO: Update Capabilities
        return csi_pb2.GetPluginCapabilitiesResponse(
            capabilities=[]
        )

    def Probe(self, request, context):
        return csi_pb2.Probe()


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_IdentityServicer_to_server(IdentityServer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    logging.basicConfig()
    serve()
