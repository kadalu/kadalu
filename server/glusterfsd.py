"""
Starts Gluster Brick(fsd) process
"""
import os
import uuid
import sys
import json
import logging

from jinja2 import Template
import xattr

from kadalulib import execute, CommandException, logf, send_analytics_tracker


VOLUME_ID_XATTR_NAME = "trusted.glusterfs.volume-id"
VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"


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


def generate_brick_volfile(volfile_path, volname):
    """
    Generate Volfile based on Volinfo stored in Config map
    For now, Generated Volfile is used in configmap
    """
    data = {}
    with open(os.path.join(VOLINFO_DIR, "%s.info" % volname)) as info_file:
        data = json.load(info_file)

    content = ""
    template_file = os.path.join(
        TEMPLATES_DIR,
        "%s.brick%s.vol.j2" % (data["type"], os.environ["BRICK_INDEX"])
    )
    with open(template_file) as tmpl_file:
        content = tmpl_file.read()

    tmpl = Template(content)

    tmpl.stream(**data).dump(volfile_path)


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

    if brickfs == "xfs":
        try:
            execute("mkfs.xfs", brick_device)
        except CommandException as err:
            if b"appears to contain an existing filesystem" not in err.err:
                logging.error(logf(
                    "Failed to create file system",
                    fstype=brickfs,
                    device=brick_device,
                ))
                sys.exit(1)

        mountdir = os.path.dirname(brick_path)
        os.makedirs(mountdir,
                    mode=0o755,
                    exist_ok=True)

        try:
            execute("mount", "-oprjquota", brick_device, mountdir)
        except CommandException as err:
            if b'already mounted' not in err.err:
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

def start():
    """
    Start the Gluster Brick Process
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
    volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volfile_id)
    generate_brick_volfile(volfile_path, volname)

    # UID is stored at the time of installation in configmap.
    uid = None
    with open(os.path.join(VOLINFO_DIR, "uid")) as uid_file:
        uid = uid_file.read()

    # Send Analytics Tracker
    # The information from this analytics is available for
    # developers to understand and build project in a better way
    send_analytics_tracker("server", uid)

    os.execv(
        "/usr/sbin/glusterfsd",
        [
            "/usr/sbin/glusterfsd",
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
            "-f", volfile_path
        ]
    )
