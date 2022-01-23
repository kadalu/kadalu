"""
nodeserver implementation
"""
import logging
import os
import time
import csi_pb2
import csi_pb2_grpc
import grpc
from volumeutils import (mount_glusterfs, mount_volume, unmount_volume)

from kadalulib import logf

HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/bin/mount"
UNMOUNT_CMD = "/bin/umount"

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

        hostvol = request.volume_context.get("hostvol", "")
        pvpath = request.volume_context.get("path", "")
        pvtype = request.volume_context.get("pvtype", "")
        voltype = request.volume_context.get("type", "")
        gserver = request.volume_context.get("gserver", None)
        gvolname = request.volume_context.get("gvolname", None)
        options = request.volume_context.get("options", None)

        # Storage volfile options
        storage_options = request.volume_context.get("storage_options", "")
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

        pvpath_full = os.path.join(mntdir, pvpath)

        logging.debug(logf(
            "Received a valid mount request",
            request=request,
            voltype=voltype,
            hostvol=hostvol,
            pvpath=pvpath,
            pvtype=pvtype,
            pvpath_full=pvpath_full,
            storage_options=storage_options
        ))

        volume = {
            'name': hostvol,
            'g_volname': gvolname,
            'g_host': gserver,
            'g_options': options,
            'type': voltype,
        }

        mountpoint = mount_glusterfs(volume, mntdir, storage_options, True)

        if voltype == "External":
            logging.debug(logf(
                "Mounted Volume for PV",
                volume=volume,
                mntdir=mntdir,
                storage_options=storage_options
            ))
            # return csi_pb2.NodePublishVolumeResponse()

        # When 'storage_options' is configured mountpoint & volfile path change,
        # Update pvpath_full accordingly.
        if storage_options != "":
            pvpath_full = os.path.join(mountpoint, pvpath)

        logging.debug(logf(
            "Mounted Hosting Volume",
            pv=request.volume_id,
            hostvol=hostvol,
            mntdir=mntdir
        ))
        # Mount the PV
        # TODO: Handle Volume capability mount flags
        if mount_volume(pvpath_full, request.target_path, pvtype, fstype=None):
            logging.info(logf(
                "Mounted PV",
                volume=request.volume_id,
                pvpath=pvpath,
                pvtype=pvtype,
                hostvol=hostvol,
                target_path=request.target_path,
                duration_seconds=time.time() - start_time
            ))
        else:
            errmsg = "Unable to bind PV to target path"
            logging.error(errmsg)
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
        unmount_volume(request.target_path)

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
