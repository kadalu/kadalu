import os
import subprocess

DRIVER_NAME = "kadalu.gluster"
DRIVER_VERSION = "0.1.0"
glusterfs_cmd = "/usr/sbin/glusterfs"
volfiles_dir = "/var/lib/gluster"


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


def mount_glusterfs(volume, target_path):
    os.makedirs(target_path, exist_ok=True)
    # Ignore if already mounted
    if os.path.ismount(target_path):
        return

    cmd = [
        glusterfs_cmd,
        "--process-name", "fuse",
        "--volfile-id=%s" % volume,
        target_path,
        "-f", "%s/%s.fuse.vol" % (volfiles_dir, volume)
    ]
    execute(*cmd)
