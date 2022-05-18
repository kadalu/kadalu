#!/usr/bin/python3

"""
Prepares, Validates and then starts the Moana Agent Process
"""

import os

from kadalulib import Monitor, Proc, logging_setup
from brickutils import (
    create_and_mount_brick,
    create_brickdir,
    verify_brickdir_xattr_support
)


def start_server_process():
    """
    Start Moana Agent Process and Exporter Service
    """
    brick_device = os.environ.get("BRICK_DEVICE", None)
    brick_path = os.environ["BRICK_PATH"]
    if brick_device is not None and brick_device != "":
        brickfs = os.environ.get("BRICK_FS", "xfs")
        create_and_mount_brick(brick_device, brick_path, brickfs)

    create_brickdir(brick_path)
    verify_brickdir_xattr_support(brick_path)

    mon = Monitor()
    curr_dir = os.path.dirname(__file__)
    mon.add_process(Proc("metrics", "python3", [curr_dir + "/exporter.py"]))
    mon.add_process(Proc("Storage Manager", "kadalu", ["mgr"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    logging_setup()
    start_server_process()
