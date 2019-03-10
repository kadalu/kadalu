import os

import csi_pb2
import csi_pb2_grpc
from utils import mount_glusterfs, execute

HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/usr/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"
mkfs_xfs_cmd = "/usr/sbin/mkfs.xfs"


class ControllerServer(csi_pb2_grpc.ControllerServicer):

    def CreateVolume(self, request, context):
        # TODO: Get Hosting Volume name from Storage Class Option
        hostVol = "glustervol"
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostVol)

        # # Try to mount the Host Volume, handle failure if already mounted
        mount_glusterfs(hostVol, mntdir)

        # TODO: Get Volume capacity from PV claim
        pvsize = 1073741824  # 1GiB

        # TODO: get pvtype from storage class
        pvtype = "virtblock"
        volpath = os.path.join(mntdir, request.name)
        if pvtype == "virtblock":
            # Create a file with required size
            fd = os.open(volpath, os.O_CREAT | os.O_RDWR)
            os.close(fd)
            os.truncate(volpath, pvsize)
            # Mkfs.xfs or based on storage class option
            execute(mkfs_xfs_cmd, volpath)
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
                    "hostvol": hostVol,
                    "pvtype": pvtype,
                    "fstype": "xfs"
                }
            }
        )

    def DeleteVolume(self, request, context):
        # TODO: Get Hosting Volume name from Storage Class Option
        hostVol = "glustervol"
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostVol)

        # Try to mount the Host Volume, handle
        # failure if already mounted
        mount_glusterfs(hostVol, mntdir)

        # TODO: get pvtype from storage class
        pvtype = "virtblock"
        volpath = os.path.join(mntdir, request.name)
        if pvtype == "virtblock":
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
        capabilityType = csi_pb2.ControllerServiceCapability.RPC.Type.Value
        return csi_pb2.ControllerGetCapabilitiesResponse(
            capabilities=[
                {
                    "rpc": {
                        "type": capabilityType("CREATE_DELETE_VOLUME")
                    }
                },
                {
                    "rpc": {
                        "type": capabilityType("LIST_VOLUMES")
                    }
                }
            ]
        )
