from concurrent import futures
import time
import logging

import grpc

import csi_pb2
import csi_pb2_grpc

_ONE_DAY_IN_SECONDS = 60 * 60 * 24
HOSTVOL_MOUNTDIR = "/mnt/"
GLUSTERFS_CMD = "/usr/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"


def get_value_from_context(context, key):
    for k, v in context:
        if k == key:
            return v

    return ""


class ControllerServer(csi_pb2_grpc.ControllerServicer):

    def CreateVolume(self, request, context):
        # TODO: Get Hosting Volume name from Storage Class Option
        hostVol = "ghostvol"
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostVol)

        # # Try to mount the Host Volume, handle failure if already mounted
        # # TODO: Get Glusterfs command with static Volfile
        execute(GLUSTERFS_CMD,)

        # TODO: Get Volume capacity from PV claim
        pvsize = 1073741824  # 1GiB
        
        # TODO: get pvtype from storage class
        pvtype = "virtblock"
        if pvtype == "virtblock":
            # Create a file with required size
            # Mkfs.xfs or based on storage class option
            pass
        else:
            # Create a subdir
            # Set BackendQuota using RPC to sidecar container of each glusterfsd pod
            pass

        return csi_pb2.CreateVolumeResponse(
            volume_id=request.volume_id,
            capacity_bytes=pvsize,
            volume_context=[
                {"key": "glustervol", "value": hostVol},
                {"key": "pvtype", "value": pvtype}
            ]
        )

    def DeleteVolume(self, request, context):
        # TODO: Get Hosting Volume name from Storage Class Option
        hostVol = "ghostvol"
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostVol)

        # # Try to mount the Host Volume, handle failure if already mounted
        # # TODO: Get Glusterfs command with static Volfile
        execute(GLUSTERFS_CMD,)

        # TODO: get pvtype from storage class
        pvtype = "virtblock"
        if pvtype == "virtblock":
            # Remove file
            pass
        else:
            # Remove directory
            pass

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
        # TODO
        pass


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_ControllerServicer_to_server(ControllerServer(), server)
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
