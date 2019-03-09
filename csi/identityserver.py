import csi_pb2
import csi_pb2_grpc
from utils import DRIVER_NAME, DRIVER_VERSION


class IdentityServer(csi_pb2_grpc.IdentityServicer):

    def GetPluginInfo(self, request, context):
        return csi_pb2.GetPluginInfoResponse(
            name=DRIVER_NAME,
            vendor_version=DRIVER_VERSION
        )

    def GetPluginCapabilities(self, request, context):
        capabilityType = csi_pb2.PluginCapability.Service.Type.Value
        return csi_pb2.GetPluginCapabilitiesResponse(
            capabilities=[
                {
                    "service": {
                        "type": capabilityType("CONTROLLER_SERVICE")
                    }
                }
            ]
        )

    def Probe(self, request, context):
        return csi_pb2.ProbeResponse()
