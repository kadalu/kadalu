"""
Starting point of CSI driver GRP server
"""
import logging
import os
import signal
import time
from concurrent import futures

import grpc

from kadalu.csi import csi_pb2_grpc
from kadalu.csi.controllerserver import ControllerServer
from kadalu.csi.identityserver import IdentityServer
from kadalu.common.utils import CommandException, logf, logging_setup
from kadalu.csi.nodeserver import NodeServer
from kadalu.csi.volumeutils import Pool

_ONE_DAY_IN_SECONDS = 60 * 60 * 24

def mount_pools():
    """
    Mount storage pools if any pools exist after a pod reboot
    """
    if os.environ.get("CSI_ROLE", "-") != "provisioner":
        logging.debug("Pool need to be mounted on only provisioner pod")
        return

    pools = Pool.list()
    for pool in pools:
        if pool.single_pv_per_pool:
            # Need to skip mounting external non-native mounts in-order for
            # kadalu-quotad not to set quota xattrs
            continue

        try:
            pool.mount()
            logging.info(logf("Pool is mounted successfully",
                              pool_name=pool.name))
        except CommandException:
            logging.error(logf("Unable to mount the Pool",
                               pool_name=pool.name))
    return


def reconfigure_pool_mounts(_signum, _frame):
    """
    Reconfigure the mounts by regenerating the volfiles.
    """
    pools = Pool.list()
    for pool in pools:
        if pool.is_mode_external:
            # Need to skip remount external
            continue

        if pool.reload_process():
            logging.info(logf("Pool reloaded successfully",
                              pool_name=pool.name))


def main():
    """
    Register Controller Server, Node server and Identity Server and start
    the GRPC server in required endpoint
    """
    logging_setup()

    # If Provisioner pod reboots, mount pools if they exist before reboot
    mount_pools()

    signal.signal(signal.SIGHUP, reconfigure_pool_mounts)

    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    csi_pb2_grpc.add_ControllerServicer_to_server(ControllerServer(), server)
    csi_pb2_grpc.add_NodeServicer_to_server(NodeServer(), server)
    csi_pb2_grpc.add_IdentityServicer_to_server(IdentityServer(), server)

    server.add_insecure_port(os.environ.get("CSI_ENDPOINT", "unix://plugin/csi.sock"))
    logging.info("Server started")
    server.start()
    try:
        while True:
            time.sleep(_ONE_DAY_IN_SECONDS)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == '__main__':
    main()
