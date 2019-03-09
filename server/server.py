#!/usr/bin/python3

import os
import uuid
import sys

import xattr

brick_path = os.environ["BRICK_PATH"]
test_xattr_name = "user.testattr"
test_xattr_value = b"testvalue"
volume_id_xattr_name = "trusted.glusterfs.volume-id"
volume_id = os.environ["VOLUME_ID"]
volume_id_bytes = uuid.UUID(volume_id).bytes
brick_path_name = os.environ["BRICK_PATH"].strip("/").replace("/", "-")
volfile_id = "%s.%s.%s" % (
    os.environ["VOLUME"],
    os.environ["HOSTNAME"],
    brick_path_name
)

# Create Brick directory and other directories required
os.makedirs(os.path.join(brick_path, ".glusterfs"),
            mode=0o755,
            exist_ok=True)

# Verify Brick dir supports xattrs
try:
    xattr.set(brick_path, test_xattr_name, test_xattr_value)
    val = xattr.get(brick_path, test_xattr_name)
    if val != test_xattr_value:
        raise Exception("Xattr value mismatch. Actual=%s Expected=%s" % (
            val, test_xattr_value))
except Exception as err:
    sys.stderr.write("Extended attributes are not "
                     "supported: %s\n" % err.message)
    sys.exit(1)

# Set Volume ID xattr
try:
    xattr.set(brick_path, volume_id_xattr_name,
              volume_id_bytes, xattr.XATTR_CREATE)
except FileExistsError:
    pass
except Exception as err:
    sys.stderr.write("Unable to set volume-id on "
                     "brick root: %s\n" % err.message)
    sys.exit(1)

# TODO: Generate Volfile based on Volinfo stored in Config map
# For now, Generated Volfile is used in configmap

# Start glusterfsd process
server_role = os.environ.get("KADALU_SERVER_ROLE", "glusterfsd")

if server_role == "glusterfsd":
    os.execv(
        "/usr/sbin/glusterfsd",
        [
            "/usr/sbin/glusterfsd",
            "-N",
            "--volfile-id", volfile_id,
            "-p", "/var/run/gluster/glusterfsd-%s.pid" % brick_path_name,
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
            "%s-server.listen-port=24007" % os.environ["VOLUME"],
            "-f", "/var/lib/gluster/%s.vol" % brick_path_name
        ]
    )
elif server_role == "glustershd":
    # TODO: Start glustershd process
    pass
