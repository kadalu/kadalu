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
from volumeutils import (NODE_ID, PVC_POOL, mount_glusterfs,
                         mount_glusterfs_with_host, mount_volume,
                         unmount_volume, update_pv_target)

HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/bin/mount"
UNMOUNT_CMD = "/bin/umount"


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

        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

        pvpath_full = os.path.join(mntdir, pvpath)

        logging.debug(logf(
            "Received a valid mount request",
            request=request,
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

        # Store node and target path corresponding to PVC
        if PVC_POOL.get(request.target_path) is None:
            update_pv_target(hostvol_mnt=mntdir,
                             pvpath=pvpath,
                             node=NODE_ID,
                             entry="add",
                             target=request.target_path)
            PVC_POOL[request.target_path] = (mntdir, pvpath)
        logging.info(logf(
            "Mounted PV",
            volume=request.volume_id,
            pvpath=pvpath,
            pvtype=pvtype,
            hostvol=hostvol,
            target_path=request.target_path,
            duration_seconds=time.time() - start_time
        ))
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

        logging.debug(
            logf(
                "Received the unmount request",
                volume=request.volume_id,
            ))

        # Workload might be re-scheduled, so clear off existing target_path
        # from info_file metadata and it should be idempotent
        if PVC_POOL.get(request.target_path) is not None:
            update_pv_target(*PVC_POOL[request.target_path],
                             node=NODE_ID,
                             entry="remove",
                             target=request.target_path)

            # PVCs count may build-up overtime, so delete the key from global dict
            PVC_POOL.pop(request.target_path, None)

        unmount_volume(request.target_path)

        return csi_pb2.NodeUnpublishVolumeResponse()

    def NodeGetCapabilities(self, request, context):
        return csi_pb2.NodeGetCapabilitiesResponse()

    def NodeGetInfo(self, request, context):
        return csi_pb2.NodeGetInfoResponse(
            node_id=NODE_ID,
        )

    def NodeExpandVolume(self, request, context):

        logging.warning(logf(
            "NodeExpandVolume called, which is not implemented."
        ))

        return csi_pb2.NodeExpandVolumeResponse()
