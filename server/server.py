#!/usr/bin/python3

import os
import uuid
import sys
import json

import xattr
from jinja2 import Template


brick_path = os.environ["BRICK_PATH"]
test_xattr_name = "user.testattr"
test_xattr_value = b"testvalue"
volume_id_xattr_name = "trusted.glusterfs.volume-id"
volume_id = os.environ["VOLUME_ID"]
volume_id_bytes = uuid.UUID(volume_id).bytes
brick_path_name = os.environ["BRICK_PATH"].strip("/").replace("/", "-")
volname = os.environ["VOLUME"]
nodename = os.environ["HOSTNAME"]
volfiles_dir = "/kadalu/volfiles"
templates_dir = "/kadalu/templates"
info_dir = "/var/lib/gluster"


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
data = {}
with open(os.path.join(info_dir, "%s.info" % volname)) as f:
    data = json.load(f)

content = ""
template_file = os.path.join(
    templates_dir,
    "%s.brick%s.vol.j2" % (data["type"], os.environ["BRICK_INDEX"])
)
with open(template_file) as f:
    content = f.read()

tmpl = Template(content)

volfile_id = "%s.%s.%s" % (volname, nodename, brick_path_name)
volfile_path = os.path.join(volfiles_dir, "%s.vol" % volfile_id)
tmpl.stream(**data).dump(volfile_path)


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
            "%s-server.listen-port=24007" % volname,
            "-f", volfile_path
        ]
    )
elif server_role == "glustershd":
    # TODO: Start glustershd process
    pass
