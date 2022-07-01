"""
nodeserver implementation
"""
import logging
import os
import time

import csi_pb2
import csi_pb2_grpc
import grpc
from kadalulib import logf
from volumeutils import PersistentVolume, PvException


# noqa # pylint: disable=too-many-locals
# noqa # pylint: disable=too-many-statements
class NodeServer(csi_pb2_grpc.NodeServicer):
    """
    NodeServer object is responsible for handling host
    volume mount and PV mounts.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def NodePublishVolume(self, request, context):
        start_time = time.time()
        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodePublishVolumeResponse()

        if not request.target_path:
            errmsg = "Target path is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodePublishVolumeResponse()

        if not request.volume_capability:
            errmsg = "Volume capability is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodePublishVolumeResponse()

        if not request.volume_context:
            errmsg = "Volume context is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodePublishVolumeResponse()

        pvol = PersistentVolume.from_volume_context(request.volume_context)

        logging.debug(logf(
            "Received a valid mount request",
            request=request,
            voltype=pvol.type,
            pool_name=pvol.pool.name,
            pvpath=pvol.path,
            pvtype=pvol.type,
            pvpath_full=pvol.abspath
        ))

        # Mount the PV
        # TODO: Handle Volume capability mount flags
        try:
            pvol.mount(request.target_path)
            logging.info(logf(
                "Mounted PV",
                volume=request.volume_id,
                pvpath=pvol.path,
                pvtype=pvol.type,
                pv_name=pvol.pool.name,
                target_path=request.target_path,
                duration_seconds=time.time() - start_time
            ))
        except PvException as ex:
            logging.error(ex)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.FAILED_PRECONDITION)

        return csi_pb2.NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request, context):
        # TODO: Validation and handle target_path failures

        if not request.volume_id:
            errmsg = "Volume ID is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodeUnpublishVolumeResponse()

        if not request.target_path:
            errmsg = "Target path is empty and must be provided"
            logging.error(errmsg)
            context.set_details(errmsg)
            context.set_code(grpc.StatusCode.INVALID_ARGUMENT)
            return csi_pb2.NodeUnpublishVolumeResponse()

        logging.debug(logf(
            "Received the unmount request",
            volume=request.volume_id,
        ))
        PersistentVolume.unmount(request.target_path)

        return csi_pb2.NodeUnpublishVolumeResponse()

    def NodeGetCapabilities(self, request, context):
        return csi_pb2.NodeGetCapabilitiesResponse()

    def NodeGetInfo(self, request, context):
        return csi_pb2.NodeGetInfoResponse(
            node_id=os.environ["NODE_ID"],
        )

    def NodeExpandVolume(self, request, context):

        logging.warning(logf(
            "NodeExpandVolume called, which is not implemented."
        ))

        return csi_pb2.NodeExpandVolumeResponse()
