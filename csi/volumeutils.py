"""
Utility functions for Volume management
"""

import os
import json
import time
import logging

from jinja2 import Template

from kadalulib import execute, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK, \
    get_volname_hash, get_volume_path, logf


GLUSTERFS_CMD = "/usr/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"
MKFS_XFS_CMD = "/usr/sbin/mkfs.xfs"
RESERVED_SIZE_PERCENTAGE = 10
HOSTVOL_MOUNTDIR = "/mnt"
GLUSTERFS_CMD = "/usr/sbin/glusterfs"
VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"


class Volume():
    """Hosting Volume object"""
    def __init__(self, volname, voltype, hostvol, **kwargs):
        self.voltype = voltype
        self.volname = volname
        self.volhash = kwargs.get("volhash", None)
        self.hostvol = hostvol
        self.size = kwargs.get("size", None)
        self.volpath = kwargs.get("volpath", None)
        self.setpath()

    def setpath(self):
        """Set Volume path based on hash and volume name"""
        if self.volpath is None:
            self.volpath = get_volume_path(
                self.voltype,
                self.volhash,
                self.volname
            )

    def get(self):
        """Get Volume name"""
        return self.volname


def get_pv_hosting_volumes(filters=None):
    """Get list of pv hosting volumes"""
    volumes = []
    total_volumes = 0

    for filename in os.listdir(VOLINFO_DIR):
        if filename.endswith(".info"):
            total_volumes += 1

            volname = filename.replace(".info", "")

            if filters is not None:
                filter_volname = filters.get("storage_name", None)

                # If specific Hosting Volume name is specified
                if filter_volname is not None and filter_volname != volname:
                    continue

            data = {}
            with open(os.path.join(VOLINFO_DIR, filename)) as info_file:
                data = json.load(info_file)

            # If Host Volume type is specified then only get the hosting
            # volumes which belongs to requested types
            if filters is not None:
                filter_hvoltype = filters.get("storage_type", None)
                if not filter_hvoltype:
                    filter_hvoltype = filters.get("hostvol_type", None)
                if filter_hvoltype is not None and \
                   filter_hvoltype != data["type"]:
                    continue

            # If a storageclass created by specifying supported_pvtype
            # then only include those hosting Volumes.
            # This is useful when different Volume option needs to be
            # set to host virtblock PVs
            if filters is not None:
                filter_supported_pvtype = filters.get("supported_pvtype", None)
                supported_pvtype = data.get("supported_pvtype", "all")
                if filter_supported_pvtype is not None and \
                   supported_pvtype != "all" and \
                   filter_supported_pvtype != supported_pvtype:
                    continue

            volumes.append(volname)

    # If volume file is not yet available, ConfigMap may not be ready
    # or synced. Wait for some time and try again
    if total_volumes == 0:
        time.sleep(2)
        return get_pv_hosting_volumes()

    return volumes


def update_free_size(hostvol, sizechange):
    """Update the free size in respective hosting Volume's stat file"""
    stat_file_path = os.path.join(HOSTVOL_MOUNTDIR, hostvol, ".stat")
    with open(stat_file_path+".tmp", "w") as stat_file_tmp:
        with open(stat_file_path) as stat_file:
            data = json.load(stat_file)
            data["free_size"] += sizechange
            stat_file_tmp.write(json.dumps(data))

    os.rename(stat_file_path+".tmp", stat_file_path)


def mount_and_select_hosting_volume(pv_hosting_volumes, required_size):
    """Mount each hosting volume to find available space"""
    for hvol in pv_hosting_volumes:
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(hvol, mntdir)

        stat_file_path = os.path.join(mntdir, ".stat")
        data = {}
        if not os.path.exists(stat_file_path):
            mntdir_stat = os.statvfs(mntdir)
            data = {
                "size": mntdir_stat.f_bavail * mntdir_stat.f_bsize,
                "free_size": mntdir_stat.f_bavail * mntdir_stat.f_bsize
            }
            with open(stat_file_path, "w") as stat_file:
                stat_file.write(json.dumps(data))
        else:
            with open(stat_file_path) as stat_file:
                data = json.load(stat_file)

        reserved_size = data["free_size"] * RESERVED_SIZE_PERCENTAGE/100
        if required_size < (data["free_size"] - reserved_size):
            return hvol

    return None


def create_virtblock_volume(hostvol_mnt, volname, size):
    """Create virtual block volume"""
    volhash = get_volname_hash(volname)
    volpath = get_volume_path(PV_TYPE_VIRTBLOCK, volhash, volname)
    volpath_full = os.path.join(hostvol_mnt, volpath)
    logging.debug(logf(
        "Volume hash",
        volhash=volhash
    ))

    # Create a file with required size
    os.makedirs(os.path.dirname(volpath_full), exist_ok=True)
    logging.debug(logf(
        "Created virtblock directory",
        path=os.path.dirname(volpath)
    ))

    volpath_fd = os.open(volpath_full, os.O_CREAT | os.O_RDWR)
    os.close(volpath_fd)
    os.truncate(volpath_full, size)
    logging.debug(logf(
        "Truncated file to required size",
        path=volpath,
        size=size
    ))

    # TODO: Multiple FS support based on volume_capability mount option
    execute(MKFS_XFS_CMD, volpath_full)
    logging.debug(logf(
        "Created Filesystem",
        path=volpath,
        command=MKFS_XFS_CMD
    ))
    save_pv_metadata(hostvol_mnt, volpath, size)
    return Volume(
        volname=volname,
        voltype=PV_TYPE_VIRTBLOCK,
        volhash=volhash,
        hostvol=os.path.basename(hostvol_mnt),
        size=size
    )


def save_pv_metadata(hostvol_mnt, pvpath, pvsize):
    """Save PV metadata in info file"""
    # Create info dir if not exists
    info_file_path = os.path.join(hostvol_mnt, "info", pvpath)
    info_file_dir = os.path.dirname(info_file_path)

    os.makedirs(info_file_dir, exist_ok=True)
    logging.debug(logf(
        "Created metadata directory",
        metadata_dir=info_file_dir
    ))

    with open(info_file_path + ".json", "w") as info_file:
        info_file.write(json.dumps({
            "size": pvsize,
            "path_prefix": os.path.dirname(pvpath)
        }))
        logging.debug(logf(
            "Metadata saved",
            metadata_file=info_file_path,
        ))


def create_subdir_volume(hostvol_mnt, volname, size):
    """Create sub directory Volume"""
    volhash = get_volname_hash(volname)
    volpath = get_volume_path(PV_TYPE_SUBVOL, volhash, volname)
    logging.debug(logf(
        "Volume hash",
        volhash=volhash
    ))

    # Create a subdir
    os.makedirs(os.path.join(hostvol_mnt, volpath), exist_ok=True)
    logging.debug(logf(
        "Created PV directory",
        pvdir=volpath
    ))

    # Write info file so that Brick's quotad sidecar
    # container picks it up.
    save_pv_metadata(hostvol_mnt, volpath, size)

    # Wait for quota set
    # TODO: Handle Timeout
    pvsize_buffer = size * 0.05  # 5%
    pvsize_min = (size - pvsize_buffer)
    pvsize_max = (size + pvsize_buffer)
    logging.debug(logf(
        "Watching df of pv directory",
        pvdir=volpath,
        pvsize_buffer=pvsize_buffer,
    ))

    count = 0
    while True:
        count += 1
        pvstat = os.statvfs(os.path.join(hostvol_mnt, volpath))
        volsize = pvstat.f_blocks * pvstat.f_bsize
        if pvsize_min < volsize < pvsize_max:
            logging.debug(logf(
                "Matching df output, Quota set successful",
                volsize=volsize,
                num_tries=count
            ))
            break

        time.sleep(1)

    return Volume(
        volname=volname,
        voltype=PV_TYPE_SUBVOL,
        volhash=volhash,
        hostvol=os.path.basename(hostvol_mnt),
        size=size
    )


def delete_volume(volname):
    """Delete virtual block or sub directory volume"""
    vol = search_volume(volname)
    if vol is not None:
        logging.debug(logf(
            "Volume found for delete",
            volname=vol.volname,
            voltype=vol.voltype,
            volhash=vol.volhash,
            hostvol=vol.hostvol
        ))
        volpath = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, vol.volpath)
        if vol.voltype == PV_TYPE_SUBVOL:
            os.removedirs(volpath)
        else:
            os.remove(volpath)

        logging.debug(logf(
            "Volume deleted",
            volpath=volpath,
            voltype=vol.voltype
        ))

        # Delete Metadata file
        info_file_path = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol,
                                      "info", vol.volpath+".json")
        stat_file_path = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, ".stat")
        with open(info_file_path) as info_file:
            data = json.load(info_file)
            # TODO: Hold lock on ".stat" file below
            with open(stat_file_path) as stat_file:
                stat_data = json.load(stat_file)
                stat_data["free_size"] += data["size"]
                with open(stat_file_path+".tmp", "w") as stat_file_tmp:
                    stat_file_tmp.write(json.dumps(stat_data))

                logging.debug(logf(
                    "Updated .stat.tmp file",
                    hostvol=vol.hostvol,
                    before=stat_data["free_size"]-data["size"],
                    after=stat_data["free_size"]
                ))
        os.rename(stat_file_path+".tmp", stat_file_path)
        logging.debug(logf(
            "Renamed .stat.tmp to .stat file",
            hostvol=vol.hostvol
        ))
        os.remove(info_file_path)
        logging.debug(logf(
            "Removed volume metadata file",
            path="info/" + vol.volpath + ".json",
            hostvol=vol.hostvol
        ))


def search_volume(volname):
    """Search for a Volume by name in all Hosting Volumes"""
    volhash = get_volname_hash(volname)
    subdir_path = get_volume_path(PV_TYPE_SUBVOL, volhash, volname)
    virtblock_path = get_volume_path(PV_TYPE_VIRTBLOCK, volhash, volname)

    host_volumes = get_pv_hosting_volumes()
    for hvol in host_volumes:
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        # Try to mount the Host Volume, handle failure if already mounted
        mount_glusterfs(hvol, mntdir)
        for info_path in [subdir_path, virtblock_path]:
            info_path_full = os.path.join(mntdir, "info", info_path + ".json")
            voltype = PV_TYPE_SUBVOL if "/%s/" % PV_TYPE_SUBVOL \
                in info_path_full else PV_TYPE_VIRTBLOCK

            if os.path.exists(info_path_full):
                data = {}
                with open(info_path_full) as info_file:
                    data = json.load(info_file)

                return Volume(
                    volname=volname,
                    voltype=voltype,
                    volhash=volhash,
                    hostvol=hvol,
                    size=data["size"]
                )
    return None


def get_subdir_virtblock_vols(mntdir, volumes, pvtype):
    """Get virtual block and subdir volumes list"""
    for dir1 in os.listdir(os.path.join(mntdir, pvtype)):
        for dir2 in os.listdir(os.path.join(mntdir, pvtype, dir1)):
            for pvdir in os.listdir(os.path.join(mntdir, pvtype, dir2)):
                volumes.append(Volume(
                    volname=pvdir,
                    voltype=pvtype,
                    hostvol=os.path.basename(mntdir),
                    volpath=os.path.join(pvtype, dir1, dir2, pvdir)
                ))


def volume_list(voltype=None):
    """List of Volumes"""
    host_volumes = get_pv_hosting_volumes()
    volumes = []
    for hvol in host_volumes:
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(hvol, mntdir)
        if voltype is None or voltype == PV_TYPE_SUBVOL:
            get_subdir_virtblock_vols(mntdir, volumes, PV_TYPE_SUBVOL)
        if voltype is None or voltype == PV_TYPE_VIRTBLOCK:
            get_subdir_virtblock_vols(mntdir, volumes, PV_TYPE_VIRTBLOCK)

    return volumes


def mount_volume(pvpath, target_path, pvtype, fstype=None):
    """Mount a Volume"""
    if pvtype == PV_TYPE_VIRTBLOCK:
        fstype = "xfs" if fstype is None else fstype
        execute(MOUNT_CMD, "-t", fstype, pvpath, target_path)
    else:
        execute(MOUNT_CMD, "--bind", pvpath, target_path)


def unmount_volume(target_path):
    """Unmount a Volume"""
    if os.path.ismount(target_path):
        execute(UNMOUNT_CMD, target_path)


def generate_client_volfile(volname):
    """Generate Client Volfile for Glusterfs Volume"""
    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    template_file_path = os.path.join(
        TEMPLATES_DIR,
        "%s.client.vol.j2" % data["type"]
    )
    client_volfile = os.path.join(
        VOLFILES_DIR,
        "%s.client.vol" % volname
    )
    content = ""
    with open(template_file_path) as template_file:
        content = template_file.read()

    Template(content).stream(**data).dump(client_volfile)


def mount_glusterfs(volume, target_path):
    """Mount Glusterfs Volume"""
    if not os.path.exists(target_path):
        os.makedirs(target_path, exist_ok=True)

    # Ignore if already mounted
    if os.path.ismount(target_path):
        return

    generate_client_volfile(volume)
    cmd = [
        GLUSTERFS_CMD,
        "--process-name", "fuse",
        "-l", "/dev/stdout",
        "--volfile-id=%s" % volume,
        target_path,
        "-f", "%s/%s.client.vol" % (VOLFILES_DIR, volume)
    ]
    execute(*cmd)
