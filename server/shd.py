"""
Starts Gluster Brick(fsd) process
"""
import os
import json

from jinja2 import Template

from kadalulib import Proc


VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"


def generate_shd_volfile(client_volfile, volname, voltype):
    """Generate Client Volfile for Glusterfs Volume"""
    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    # Tricky to get this right, but this solves all the elements of distribute in code :-)
    data['dht_subvol'] = []
    if data["type"] == "Replica1":
        for brick in data["bricks"]:
            data["dht_subvol"].append("%s-client-%d" % (data["volname"], brick["brick_index"]))
    else:
        count = 3
        if data["type"] == "Replica2":
            count = 2
        for i in range(0, int(len(data["bricks"]) / count)):
            data["dht_subvol"].append("%s-replica-%d" % (data["volname"], i))

    template_file_path = os.path.join(TEMPLATES_DIR,
                                      "%s.shd.vol.j2" % voltype)
    content = ""
    with open(template_file_path) as template_file:
        content = template_file.read()

    Template(content).stream(**data).dump(client_volfile)


def start_args():
    """
    Start the Gluster Self-Heal Process
    """
    volname = os.environ["VOLUME"]
    voltype = os.environ["VOLUME_TYPE"]

    volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")
    generate_shd_volfile(volfile_path, volname, voltype)

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
            "-f", volfile_path
        ]
    )
