"""
Starts Gluster Brick(fsd) process
"""
import json
import os

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
    decommissioned = []
    if data["type"] == "Replica1":
        for brick in data["bricks"]:
            brick_name = "%s-client-%d" % (data["volname"], brick["brick_index"])
            data["dht_subvol"].append(brick_name)
            if brick.get("decommissioned", "") != "":
                decommissioned.append(brick_name)
    else:
        count = 3
        if data["type"] == "Replica2":
            count = 2

        if data["type"] == "Disperse":
            count = data["disperse"]["data"] + data["disperse"]["redundancy"]
            data["disperse_redundancy"] = data["disperse"]["redundancy"]

        data["subvol_bricks_count"] = count
        for i in range(0, int(len(data["bricks"]) / count)):
            brick_name = "%s-%s-%d" % (
                data["volname"],
                "disperse" if data["type"] == "Disperse" else "replica",
                i
            )
            data["dht_subvol"].append(brick_name)
            if data["bricks"][(i * count)].get("decommissioned", "") != "":
                decommissioned.append(brick_name)

    data['decommissioned'] = ",".join(decommissioned)
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
