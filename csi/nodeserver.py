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


class NodeServer(csi_pb2_grpc.NodeServicer):

    def NodePublishVolume(self, request, context):
        volume = get_value_from_context(request.volume_context, "hostvol")
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, volume)

        # Try to mount the Host Volume, handle failure if already mounted
        # TODO: Get Glusterfs command with static Volfile
        execute(GLUSTERFS_CMD,)

        # Mount the PV
        pvtype = get_value_from_context(request.volume_context, "pvtype")
        pvpath = os.path.join(mntdir, request.volume_id)
        # TODO: Handle Volume capability mount flags
        if pvtype == "virtblock":
            execute(MOUNT_CMD, "-t", "xfs", pvpath, request.target_path)
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
            # TODO: Set Node ID
            node_id=""
        )


def main():
    logging.basicConfig()
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_NodeServicer_to_server(NodeServer(), server)
    server.add_insecure_port('[::]:50051')
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
