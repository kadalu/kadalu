"""
Starts Gluster Brick(fsd) process
"""
import logging
import os
import sys

import xattr

from kadalu.common.utils import CommandException, execute, logf

# noqa # pylint: disable=I1101
MKFS_XFS_CMD = "/sbin/mkfs.xfs"


def create_storage_unit_dir(storage_unit_path):
    """Create Storage Unit directory and other directories required"""
    os.makedirs(os.path.join(storage_unit_path, ".glusterfs"),
                mode=0o755,
                exist_ok=True)


def verify_storage_unit_dir_xattr_support(storage_unit_path):
    """Verify Storage Unit dir supports xattrs"""
    test_xattr_name = "user.testattr"
    test_xattr_value = b"testvalue"
    try:
        xattr.set(storage_unit_path, test_xattr_name, test_xattr_value)
        val = xattr.get(storage_unit_path, test_xattr_name)
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


def create_and_mount_storage_unit(storage_unit_device, storage_unit_path,
                                  storage_unit_fs):
    """
    Create Storage Unit filesystem and mount the Storage Unit. Currently
    only xfs is supported
    """

    # If storage_unit device path is not starts with /dev then use
    # /storage_unit_dev prefix. Storage Unit device directory passed by the user
    # is mounted as /storage_unit_dev to avoid mixing with any other
    # dirs inside container.
    if not storage_unit_device.startswith("/dev/"):
        storage_unit_device = "/storage_unit_dev/" + os.path.basename(storage_unit_device)

    mountdir = os.path.dirname(storage_unit_path)
    os.makedirs(mountdir,
                mode=0o755,
                exist_ok=True)

    try:
        execute("mount", storage_unit_device, mountdir)
        logging.info(logf(
            "Successfully mounted device on path",
            fstype=storage_unit_fs,
            device=storage_unit_device,
            mountdir=mountdir,
            ))
    except CommandException as err:
        logging.info(logf(
            "Failed to mount device, continuing with mkfs",
            err=err,
            fstype=storage_unit_fs,
            device=storage_unit_device,
            mountdir=mountdir,
        ))
        if 'wrong fs type' in err.err:
            # This error pops up when we do mount on an empty device or wrong fs
            # Try doing a mkfs and try mount
            try:
                execute(MKFS_XFS_CMD, storage_unit_device)
                logging.info(logf(
                    "Successfully created xfs file system on device",
                    fstype=storage_unit_fs,
                    device=storage_unit_device,
                    ))
            except CommandException as err1:
                if "appears to contain an existing filesystem" not in err1.err:
                    logging.error(logf(
                        "Failed to create file system",
                        fstype=storage_unit_fs,
                        device=storage_unit_device,
                        error=err1,
                    ))
                    sys.exit(1)
                else:
                    logging.info(logf(
                        "Failed to perform mkfs on device. continuing with mount",
                        err=err1,
                        device=storage_unit_device,
                        mountdir=mountdir,
                    ))
            try:
                execute("mount", storage_unit_device, mountdir)
                logging.info(logf(
                    "Successfully mounted device on path",
                    fstype=storage_unit_fs,
                    device=storage_unit_device,
                    mountdir=mountdir,
                    ))
            except CommandException as err1:
                logging.error(logf(
                    "Failed to mount export brick (after mkfs)",
                    fstype=storage_unit_fs,
                    device=storage_unit_device,
                    mountdir=mountdir,
                    error=err1,
                ))
                sys.exit(1)

        elif 'already mounted' not in err.err:
            logging.error(logf(
                "Failed to mount export storage_unit",
                fstype=storage_unit_fs,
                device=storage_unit_device,
                mountdir=mountdir,
                error=err,
            ))
            sys.exit(1)

        else:
            pass
