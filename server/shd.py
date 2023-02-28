"""
Starts Gluster Brick Self Heal Daemon(shd) process
"""
import json
import os

from jinja2 import Template
from kadalulib import Proc

from serverutils import generate_shd_volfile

VOLFILES_DIR = "/kadalu/volfiles"
VOLINFO_DIR = "/var/lib/gluster"


def create_shd_volfile(shd_volfile_path, volname, voltype):
    """
    Generate Self Heal Daemon(SHD) Volfile for Glusterfs
    Volume of type Replica2.
    """

    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    content = generate_shd_volfile(data)
    with open(shd_volfile_path, "w") as shd_volfile:
        shd_volfile.write(content)


def start_args():
    """
    Start the Gluster Self-Heal Process
    """
    volname = os.environ["VOLUME"]
    voltype = os.environ["VOLUME_TYPE"]

    shd_volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")
    create_shd_volfile(shd_volfile_path, volname, voltype)

    return Proc(
        "shd",
        "/opt/sbin/glusterfs",
        [
            "-N",
            "--volfile-id", "gluster/glustershd",
            "-p", "/var/run/gluster/glustershd.pid",
            "-S", "/var/run/gluster/shd.socket",
            "-l", "-",  # Log to stderr
            "--xlator-option",
            "*replicate*.node-uuid=%s" % os.environ["NODEID"],
            "--fs-display-name", "kadalu:%s" % volname,
            "-f", shd_volfile_path
        ]
    )
