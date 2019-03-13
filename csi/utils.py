import os
import subprocess
import time
import json

from jinja2 import Template


DRIVER_NAME = "kadalu.gluster"
DRIVER_VERSION = "0.1.0"
glusterfs_cmd = "/usr/sbin/glusterfs"
info_dir = "/var/lib/gluster"
volfiles_dir = "/kadalu-csi/volfiles"
templates_dir = "/kadalu-csi/templates"
reserved_size_percentage = 10
PV_TYPE_VIRTBLOCK = "virtblock"
PV_TYPE_SUBVOL = "subvol"


class CommandException(Exception):
    pass


def get_csi_endpoint():
    return os.environ.get("CSI_ENDPOINT", "unix://plugin/csi.sock")


def execute(*cmd):
    p = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                         stdout=subprocess.PIPE)
    out, err = p.communicate()
    if p.returncode != 0:
        raise CommandException(p.returncode, out.strip(), err.strip())
    return (out.strip(), err.strip())


def generate_client_volfile(volname):
    info_file = os.path.join(info_dir, "%s.info" % volname)
    data = {}
    with open(info_file) as f:
        data = json.load(f)

    template_file = os.path.join(
        templates_dir,
        "%s.client.vol.j2" % data["type"]
    )
    client_volfile = os.path.join(
        volfiles_dir,
        "%s.client.vol" % volname
    )
    content = ""
    with open(template_file) as f:
        content = f.read()

    Template(content).stream(**data).dump(client_volfile)


def mount_glusterfs(volume, target_path):
    os.makedirs(target_path, exist_ok=True)
    # Ignore if already mounted
    if os.path.ismount(target_path):
        return

    generate_client_volfile(volume)
    cmd = [
        glusterfs_cmd,
        "--process-name", "fuse",
        "--volfile-id=%s" % volume,
        target_path,
        "-f", "%s/%s.client.vol" % (volfiles_dir, volume)
    ]
    execute(*cmd)


def get_pv_hosting_volumes():
    volumes = []

    for infofile in os.listdir(info_dir):
        if infofile.endswith(".info"):
            volumes.append(infofile.replace(".info", ""))

    # If volume file is not yet available, ConfigMap may not be ready
    # or synced. Wait for some time and try again
    if len(volumes) == 0:
        time.sleep(2)
        return get_pv_hosting_volumes()

    return volumes


def is_space_available(mount_path, required_size):
    st = os.statvfs(mount_path)
    available_size = st.f_bavail * st.f_bsize
    reserved_size = available_size * reserved_size_percentage/100
    if required_size < (available_size-reserved_size):
        return True

    return False
