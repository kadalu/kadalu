"""
nodeserver implementation
"""
import os

import csi_pb2
import csi_pb2_grpc
from utils import mount_glusterfs, execute, PV_TYPE_VIRTBLOCK


HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/usr/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"


class NodeServer(csi_pb2_grpc.NodeServicer):
    """
    NodeServer object is responsible for handling host
    volume mount and PV mounts.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def NodePublishVolume(self, request, context):
        volume = request.volume_context.get("hostvol", "")
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, volume)

        # Try to mount the Host Volume, handle failure if already mounted
        mount_glusterfs(volume, mntdir)

        # Mount the PV
        pvtype = request.volume_context.get("pvtype", "")
        pvpath = os.path.join(mntdir, pvtype, request.volume_id)
        # TODO: Handle Volume capability mount flags
        if pvtype == PV_TYPE_VIRTBLOCK:
            execute(
                MOUNT_CMD,
                "-t",
                request.volume_context.get("fstype", "xfs"),
                pvpath,
                request.target_path
            )
        else:  # pv type is subdir
            execute(MOUNT_CMD, "--bind", pvpath, request.target_path)

        return csi_pb2.NodePublishVolumeResponse()

    def NodeUnpublishVolume(self, request, context):
        # TODO: Validation and handle target_path failures

        # if request.volume_id == "":
        #     raise
        # if request.target_path == "":
        #     raise
        # Check is mount

        if os.path.ismount(request.target_path):
            execute(UNMOUNT_CMD, request.target_path)

        return csi_pb2.NodeUnpublishVolumeResponse()

    def NodeGetCapabilities(self, request, context):
        return csi_pb2.NodeGetCapabilitiesResponse()

    def NodeGetInfo(self, request, context):
        return csi_pb2.NodeGetInfoResponse(
            node_id=os.environ["NODE_ID"],
        )
