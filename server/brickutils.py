"""
Starts Gluster Brick(fsd) process
"""
import logging
import os
import sys

import xattr
from kadalulib import CommandException, execute, logf

# noqa # pylint: disable=I1101
MKFS_XFS_CMD = "/sbin/mkfs.xfs"


def create_brickdir(brick_path):
    """Create Brick directory and other directories required"""
    os.makedirs(os.path.join(brick_path, ".glusterfs"),
                mode=0o755,
                exist_ok=True)


def verify_brickdir_xattr_support(brick_path):
    """Verify Brick dir supports xattrs"""
    test_xattr_name = "user.testattr"
    test_xattr_value = b"testvalue"
    try:
        xattr.set(brick_path, test_xattr_name, test_xattr_value)
        val = xattr.get(brick_path, test_xattr_name)
        if val != test_xattr_value:
            logging.error(logf("Xattr value mismatch.",
                               actual=val,
                               expected=test_xattr_value))
            sys.exit(1)
    except OSError as err:
        logging.error(logf("Extended attributes are not "
                           "supported",
                           error=err))
        sys.exit(1)


def create_and_mount_brick(brick_device, brick_path, brickfs):
    """
    Create brick filesystem and mount the brick. Currently
    only xfs is supported
    """

    # If brick device path is not starts with /dev then use
    # /brickdev prefix. Brick device directory passed by the user
    # is mounted as /brickdev to avoid mixing with any other
    # dirs inside container.
    if not brick_device.startswith("/dev/"):
        brick_device = "/brickdev/" + os.path.basename(brick_device)

    mountdir = os.path.dirname(brick_path)
    os.makedirs(mountdir,
                mode=0o755,
                exist_ok=True)

    try:
        execute("mount", brick_device, mountdir)
        logging.info(logf(
            "Successfully mounted device on path",
            fstype=brickfs,
            device=brick_device,
            mountdir=mountdir,
            ))
    except CommandException as err:
        logging.info(logf(
            "Failed to mount device, continuing with mkfs",
            err=err,
            fstype=brickfs,
            device=brick_device,
            mountdir=mountdir,
        ))
        if 'wrong fs type' in err.err:
            # This error pops up when we do mount on an empty device or wrong fs
            # Try doing a mkfs and try mount
            try:
                execute(MKFS_XFS_CMD, brick_device)
                logging.info(logf(
                    "Successfully created xfs file system on device",
                    fstype=brickfs,
                    device=brick_device,
                    ))
            except CommandException as err1:
                if "appears to contain an existing filesystem" not in err1.err:
                    logging.error(logf(
                        "Failed to create file system",
                        fstype=brickfs,
                        device=brick_device,
                        error=err1,
                    ))
                    sys.exit(1)
                else:
                    logging.info(logf(
                        "Failed to perform mkfs on device. continuing with mount",
                        err=err1,
                        device=brick_device,
                        mountdir=mountdir,
                    ))
            try:
                execute("mount", brick_device, mountdir)
                logging.info(logf(
                    "Successfully mounted device on path",
                    fstype=brickfs,
                    device=brick_device,
                    mountdir=mountdir,
                    ))
            except CommandException as err1:
                logging.error(logf(
                    "Failed to mount export brick (after mkfs)",
                    fstype=brickfs,
                    device=brick_device,
                    mountdir=mountdir,
                    error=err1,
                ))
                sys.exit(1)

        elif 'already mounted' not in err.err:
            logging.error(logf(
                "Failed to mount export brick",
                fstype=brickfs,
                device=brick_device,
                mountdir=mountdir,
                error=err,
            ))
            sys.exit(1)

        else:
            pass
