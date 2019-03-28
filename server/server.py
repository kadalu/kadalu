#!/usr/bin/python3

"""
Prepares, Validates and then starts the Server process(glusterfsd, shd)
"""

import os
import uuid
import sys
import json

from jinja2 import Template
import xattr


BRICK_PATH = os.environ["BRICK_PATH"]
TEST_XATTR_NAME = "user.testattr"
TEST_XATTR_VALUE = b"testvalue"
VOLUME_ID_XATTR_NAME = "trusted.glusterfs.volume-id"
VOLUME_ID = os.environ["VOLUME_ID"]
VOLUME_ID_BYTES = uuid.UUID(VOLUME_ID).bytes
BRICK_PATH_NAME = os.environ["BRICK_PATH"].strip("/").replace("/", "-")
VOLNAME = os.environ["VOLUME"]
NODENAME = os.environ["HOSTNAME"]
VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
INFO_DIR = "/var/lib/gluster"
SERVER_ROLE = os.environ.get("KADALU_SERVER_ROLE", "glusterfsd")


def create_brickdir():
    """Create Brick directory and other directories required"""
    os.makedirs(os.path.join(BRICK_PATH, ".glusterfs"),
                mode=0o755,
                exist_ok=True)


def verify_brickdir_xattr_support():
    """Verify Brick dir supports xattrs"""
    try:
        xattr.set(BRICK_PATH, TEST_XATTR_NAME, TEST_XATTR_VALUE)
        val = xattr.get(BRICK_PATH, TEST_XATTR_NAME)
        if val != TEST_XATTR_VALUE:
            sys.stderr.write(
                "Xattr value mismatch. Actual=%s Expected=%s\n" % (
                    val, TEST_XATTR_VALUE))
            sys.exit(1)
    except OSError as err:
        sys.stderr.write("Extended attributes are not "
                         "supported: %s\n" % err)
        sys.exit(1)


def set_volume_id_xattr():
    """Set Volume ID xattr"""
    try:
        xattr.set(BRICK_PATH, VOLUME_ID_XATTR_NAME,
                  VOLUME_ID_BYTES, xattr.XATTR_CREATE)
    except FileExistsError:
        pass
    except OSError as err:
        sys.stderr.write("Unable to set volume-id on "
                         "brick root: %s\n" % err)
        sys.exit(1)


def generate_brick_volfile(volfile_path):
    """
    Generate Volfile based on Volinfo stored in Config map
    For now, Generated Volfile is used in configmap
    """
    data = {}
    with open(os.path.join(INFO_DIR, "%s.info" % VOLNAME)) as info_file:
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


def start_server_process():
    """
    Start glusterfsd or glustershd process
    """
    if SERVER_ROLE == "glusterfsd":
        create_brickdir()
        verify_brickdir_xattr_support()
        set_volume_id_xattr()

        volfile_id = "%s.%s.%s" % (VOLNAME, NODENAME, BRICK_PATH_NAME)
        volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volfile_id)
        generate_brick_volfile(volfile_path)

        os.execv(
            "/usr/sbin/glusterfsd",
            [
                "/usr/sbin/glusterfsd",
                "-N",
                "--volfile-id", volfile_id,
                "-p", "/var/run/gluster/glusterfsd-%s.pid" % BRICK_PATH_NAME,
                # TODO: Change socket file name
                "-S", "/var/run/gluster/b99981c29a4c396c.socket",
                "--brick-name", os.environ["BRICK_PATH"],
                "-l", "-",  # Log to stderr
                # TODO: Change Node ID
                "--xlator-option",
                "*-posix.glusterd-uuid=6958dddc-1842-4ee0-92df-b6a060dfba5e",
                "--process-name", "brick",
                "--brick-port", "24007",
                "--xlator-option",
                "%s-server.listen-port=24007" % VOLNAME,
                "-f", volfile_path
            ]
        )
    elif SERVER_ROLE == "glustershd":
        # TODO: Start glustershd process
        pass


if __name__ == "__main__":
    start_server_process()
