"""
controller server implementation
"""
import os

import csi_pb2
import csi_pb2_grpc
from utils import mount_glusterfs, execute, get_pv_hosting_volumes, \
    PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK, is_space_available

HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/usr/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"
MKFS_XFS_CMD = "/usr/sbin/mkfs.xfs"


class ControllerServer(csi_pb2_grpc.ControllerServicer):
    """
    ControllerServer object is responsible for handling host
    volume mount and PV creation.
    Ref:https://github.com/container-storage-interface/spec/blob/master/spec.md
    """
    def CreateVolume(self, request, context):
        pvsize = request.capacity_range.required_bytes

        # TODO: Check the available space under lock

        host_volumes = get_pv_hosting_volumes()
        hostvol = ""
        for hvol in host_volumes:
            mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
            # Try to mount the Host Volume, handle failure if already mounted
            mount_glusterfs(hvol, mntdir)
            if is_space_available(mntdir, pvsize):
                hostvol = hvol
                break

        if hostvol == "":
            raise Exception("no Hosting Volumes available, add more storage")

        pvtype = PV_TYPE_SUBVOL
        for vol_capability in request.volume_capabilities:
            # using getattr to avoid Pylint error
            single_node_writer = getattr(csi_pb2.VolumeCapability.AccessMode,
                                         "SINGLE_NODE_WRITER")

            if vol_capability.access_mode.mode == single_node_writer:
                pvtype = PV_TYPE_VIRTBLOCK

        volpath = os.path.join(HOSTVOL_MOUNTDIR, hostvol, pvtype, request.name)
        if pvtype == PV_TYPE_VIRTBLOCK:
            # Create a file with required size
            os.makedirs(os.path.dirname(volpath), exist_ok=True)
            volpath_fd = os.open(volpath, os.O_CREAT | os.O_RDWR)
            os.close(volpath_fd)
            os.truncate(volpath, pvsize)
            # TODO: Multiple FS support based on volume_capability mount option
            execute(MKFS_XFS_CMD, volpath)
        else:
            # Create a subdir
            os.makedirs(volpath)
            # TODO: Set BackendQuota using RPC to sidecar
            # container of each glusterfsd pod

        return csi_pb2.CreateVolumeResponse(
            volume={
                "volume_id": request.name,
                "capacity_bytes": pvsize,
                "volume_context": {
                    "hostvol": hostvol,
                    "pvtype": pvtype,
                    "fstype": "xfs"
                }
            }
        )

    def DeleteVolume(self, request, context):
        hostvol = request.volume_context.get("hostvol", "")
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

        # Try to mount the Host Volume, handle
        # failure if already mounted
        mount_glusterfs(hostvol, mntdir)

        # TODO: get pvtype from storage class
        pvtype = request.volume_context.get("pvtype", "")
        volpath = os.path.join(mntdir, pvtype, request.name)
        if pvtype == PV_TYPE_VIRTBLOCK:
            os.remove(volpath)
        else:
            os.removedirs(volpath)

        return csi_pb2.DeleteVolumeResponse()

    def ValidateVolumeCapabilities(self, request, context):
        # TODO
        pass

    def ListVolumes(self, request, context):
        # TODO
        # Mount hostvol
        # Listdir and return the list
        # Volume capacity need to be stored somewhere
        pass

    def ControllerGetCapabilities(self, request, context):
        # using getattr to avoid Pylint error
        capability_type = getattr(
            csi_pb2.ControllerServiceCapability.RPC, "Type").Value

        return csi_pb2.ControllerGetCapabilitiesResponse(
            capabilities=[
                {
                    "rpc": {
                        "type": capability_type("CREATE_DELETE_VOLUME")
                    }
                },
                {
                    "rpc": {
                        "type": capability_type("LIST_VOLUMES")
                    }
                }
            ]
        )
