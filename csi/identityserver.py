"""
Identity Server implementation
"""
import csi_pb2
import csi_pb2_grpc


DRIVER_NAME = "kadalu"
DRIVER_VERSION = "0.7.0"


class IdentityServer(csi_pb2_grpc.IdentityServicer):
    """
    IdentityServer object is responsible for providing
    CSI driver's identity
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def GetPluginInfo(self, request, context):
        return csi_pb2.GetPluginInfoResponse(
            name=DRIVER_NAME,
            vendor_version=DRIVER_VERSION
        )

    def GetPluginCapabilities(self, request, context):
        # using getattr to avoid Pylint error
        capability_type = getattr(
            csi_pb2.PluginCapability.Service, "Type").Value

        return csi_pb2.GetPluginCapabilitiesResponse(
            capabilities=[
                {
                    "service": {
                        "type": capability_type("CONTROLLER_SERVICE")
                    }
                }
            ]
        )

    def Probe(self, request, context):
        return csi_pb2.ProbeResponse()
