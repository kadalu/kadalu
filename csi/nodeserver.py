"""
nodeserver implementation
"""
import os
import logging
import time

import csi_pb2
import csi_pb2_grpc
from volumeutils import mount_volume, unmount_volume, mount_glusterfs, \
    mount_glusterfs_with_host
from kadalulib import logf


HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"


class NodeServer(csi_pb2_grpc.NodeServicer):
    """
    NodeServer object is responsible for handling host
    volume mount and PV mounts.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def NodePublishVolume(self, request, context):
        start_time = time.time()
        hostvol = request.volume_context.get("hostvol", "")
        pvpath = request.volume_context.get("path", "")
        pvtype = request.volume_context.get("pvtype", "")
        voltype = request.volume_context.get("type", "")
        gserver = request.volume_context.get("gserver", None)
        gvolname = request.volume_context.get("gvolname", None)
        options = request.volume_context.get("options", None)

        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

        pvpath_full = os.path.join(mntdir, pvpath)

        logging.debug(logf(
            "Received the mount request",
            volume=request.volume_id,
            voltype=voltype,
            hostvol=hostvol,
            pvpath=pvpath,
            pvtype=pvtype
        ))

        if voltype == "External":
            # If no separate PV Path, use the whole volume as PV
            if pvpath == "":
                mount_glusterfs_with_host(gvolname, request.target_path, gserver, options, True)

                logging.debug(logf(
                    "Mounted Volume for PV",
                    volume=request.volume_id,
                    mntdir=request.target_path,
                    pvpath=gserver,
                    options=options
                ))
                return csi_pb2.NodePublishVolumeResponse()

        volume = {
            'name': hostvol,
            'g_volname': gvolname,
            'g_host': gserver,
            'g_options': options,
            'type': voltype,
        }

        mount_glusterfs(volume, mntdir, True)

        logging.debug(logf(
            "Mounted Hosting Volume",
            pv=request.volume_id,
            hostvol=hostvol,
            mntdir=mntdir,
        ))
        # Mount the PV
        # TODO: Handle Volume capability mount flags
        mount_volume(pvpath_full, request.target_path, pvtype, fstype=None)
        logging.info(logf(
            "Mounted PV",
            volume=request.volume_id,
            pvpath=pvpath,
            pvtype=pvtype,
            hostvol=hostvol,
            duration_seconds=time.time() - start_time
        ))
        return csi_pb2.NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request, context):
        # TODO: Validation and handle target_path failures
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
