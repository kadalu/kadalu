"""
Starts Gluster Brick(fsd) process
"""
import os
import uuid
import sys
import json
import logging

from jinja2 import Template

from kadalulib import logf


VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"


def generate_shd_volfile(volfile_path, volname):
    """Generate Client Volfile for Glusterfs Volume"""
    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    template_file_path = os.path.join(TEMPLATES_DIR, "Replica3.shd.vol.j2")
    client_volfile = os.path.join(VOLFILES_DIR, "glustershd.vol")
    content = ""
    with open(template_file_path) as template_file:
        content = template_file.read()

    Template(content).stream(**data).dump(client_volfile)


def start():
    """
    Start the Gluster Self-Heal Process
    """
    volname = os.environ["VOLUME"]

    volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")
    generate_shd_volfile(volfile_path, volname)

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
