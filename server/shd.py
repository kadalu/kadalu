"""
Starts Gluster Brick(fsd) process
"""
import os
import json

from jinja2 import Template


VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"


def generate_shd_volfile(client_volfile, volname, voltype):
    """Generate Client Volfile for Glusterfs Volume"""
    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    template_file_path = os.path.join(TEMPLATES_DIR,
                                      "%s.shd.vol.j2" % voltype)
    content = ""
    with open(template_file_path) as template_file:
        content = template_file.read()

    Template(content).stream(**data).dump(client_volfile)


def start():
    """
    Start the Gluster Self-Heal Process
    """
    volname = os.environ["VOLUME"]
    voltype = os.environ["VOLUME_TYPE"]

    volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")
    generate_shd_volfile(volfile_path, volname, voltype)

    os.execv(
        "/usr/sbin/glusterfs",
        [
            "/usr/sbin/glusterfs",
            "-N",
            "--volfile-id", "gluster/glustershd",
            "-p", "/var/run/gluster/glustershd.pid",
            "-S", "/var/run/gluster/shd.socket",
            "-l", "-",  # Log to stderr
            "--xlator-option",
            "*replicate*.node-uuid=%s" % os.environ["NODEID"],
            "-f", volfile_path
        ]
    )

if __name__ == "__main__":
    start()
