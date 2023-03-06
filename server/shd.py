"""
Starts Gluster Brick Self Heal Daemon(shd) process
"""
import json
import os

from kadalulib import Proc
from serverutils import generate_shd_volfile

VOLFILES_DIR = "/var/lib/kadalu/volfiles"
VOLINFO_DIR = "/var/lib/gluster"


def create_shd_volfile(shd_volfile_path, volname):
    """
    Generate Self Heal Daemon(SHD) Volfile for Glusterfs
    Volume of type Replica2.
    """

    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    generate_shd_volfile(data, shd_volfile_path)


def start_args():
    """
    Start the Gluster Self-Heal Process
    """
    volname = os.environ["VOLUME"]

    shd_volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")
    create_shd_volfile(shd_volfile_path, volname)

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
