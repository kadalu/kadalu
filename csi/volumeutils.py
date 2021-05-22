"""
Utility functions for Volume management
"""

import json
import logging
import os
import shutil
import threading
import time
from errno import ENOTCONN

from jinja2 import Template

from kadalulib import (PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK, CommandException,
                       SizeAccounting, execute, get_volname_hash,
                       get_volume_path, is_gluster_mount_proc_running, logf,
                       makedirs, retry_errors)

GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/usr/bin/mount"
UNMOUNT_CMD = "/usr/bin/umount"
MKFS_XFS_CMD = "/usr/sbin/mkfs.xfs"
RESERVED_SIZE_PERCENTAGE = 10
HOSTVOL_MOUNTDIR = "/mnt"
VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
VOLINFO_DIR = "/var/lib/gluster"

# This variable contains in-memory map of all glusterfs processes (hash of volfile and pid)
# Used while sending SIGHUP during any modifcation to storage config
VOL_DATA = {}

statfile_lock = threading.Lock()    # noqa # pylint: disable=invalid-name
mount_lock = threading.Lock()    # noqa # pylint: disable=invalid-name


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


def filter_node_affinity(volume, filters):
    """
    Filter volume based on node affinity provided
    """
    node_name = filters.get("node_affinity", None)
    if node_name is not None:
        # Node affinity is only applicable for Replica1 Volumes
        if volume["type"] != "Replica1":
            return None

        # Volume is not from the requested node
        if node_name != volume["bricks"][0]["kube_hostname"]:
            return None

    return volume


def filter_storage_name(volume, filters):
    """
    filter volume based on the name provided in filter
    """
    storage_name = filters.get("storage_name", None)
    if storage_name is not None and storage_name != volume["volname"]:
        return None

    return volume


def filter_storage_type(volume, filters):
    """
    If Host Volume type is specified then only get the hosting
    volumes which belongs to requested types
    """
    hvoltype = filters.get(
        "storage_type",
        filters.get("hostvol_type", None)
    )
    if hvoltype is not None and hvoltype != volume["type"]:
        return None

    return volume


def filter_supported_pvtype(volume, filters):
    """
    If a storageclass created by specifying supported_pvtype
    then only include those hosting Volumes.
    This is useful when different Volume option needs to be
    set to host virtblock PVs
    """
    f_supported_pvtype = filters.get("supported_pvtype", None)
    supported_pvtype = volume.get("supported_pvtype", "all")
    if supported_pvtype == "all":
        return volume

    if f_supported_pvtype is not None \
       and f_supported_pvtype != supported_pvtype:
        return None

    return volume


# Disabled pylint here because filters argument is used as
# readonly in all functions
# noqa # pylint: disable=dangerous-default-value
def get_pv_hosting_volumes(filters={}, iteration=0):
    """Get list of pv hosting volumes"""
    volumes = []
    total_volumes = 0

    filter_funcs = [
        filter_node_affinity,
        filter_storage_type,
        filter_supported_pvtype
    ]

    for filename in os.listdir(VOLINFO_DIR):
        if filename.endswith(".info"):
            total_volumes += 1
            volname = filename.replace(".info", "")

            filtered = filter_storage_name({"volname": volname}, filters)
            if filtered is None:
                logging.debug(logf(
                    "Volume doesn't match the filter",
                    volname=volname,
                    **filters
                ))
                continue

            data = {}
            with open(os.path.join(VOLINFO_DIR, filename)) as info_file:
                data = json.load(info_file)

            filtered_data = True
            for filter_func in filter_funcs:
                filtered = filter_func(data, filters)
                # Node affinity is not matching for this Volume,
                # Try other volumes
                if filtered is None:
                    filtered_data = False
                    logging.debug(logf(
                        "Volume doesn't match the filter",
                        volname=data["volname"],
                        **filters
                    ))
                    break

            if not filtered_data:
                continue

            volume = {
                "name": volname,
                "type": data["type"],
                "g_volname": data.get("gluster_volname", None),
                "g_host": data.get("gluster_hosts", None),
                "g_options": data.get("gluster_options", None),
                "k_format": data.get("kadalu_format", None),
            }

            volumes.append(volume)

    # Need a different way to get external-kadalu volumes

    # If volume file is not yet available, ConfigMap may not be ready
    # or synced. Wait for some time and try again
    # Lets just give maximum 2 minutes for the config map to come up!
    if total_volumes == 0 and iteration < 40:
        time.sleep(3)
        iteration += 1
        return get_pv_hosting_volumes(filters, iteration)

    return volumes


def update_free_size(hostvol, pvname, sizechange):
    """Update the free size in respective host volume's stats.db file"""

    mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)

    # Check for mount availability before updating the free size
    retry_errors(os.statvfs, [mntdir], [ENOTCONN])

    with statfile_lock:
        with SizeAccounting(hostvol, mntdir) as acc:
            # Reclaim space
            if sizechange > 0:
                acc.remove_pv_record(pvname)
            else:
                acc.update_pv_record(pvname, -sizechange)


def mount_and_select_hosting_volume(pv_hosting_volumes, required_size):
    """Mount each hosting volume to find available space"""
    for volume in pv_hosting_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(volume, mntdir)

        with statfile_lock:
            # Stat done before `os.path.exists` to prevent ignoring
            # file not exists even in case of ENOTCONN
            mntdir_stat = retry_errors(os.statvfs, [mntdir], [ENOTCONN])
            with SizeAccounting(hvol, mntdir) as acc:
                acc.update_summary(mntdir_stat.f_bavail * mntdir_stat.f_bsize)
                pv_stats = acc.get_stats()
                reserved_size = pv_stats["free_size_bytes"] * RESERVED_SIZE_PERCENTAGE/100

            logging.debug(logf(
                "pv stats",
                hostvol=hvol,
                total_size_bytes=pv_stats["total_size_bytes"],
                used_size_bytes=pv_stats["used_size_bytes"],
                free_size_bytes=pv_stats["free_size_bytes"],
                number_of_pvs=pv_stats["number_of_pvs"],
                required_size=required_size,
                reserved_size=reserved_size
            ))

            if required_size < (pv_stats["free_size_bytes"] - reserved_size):
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

    # Check for mount availability before creating virtblock volume
    retry_errors(os.statvfs, [hostvol_mnt], [ENOTCONN])

    # Create a file with required size
    makedirs(os.path.dirname(volpath_full))
    logging.debug(logf(
        "Created virtblock directory",
        path=os.path.dirname(volpath)
    ))

    if os.path.exists(volpath_full):
        rand = time.time()
        logging.info(logf(
            "Getting 'Create request' on existing file, renaming.",
            path=volpath_full, random=rand
        ))
        os.rename(volpath_full, "%s.%s" % (volpath_full, rand))

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
        size=size,
        volpath=volpath,
    )


def save_pv_metadata(hostvol_mnt, pvpath, pvsize):
    """Save PV metadata in info file"""
    # Create info dir if not exists
    info_file_path = os.path.join(hostvol_mnt, "info", pvpath)
    info_file_dir = os.path.dirname(info_file_path)

    retry_errors(makedirs, [info_file_dir], [ENOTCONN])
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

    # Check for mount availability before creating subdir volume
    retry_errors(os.statvfs, [hostvol_mnt], [ENOTCONN])

    # Create a subdir
    makedirs(os.path.join(hostvol_mnt, volpath))
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

    #setfattr -n trusted.glusterfs.namespace -v true
    #setfattr -n trusted.gfs.squota.limit -v size
    try:
        retry_errors(os.setxattr,
                     [os.path.join(hostvol_mnt, volpath),
                      "trusted.glusterfs.namespace",
                      "true".encode()],
                     [ENOTCONN])
        retry_errors(os.setxattr,
                     [os.path.join(hostvol_mnt, volpath),
                      "trusted.gfs.squota.limit",
                      str(size).encode()],
                     [ENOTCONN])
    # noqa # pylint: disable=broad-except
    except Exception as err:
        logging.info(logf(
            "Failed to set quota using simple-quota. Continuing",
            error=err
        ))

    count = 0
    while True:
        count += 1
        pvstat = retry_errors(os.statvfs, [os.path.join(hostvol_mnt, volpath)], [ENOTCONN])
        volsize = pvstat.f_blocks * pvstat.f_bsize
        if pvsize_min < volsize < pvsize_max:
            logging.debug(logf(
                "Matching df output, Quota set successful",
                volsize=volsize,
                num_tries=count
            ))
            break

        if count >= 6:
            logging.warning(logf(
                "Waited for some time, Quota set failed, continuing.",
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
        size=size,
        volpath=volpath,
    )


def is_hosting_volume_free(hostvol, requested_pvsize):
    """Check if host volume is free to expand or create (external)volume"""

    mntdir = os.path.join(HOSTVOL_MOUNTDIR, hostvol)
    with statfile_lock:

        # Stat done before `os.path.exists` to prevent ignoring
        # file not exists even in case of ENOTCONN
        mntdir_stat = retry_errors(os.statvfs, [mntdir], [ENOTCONN])
        with SizeAccounting(hostvol, mntdir) as acc:
            acc.update_summary(mntdir_stat.f_bavail * mntdir_stat.f_bsize)
            pv_stats = acc.get_stats()
            reserved_size = pv_stats["free_size_bytes"] * RESERVED_SIZE_PERCENTAGE/100

        logging.debug(logf(
            "pv stats",
            hostvol=hostvol,
            total_size_bytes=pv_stats["total_size_bytes"],
            used_size_bytes=pv_stats["used_size_bytes"],
            free_size_bytes=pv_stats["free_size_bytes"],
            number_of_pvs=pv_stats["number_of_pvs"],
            required_size=requested_pvsize,
            reserved_size=reserved_size
        ))

        if requested_pvsize < (pv_stats["free_size_bytes"] - reserved_size):
            return True

        return False


def update_subdir_volume(hostvol_mnt, volname, expansion_requested_pvsize):
    """Update sub directory Volume"""

    volhash = get_volname_hash(volname)
    volpath = get_volume_path(PV_TYPE_SUBVOL, volhash, volname)
    logging.debug(logf(
        "Volume hash",
        volhash=volhash
    ))

    # Check for mount availability before updating subdir volume
    retry_errors(os.statvfs, [hostvol_mnt], [ENOTCONN])

    # Create a subdir
    makedirs(os.path.join(hostvol_mnt, volpath))
    logging.debug(logf(
        "Updated PV directory",
        pvdir=volpath
    ))

    # Write info file so that Brick's quotad sidecar
    # container picks it up.
    update_pv_metadata(hostvol_mnt, volpath, expansion_requested_pvsize)

    # Wait for quota set
    # TODO: Handle Timeout
    pvsize_buffer = expansion_requested_pvsize * 0.05  # 5%
    pvsize_min = (expansion_requested_pvsize - pvsize_buffer)
    pvsize_max = (expansion_requested_pvsize + pvsize_buffer)
    logging.debug(logf(
        "Watching df of pv directory",
        pvdir=volpath,
        pvsize_buffer=pvsize_buffer,
    ))

    retry_errors(os.setxattr,
                 [os.path.join(hostvol_mnt, volpath),
                  "trusted.gfs.squota.limit",
                  str(expansion_requested_pvsize).encode()],
                 [ENOTCONN])
    count = 0
    while True:
        count += 1
        pvstat = retry_errors(os.statvfs, [os.path.join(hostvol_mnt, volpath)], [ENOTCONN])
        volsize = pvstat.f_blocks * pvstat.f_bsize
        if pvsize_min < volsize < pvsize_max:
            logging.debug(logf(
                "Matching df output, Quota update set successful",
                volsize=volsize,
                pvsize=expansion_requested_pvsize,
                num_tries=count
            ))
            break

        if count >= 6:
            logging.warning(logf(
                "Waited for some time, Quota update set failed, continuing.",
                volsize=volsize,
                pvsize=expansion_requested_pvsize,
                num_tries=count
            ))
            break

        time.sleep(1)

    return Volume(
        volname=volname,
        voltype=PV_TYPE_SUBVOL,
        volhash=volhash,
        hostvol=os.path.basename(hostvol_mnt),
        size=expansion_requested_pvsize,
        volpath=volpath,
    )


def update_virtblock_volume(hostvol_mnt, volname, expansion_requested_pvsize):
    """Update virtual block volume"""

    volhash = get_volname_hash(volname)
    volpath = get_volume_path(PV_TYPE_VIRTBLOCK, volhash, volname)
    volpath_full = os.path.join(hostvol_mnt, volpath)
    logging.debug(logf(
        "Volume hash",
        volhash=volhash
    ))

    # Check for mount availability before updating virtblock volume
    retry_errors(os.statvfs, [hostvol_mnt], [ENOTCONN])

    # Update the file with required size
    makedirs(os.path.dirname(volpath_full))
    logging.debug(logf(
        "Updated virtblock directory",
        path=os.path.dirname(volpath)
    ))

    volpath_fd = os.open(volpath_full, os.O_CREAT | os.O_RDWR)
    os.close(volpath_fd)

    execute("truncate", "-s", expansion_requested_pvsize, volpath_full)
    logging.debug(logf(
        "Truncated file to required size",
        path=volpath,
        size=expansion_requested_pvsize
    ))

    # TODO: Multiple FS support based on volume_capability mount option
    execute(MKFS_XFS_CMD, volpath_full)
    logging.debug(logf(
        "Created Filesystem",
        path=volpath,
        command=MKFS_XFS_CMD
    ))

    update_pv_metadata(hostvol_mnt, volpath, expansion_requested_pvsize)
    return Volume(
        volname=volname,
        voltype=PV_TYPE_VIRTBLOCK,
        volhash=volhash,
        hostvol=os.path.basename(hostvol_mnt),
        size=expansion_requested_pvsize,
        volpath=volpath,
    )


def update_pv_metadata(hostvol_mnt, pvpath, expansion_requested_pvsize):
    """Update PV metadata in info file"""

    # Create info dir if not exists
    info_file_path = os.path.join(hostvol_mnt, "info", pvpath)
    info_file_dir = os.path.dirname(info_file_path)

    retry_errors(makedirs, [info_file_dir], [ENOTCONN])
    logging.debug(logf(
        "Updated metadata directory",
        metadata_dir=info_file_dir
    ))

    # Update existing PV contents
    with open(info_file_path + ".json", "r") as info_file:
        data = json.load(info_file)

    # Update PV contents
    data["size"] = expansion_requested_pvsize
    data["path_prefix"] = os.path.dirname(pvpath)

    # Save back the changes
    with open(info_file_path + ".json", "w+") as info_file:
        info_file.write(json.dumps(data))

    logging.debug(logf(
        "Metadata updated",
        metadata_file=info_file_path
    ))


def delete_volume(volname):
    """Delete virtual block, sub directory volume, or External"""

    vol = search_volume(volname)
    if vol is None:
        logging.warning(logf(
            "Volume not found for delete",
            volname=volname
        ))
        return False

    logging.debug(logf(
        "Volume found for delete",
        volname=vol.volname,
        voltype=vol.voltype,
        volhash=vol.volhash,
        hostvol=vol.hostvol
    ))

    # Check for mount availability before deleting the volume
    retry_errors(os.statvfs, [os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol)],
                 [ENOTCONN])

    storage_filename = vol.hostvol + ".info"
    with open(os.path.join(VOLINFO_DIR, storage_filename)) as info_file:
        storage_data = json.load(info_file)

    pv_reclaim_policy = storage_data.get("pvReclaimPolicy", "delete")

    volpath = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, vol.volpath)

    if pv_reclaim_policy == "archive":

        old_volname = vol.volname
        vol.volname = "archived-" + vol.volname
        path_prefix = os.path.dirname(vol.volpath)
        vol.volpath = os.path.join(path_prefix, vol.volname)

        # Rename directory & files that are to be archived
        try:

            # Brick/PVC
            os.rename(
                os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, path_prefix, old_volname),
                os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, path_prefix, vol.volname)
            )

            # Info-File
            old_info_file_name = old_volname + ".json"
            info_file_name = vol.volname + ".json"
            os.rename(
                os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, "info",
                             path_prefix, old_info_file_name),
                os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, "info",
                             path_prefix, info_file_name)
            )

            logging.info(logf(
                "Volume archived",
                old_volname=old_volname,
                new_archived_volname=vol.volname,
                volpath=vol.volpath
            ))

        except OSError as err:
            logging.info(logf(
                "Error while archiving volume",
                volname=old_volname,
                volpath=os.path.join(path_prefix, old_volname),
                voltype=vol.voltype,
                error=err,
            ))

        return True

    try:
        if vol.voltype == PV_TYPE_SUBVOL:
            shutil.rmtree(volpath)
        else:
            os.remove(volpath)
    except OSError as err:
        logging.info(logf(
            "Error while deleting volume",
            volpath=volpath,
            voltype=vol.voltype,
            error=err,
        ))

    logging.info(logf(
        "Volume deleted",
        volpath=volpath,
        voltype=vol.voltype
    ))

    # Delete Metadata file
    info_file_path = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol,
                                  "info", vol.volpath+".json")

    try:
        with open(info_file_path) as info_file:
            data = json.load(info_file)
            # We assume there would be a create before delete, but while
            # developing thats not true. There can be a delete request for
            # previously created pvc, which would be assigned to you once
            # you come up. We can't fail then.
            update_free_size(vol.hostvol, volname, data["size"])

        os.remove(info_file_path)
        logging.debug(logf(
            "Removed volume metadata file",
            path="info/" + vol.volpath + ".json",
            hostvol=vol.hostvol
        ))
    except OSError as err:
        logging.info(logf(
            "Error while removing the file",
            path="info/" + vol.volpath + ".json",
            hostvol=vol.hostvol,
            error=err,
        ))

    return True


def search_volume(volname):
    """Search for a Volume by name in all Hosting Volumes"""
    volhash = get_volname_hash(volname)
    subdir_path = get_volume_path(PV_TYPE_SUBVOL, volhash, volname)
    virtblock_path = get_volume_path(PV_TYPE_VIRTBLOCK, volhash, volname)

    host_volumes = get_pv_hosting_volumes({})
    for volume in host_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(volume, mntdir)
        # Check for mount availability before checking the info file
        retry_errors(os.statvfs, [mntdir], [ENOTCONN])

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
    host_volumes = get_pv_hosting_volumes({})
    volumes = []
    for volume in host_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(volume, mntdir)

        # Check for mount availability before listing the Volumes
        retry_errors(os.statvfs, [mntdir], [ENOTCONN])

        if voltype is None or voltype == PV_TYPE_SUBVOL:
            get_subdir_virtblock_vols(mntdir, volumes, PV_TYPE_SUBVOL)
        if voltype is None or voltype == PV_TYPE_VIRTBLOCK:
            get_subdir_virtblock_vols(mntdir, volumes, PV_TYPE_VIRTBLOCK)

    return volumes


def mount_volume(pvpath, mountpoint, pvtype, fstype=None):
    """Mount a Volume"""
    # Need this after kube 1.20.0
    makedirs(mountpoint)

    if pvtype == PV_TYPE_VIRTBLOCK:
        fstype = "xfs" if fstype is None else fstype
        execute(MOUNT_CMD, "-t", fstype, pvpath, mountpoint)
    else:
        execute(MOUNT_CMD, "--bind", pvpath, mountpoint)

    os.chmod(mountpoint, 0o777)


def unmount_glusterfs(mountpoint):
    """Unmount GlusterFS mount"""
    volname = os.path.basename(mountpoint)
    if is_gluster_mount_proc_running(volname, mountpoint):
        execute(UNMOUNT_CMD, "-l", mountpoint)


def unmount_volume(mountpoint):
    """Unmount a Volume"""
    if os.path.ismount(mountpoint):
        execute(UNMOUNT_CMD, "-l", mountpoint)


def expand_volume(mountpoint):
    """Expand a Volume"""
    if os.path.ismount(mountpoint):
        execute("xfs_growfs", "-d", mountpoint)


def generate_client_volfile(volname):
    """Generate Client Volfile for Glusterfs Volume"""
    info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)
    data = {}
    with open(info_file_path) as info_file:
        data = json.load(info_file)

    # If the hash of configmap is same for the given volume, then there
    # is no need to generate client volfile again.
    if not VOL_DATA.get(volname, None):
        VOL_DATA[volname] = {}
    hashval = VOL_DATA[volname].get("hash", 0)
    current_hash = hash(json.dumps(data))

    if hashval == current_hash:
        return False

    VOL_DATA[volname]["hash"] = current_hash

    # Tricky to get this right, but this solves all the elements of distribute in code :-)
    data['dht_subvol'] = []
    if data["type"] == "Replica1":
        for brick in data["bricks"]:
            data["dht_subvol"].append("%s-client-%d" % (data["volname"], brick["brick_index"]))
    else:
        count = 3
        if data["type"] == "Replica2":
            count = 2

        data["subvol_bricks_count"] = count
        if data["type"] == "Disperse":
            data["subvol_bricks_count"] = data["disperse"]["data"] + \
              data["disperse"]["redundancy"]
            data["disperse_redundancy"] = data["disperse"]["redundancy"]

        for i in range(0, int(len(data["bricks"]) / data["subvol_bricks_count"])):
            data["dht_subvol"].append("%s-%s-%d" % (
                data["volname"],
                "disperse" if data["type"] == "Disperse" else "replica",
                i
            ))

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
    return True


def mount_glusterfs(volume, mountpoint, is_client=False):
    """Mount Glusterfs Volume"""
    if volume["type"] == "External":
        volname = volume['g_volname']
    else:
        volname = volume["name"]

    # Ignore if already glusterfs process running for that volume
    if is_gluster_mount_proc_running(volname, mountpoint):
        logging.debug(logf(
            "Already mounted",
            mount=mountpoint
        ))
        return

    # Ignore if already mounted
    if is_gluster_mount_proc_running(volname, mountpoint):
        logging.debug(logf(
            "Already mounted (2nd try)",
            mount=mountpoint
        ))
        return

    if not os.path.exists(mountpoint):
        makedirs(mountpoint)

    if volume['type'] == 'External':
        # Try to mount the Host Volume, handle failure if
        # already mounted
        with mount_lock:
            mount_glusterfs_with_host(volume['g_volname'],
                                      mountpoint,
                                      volume['g_host'],
                                      volume['g_options'],
                                      is_client)
        return

    with mount_lock:
        generate_client_volfile(volume['name'])
        # Fix the log, so we can check it out later
        # log_file = "/var/log/gluster/%s.log" % mountpoint.replace("/", "-")
        log_file = "/var/log/gluster/gluster.log"
        cmd = [
            GLUSTERFS_CMD,
            "--process-name", "fuse",
            "-l", log_file,
            "--volfile-id", volume['name'],
            "--fs-display-name", "kadalu:%s" % volume['name'],
            "-f", "%s/%s.client.vol" % (VOLFILES_DIR, volume['name']),
            mountpoint
        ]

        ## required for 'simple-quota'
        if not is_client:
            cmd.extend(["--client-pid", "-14"])

        try:
            (_, err, pid) = execute(*cmd)
            VOL_DATA[volname]["pid"] = pid
        except CommandException as err:
            logging.error(logf(
                "error to execute command",
                volume=volume,
                cmd=cmd,
                error=format(err)
            ))
            raise err

    return

def reload_glusterfs(volume):
    """Mount Glusterfs Volume"""
    if volume["type"] == "External":
        return False

    volname = volume["name"]

    if not VOL_DATA.get(volname, None):
        return False

    # Ignore if already glusterfs process running for that volume
    with mount_lock:
        if not generate_client_volfile(volname):
            return False
        pid = VOL_DATA[volname]["pid"]
        cmd = ["kill", "-HUP", pid]

        try:
            execute(*cmd)
        except CommandException as err:
            logging.error(logf(
                "error to execute command",
                volume=volume,
                cmd=cmd,
                error=format(err)
            ))
            raise err

    return True


# noqa # pylint: disable=unused-argument
def mount_glusterfs_with_host(volname, mountpoint, hosts, options=None, is_client=False):
    """Mount Glusterfs Volume"""

    # Ignore if already mounted
    if is_gluster_mount_proc_running(volname, mountpoint):
        logging.debug(logf(
            "Already mounted",
            mount=mountpoint
        ))
        return

    if not os.path.exists(mountpoint):
        makedirs(mountpoint)

    # FIXME: make this better later (an issue for external contribution)
    # opt_array = None
    # if options:
    #     opt_array = []
    #     for opt in options.split(","):
    #         if not opt or opt == "":
    #             break
    #         for k,v in opt.split("="):
    #             if k == "log-level":
    #                 opt_array.append("--log-level")
    #                 opt_array.append(v)
    #                 # TODO: handle more options, and document them

    # Fix the log, so we can check it out later
    # log_file = "/var/log/gluster/%s.log" % mountpoint.replace("/", "-")
    log_file = "/var/log/gluster/gluster.log"

    cmd = [
        GLUSTERFS_CMD,
        "--process-name", "fuse",
        "-l", "%s" % log_file,
        "--volfile-id", volname,
    ]
    ## on server component we can mount glusterfs with client-pid
    #if not is_client:
    #    cmd.extend(["--client-pid", "-14"])

    for host in hosts.split(','):
        cmd.extend(["--volfile-server", host])

    cmd.append(mountpoint)

    # if opt_array:
    #     cmd.extend(opt_array)
    #
    # # add mount point after all options
    # cmd.append(mountpoint)
    logging.debug(logf(
        "glusterfs command",
        cmd=cmd
    ))

    try:
        execute(*cmd)
    except CommandException as err:
        logging.info(logf(
            "mount command failed",
            cmd=cmd,
            error=err,
        ))

    return

def check_external_volume(pv_request, host_volumes):
    """Mount hosting volume"""
    # Assumption is, this has to have 'hostvol_type' as External.
    params = {}
    for pkey, pvalue in pv_request.parameters.items():
        params[pkey] = pvalue

    mntdir = None
    hvol = None
    for vol in host_volumes:
        if vol["type"] != "External":
            continue

        # For external volume both k_format, g_volname and hosts should match
        # gluster_hosts is flattened to a string and can be compared as such
        # Assumptions:
        # 1. User will not reuse a gluster non-native volume
        if (vol["k_format"] == params["kadalu_format"]
                and vol["g_volname"] == params["gluster_volname"]
                and vol["g_host"] == params["gluster_hosts"]):
            mntdir = os.path.join(HOSTVOL_MOUNTDIR, vol["name"])
            hvol = vol
            break

    if not mntdir:
        logging.warning("No host volume found to provide PV")
        return None

    mount_glusterfs_with_host(hvol['g_volname'], mntdir, hvol['g_host'], hvol['g_options'])

    time.sleep(0.37)

    if not is_gluster_mount_proc_running(hvol['g_volname'], mntdir):
        logging.debug(logf(
            "Mount failed",
            hvol=hvol,
            mntdir=mntdir
        ))
        return None

    logging.debug(logf(
        "Mount successful",
        hvol=hvol
    ))

    return hvol


def yield_hostvol_mount():
    """Yields mount directory where hostvol is mounted"""
    host_volumes = get_pv_hosting_volumes()
    for volume in host_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        try:
            mount_glusterfs(volume, mntdir)
        except CommandException as excep:
            logging.error(
                logf("Unable to mount volume", hvol=hvol, excep=excep.args))
            return
        logging.info(logf("Volume is mounted successfully", hvol=hvol))
        # After mounting a hostvol, start looking for PVC from '/mntdir/info'
        yield os.path.join(mntdir, 'info')


def yield_pvc_from_mntdir(mntdir):
    """Yields PVCs from a single mntdir"""
    # Max recursion depth is two subdirs (/<mntdir>/x/y/<pvc-hash-.json>)
    # If 'subvol' exist then max depth will be three subdirs
    for child in os.listdir(mntdir):
        name = os.path.join(mntdir, child)
        if os.path.isdir(name):
            yield from yield_pvc_from_mntdir(name)
        elif name.endswith('json'):
            # Base case we are interested in, the filename ending with '.json'
            # is 'PVC' name and contains it's size
            file_path = os.path.join(mntdir, name)
            with open(file_path) as handle:
                data = json.loads(handle.read().strip())
            logging.debug(
                logf("Found a PVC at", path=file_path, size=data.get("size")))
            yield name[name.find("pvc"):name.find(".json")], data.get("size")


def yield_pvc_from_hostvol():
    """Yields a single PVC sequentially from all the hostvolumes"""
    for mntdir in yield_hostvol_mount():
        pvcs = yield_pvc_from_mntdir(mntdir)
        yield from pvcs


def wrap_pvc(pvc_gen):
    """Yields a tuple consisting value from gen and bool for last element"""
    # No need to get num of PVCs existing in Kadalu Storage, query them in real
    # time and yield PVC, True if current entry is the last of the PVC list
    # else yield PVC, False
    gen = pvc_gen()
    try:
        prev = next(gen)
    except StopIteration:
        return
    for value in gen:
        yield prev, False
        prev = value
    yield prev, True


def yield_list_of_pvcs(max_entries=0):
    """Yields list of PVCs limited at 'max_entries'"""
    # List of tuples containing PVC Name and Size
    pvcs = []
    for idx, value in enumerate(wrap_pvc(yield_pvc_from_hostvol)):
        pvc, last = value
        token = "" if last else str(idx)
        pvcs.append(pvc)
        # Main logic is to 'yield' values when one of the below is observed:
        # 1. If max_entries is set and we collected max_entries of PVCs
        # 2. If max_entries is set and we are at last PVC (unaligned total PVCs
        # against max_entries)
        # 3. No max_entries is set (~all) and we are at last PVC yield all
        # pylint: disable=too-many-boolean-expressions
        if (max_entries and len(pvcs) == max_entries) or (
                max_entries and last) or (not max_entries and last):
            # As per spec 'token' has to be string, we are simply using current
            # PVC count as 'token' and validating the same
            next_token = yield
            logging.debug(logf("Received token", next_token=next_token))
            if next_token and not last and (int(next_token) !=
                                            int(token) - max_entries):
                return
            logging.debug(
                logf("Yielding PVC set and next token is ",
                     token=token,
                     pvcs=pvcs))
            yield pvcs, token
            pvcs *= 0
