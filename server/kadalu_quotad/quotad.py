"""
Manage Filesystem Quota
"""
import os
import time
import json
import logging
try:
    from .glusterutils import get_automatic_bricks
except ImportError:
    from glusterutils import get_automatic_bricks

try:
    from .kadalulib import execute, logf, CommandException, \
        get_volname_hash, get_volume_path, PV_TYPE_SUBVOL
except ImportError:
    from kadalulib import execute, logf, CommandException, \
        get_volname_hash, get_volume_path, PV_TYPE_SUBVOL

# Config file for kadalu info
# Config file format:
# {
#    "version": 1,
#    "bricks": [
#      "/data/brick1",
#      "/data/brick2"
#    ]
# }
# We are using a json file, so the same file may get more parameters
# for other tools
#
CONFIG_FILE = "/var/lib/glusterd/kadalu.info"
PROJECT_MOD = 4294967296 # XFS project number is 32bit unsigned
SIZE_LIMITS = {} # Handles quota updates

def set_quota(rootdir, subdir_path, quota_value):
    """
    Set Quota for given subdir path. Get project
    ID from directory inode. XFS can have 64 bit inodes
    so strip it to 32 bit and hope not to clash.
    """
    ino = os.lstat(subdir_path).st_ino % PROJECT_MOD
    execute("xfs_quota",
            "-x", "-c",
            'project -s -p %s %d' % (subdir_path, ino),
            rootdir)

    execute("xfs_quota",
            "-x", "-c",
            'limit -p bhard=%s %d' % (quota_value, ino),
            rootdir)


def get_quota_report(rootdir):
    """Get Project Quota Report"""
    try:
        out, _ = execute(
            "xfs_quota",
            "-x",
            "-c",
            'report -p -b',
            rootdir)
        return out.split("\n")
    except CommandException as err:
        logging.error(logf("Failed to get Quota Report",
                           rootdir=rootdir,
                           err=err.err,
                           ret=err.ret))

    return []


def handle_quota(brick_path, volname, pvtype):
    """Sets Quota if info file is available"""

    volhash = get_volname_hash(volname)
    volpath = get_volume_path(pvtype, volhash, volname)
    subdir_path = os.path.join(brick_path, volpath)

    pvinfo_file_path = os.path.join(brick_path, "info", volpath + ".json")
    if os.path.exists(pvinfo_file_path):
        data = {}
        with open(pvinfo_file_path) as pvinfo_file:
            data = json.loads(pvinfo_file.read().strip())

            # global dictionary to avoid init to None
            global SIZE_LIMITS

            # Add every new entry of volnames
            if volname not in SIZE_LIMITS:
                SIZE_LIMITS[volname] = {}

            # Handle PV resize quota updates

            # Init existing_size to -1 to handle new quota requests
            # Update existing_size for every update requests
            if data["size"] > SIZE_LIMITS[volname].get('existing_size', -1):
                SIZE_LIMITS[volname]['existing_size'] = data["size"]
            # Quota already set for size, return
            else:
                return

            try:
                set_quota(os.path.dirname(brick_path), subdir_path, data["size"])
                logging.info(logf(
                    "Quota set for size",
                    size=data["size"]
                ))
            except CommandException as err:
                logging.error(logf("Failed to set Quota",
                                   err=err.err,
                                   path=subdir_path.replace(
                                       brick_path, ""),
                                   size=data["size"]))
    return


def crawl(brick_path):
    """
    Crawl to find if Quota set is pending for any directory.
    Get Quota size information from info file
    """
    if not brick_path:
        return

    subvol_root = os.path.join(brick_path, PV_TYPE_SUBVOL)

    quota_report = get_quota_report(os.path.dirname(brick_path))
    if not quota_report:
        return

    if not os.path.exists(subvol_root):
        return

    for dir1 in os.listdir(subvol_root):
        for dir2 in os.listdir(os.path.join(subvol_root, dir1)):
            for pvdir in os.listdir(os.path.join(subvol_root, dir1, dir2)):
                handle_quota(brick_path, pvdir, PV_TYPE_SUBVOL)

    return


def start():
    """
    Start Quota Manager
    """
    first_time = True
    automatic_bricks = []
    automatic_pass = 0
    while True:
        brick_path = os.environ.get("BRICK_PATH", None)
        if brick_path is not None:
            if brick_path.lower() == 'auto':
                # Getting the bricks is expensive, do it roughly
                # once a minute
                if automatic_pass % 30 == 0:
                    automatic_bricks = get_automatic_bricks()
                automatic_pass += 1
                for brick in automatic_bricks:
                    crawl(brick)
            else:
                crawl(brick_path)
        try:
            with open(CONFIG_FILE) as conf_file:
                config_data = json.loads(conf_file.read().strip())
                for brick in config_data.get('bricks', None):
                    crawl(brick)
        except json.decoder.JSONDecodeError as jex:
            print("Decoding "+CONFIG_FILE+" failed: "+str(jex))
        except:    # noqa # pylint: disable=bare-except
            # Ignore all other errors
            pass

        time.sleep(2)

        if first_time:
            print("Successfully started quotad process")
            first_time = False

    return 0

if __name__ == "__main__":
    start()
