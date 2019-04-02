"""
Manage Filesystem Quota
"""
import os
import time
import json
import logging

from kadalulib import execute, logf, CommandException, \
    get_volname_hash, get_volume_path, PV_TYPE_SUBVOL


def set_quota(rootdir, subdir_path, quota_value):
    """
    Set Quota for given subdir path. Get project
    ID from directory inode
    """
    ino = os.lstat(subdir_path).st_ino
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
        return out.split(b"\n")
    except CommandException as err:
        logging.error(logf("Failed to get Quota Report",
                           rootdir=rootdir,
                           err=err.err,
                           ret=err.ret))
        return []


def handle_quota(quota_report, brick_path, volname, pvtype):
    """Sets Quota if info file is available"""

    volhash = get_volname_hash(volname)
    volpath = get_volume_path(pvtype, volhash, volname)
    subdir_path = os.path.join(brick_path, volpath)
    projid = b"#%d" % os.lstat(subdir_path).st_ino
    limit_hard = 0
    for line in quota_report:
        if line.startswith(projid):
            limit_hard = int(line.split()[3])
            break

    # Quota is already set, continue
    # TODO: Handle PV resize requests
    if limit_hard > 0:
        return

    pvinfo_file_path = os.path.join(brick_path, "info", volpath + ".json")
    if os.path.exists(pvinfo_file_path):
        data = {}
        with open(pvinfo_file_path) as pvinfo_file:
            data = json.loads(pvinfo_file.read().strip())

            try:
                set_quota(os.path.dirname(brick_path), subdir_path, data["size"])
                logging.info(logf("Quota Set",
                                  path=subdir_path.replace(brick_path, ""),
                                  size=data["size"]))
            except CommandException as err:
                logging.error(logf("Failed to set Quota",
                                   err=err.err,
                                   path=subdir_path.replace(
                                       brick_path, ""),
                                   size=data["size"]))


def crawl():
    """
    Crawl to find if Quota set is pending for any directory.
    Get Quota size information from info file
    """
    brick_path = os.environ["BRICK_PATH"]
    subvol_root = os.path.join(brick_path, PV_TYPE_SUBVOL)

    quota_report = get_quota_report(os.path.dirname(brick_path))
    if not quota_report:
        return

    if not os.path.exists(subvol_root):
        return

    for dir1 in os.listdir(subvol_root):
        for dir2 in os.listdir(os.path.join(subvol_root, dir1)):
            for pvdir in os.listdir(os.path.join(subvol_root, dir1, dir2)):
                handle_quota(quota_report, brick_path, pvdir, PV_TYPE_SUBVOL)


def start():
    """
    Start Quota Manager
    """
    while True:
        crawl()
        time.sleep(1)


if __name__ == "__main__":
    start()
