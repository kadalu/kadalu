"""
Starts Gluster Brick(fsd) process
"""
import logging
import os
import sys
import uuid
import json

import xattr
from kadalulib import (CommandException, Proc, execute, logf,
                       send_analytics_tracker)

from serverutils import (generate_brick_volfile,
                         generate_client_volfile)

# noqa # pylint: disable=I1101
VOLUME_ID_XATTR_NAME = "trusted.glusterfs.volume-id"
VOLFILES_DIR = "/var/lib/kadalu/volfiles"
VOLINFO_DIR = "/var/lib/gluster"
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


def set_volume_id_xattr(brick_path, volume_id):
    """Set Volume ID xattr"""

    volume_id_bytes = uuid.UUID(volume_id).bytes
    try:
        xattr.set(brick_path, VOLUME_ID_XATTR_NAME,
                  volume_id_bytes, xattr.XATTR_CREATE)
    except FileExistsError:
        pass
    except OSError as err:
        logging.error(logf("Unable to set volume-id on "
                           "brick root",
                           error=err))
        sys.exit(1)


def create_brick_volfile(storage_unit_volfile_path, volname, volume_id, brick_path):
    """
    Create Brick/Storage Unit Volfile based on Volinfo stored in Config map
    For now, Generated Volfile is used in configmap
    """

    storage_unit = {}
    storage_unit["path"] = brick_path
    storage_unit["port"] = 24007
    storage_unit["volume"] = {}
    storage_unit["volume"]["name"] = volname
    storage_unit["volume"]["id"] = volume_id

    generate_brick_volfile(storage_unit, storage_unit_volfile_path)


def create_client_volfile(client_volfile_path, volname):
    """
    Create client volfile based on Volinfo stored in Config map using
    Kadalu Volgen library.
    """

    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    generate_client_volfile(data, client_volfile_path)



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
            except CommandException as err:
                if "appears to contain an existing filesystem" not in err.err:
                    logging.error(logf(
                        "Failed to create file system",
                        fstype=brickfs,
                        device=brick_device,
                        error=err,
                    ))
                    sys.exit(1)
                else:
                    logging.info(logf(
                        "Failed to perform mkfs on device. continuing with mount",
                        err=err,
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
            except CommandException as err:
                logging.error(logf(
                    "Failed to mount export brick (after mkfs)",
                    fstype=brickfs,
                    device=brick_device,
                    mountdir=mountdir,
                    error=err,
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


def start_args():
    """
    Prepare the things required for Brick Start and Returns the Proc
    object required to start Brick Process.
    """

    brick_device = os.environ.get("BRICK_DEVICE", None)
    brick_path = os.environ["BRICK_PATH"]
    if brick_device is not None and brick_device != "":
        brickfs = os.environ.get("BRICK_FS", "xfs")
        create_and_mount_brick(brick_device, brick_path, brickfs)

    volume_id = os.environ["VOLUME_ID"]
    brick_path_name = brick_path.strip("/").replace("/", "-")
    volname = os.environ["VOLUME"]
    nodename = os.environ["HOSTNAME"]

    create_brickdir(brick_path)
    verify_brickdir_xattr_support(brick_path)
    set_volume_id_xattr(brick_path, volume_id)

    volfile_id = "%s.%s.%s" % (volname, nodename, brick_path_name)
    storage_unit_volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volfile_id)
    client_volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volname)
    create_brick_volfile(storage_unit_volfile_path, volname, volume_id, brick_path)
    create_client_volfile(client_volfile_path, volname)

    # UID is stored at the time of installation in configmap.
    uid = None
    with open(os.path.join(VOLINFO_DIR, "uid")) as uid_file:
        uid = uid_file.read()

    # Send Analytics Tracker
    # The information from this analytics is available for
    # developers to understand and build project in a better way
    send_analytics_tracker("server", uid)

    return Proc(
        "glusterfsd",
        "/opt/sbin/glusterfsd",
        [
            "-N",
            "--volfile-id", volfile_id,
            "-p", "/var/run/gluster/glusterfsd-%s.pid" % brick_path_name,
            "-S", "/var/run/gluster/brick.socket",
            "--brick-name", brick_path,
            "-l", "-",  # Log to stderr
            "--xlator-option",
            "*-posix.glusterd-uuid=%s" % os.environ["NODEID"],
            "--process-name", "brick",
            "--brick-port", "24007",
            "--xlator-option",
            "%s-server.listen-port=24007" % volname,
            "-f", storage_unit_volfile_path
        ]
    )
