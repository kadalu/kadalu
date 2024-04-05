"""
Utility functions for Volume management
"""

import json
import logging
import os
import re
import shutil
import threading
import time
from errno import ENOTCONN
from pathlib import Path

from kadalulib import (PV_TYPE_RAWBLOCK, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK,
                       CommandException, SizeAccounting, execute,
                       get_volname_hash, get_volume_path,
                       is_gluster_mount_proc_running, logf, makedirs,
                       reachable_host, retry_errors, get_single_pv_per_pool,
                       is_server_pod_reachable)

GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/bin/mount"
UNMOUNT_CMD = "/bin/umount"
MKFS_XFS_CMD = "/sbin/mkfs.xfs"
XFS_GROWFS_CMD = "/sbin/xfs_growfs"
RESERVED_SIZE_PERCENTAGE = 10
HOSTVOL_MOUNTDIR = "/mnt"
VOLFILES_DIR = "/kadalu/volfiles"
VOLINFO_DIR = "/var/lib/gluster"

statfile_lock = threading.Lock()    # noqa # pylint: disable=invalid-name
mount_lock = threading.Lock()    # noqa # pylint: disable=invalid-name


class Volume():
    """Hosting Volume object"""
    # noqa # pylint: disable=too-many-instance-attributes
    def __init__(self, volname, voltype, hostvol, **kwargs):
        self.voltype = voltype
        self.volname = volname
        self.volhash = kwargs.get("volhash", None)
        self.volpath = kwargs.get("volpath", None)
        self.hostvol = hostvol
        self.single_pv_per_pool = False
        self.size = kwargs.get("size", None)
        self.extra = {}
        self.extra['ghost'] = kwargs.get("ghost", None)
        self.extra['hostvoltype'] = kwargs.get("hostvoltype", None)
        self.extra['gvolname'] = kwargs.get("gvolname", None)
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
def get_pv_hosting_volumes(filters={}, iteration=40):
    """Get list of pv hosting volumes"""
    volumes = []
    total_volumes = 0

    filter_funcs = [
        filter_node_affinity, filter_storage_type, filter_supported_pvtype
    ]

    for filename in os.listdir(VOLINFO_DIR):
        if filename.endswith(".info"):
            total_volumes += 1
            volname = filename.replace(".info", "")

            filtered = filter_storage_name({"volname": volname}, filters)
            if filtered is None:
                logging.debug(
                    logf("Volume doesn't match the filter",
                         volname=volname,
                         **filters))
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
                    logging.debug(
                        logf("Volume doesn't match the filter",
                             volname=data["volname"],
                             **filters))
                    break

            if not filtered_data:
                continue

            volume = {
                "name": volname,
                "type": data["type"],
                "g_volname": data.get("gluster_volname", None),
                "g_host": data.get("gluster_hosts", None),
                "g_options": data.get("gluster_options", ""),
                "single_pv_per_pool": get_single_pv_per_pool(data)
            }

            volumes.append(volume)

    # Need a different way to get external-kadalu volumes

    # If volume file is not yet available, ConfigMap may not be ready
    # or synced. Wait for some time and try again
    # Lets just give maximum 2 minutes for the config map to come up!
    if total_volumes == 0 and iteration > 0:
        time.sleep(3)
        iteration -= 1
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
                acc.update_summary(mntdir_stat.f_blocks * mntdir_stat.f_bsize)
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


def create_block_volume(pvtype, hostvol_mnt, volname, size):
    """Create virtual block volume"""
    volhash = get_volname_hash(volname)
    volpath = get_volume_path(pvtype, volhash, volname)
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
        f"Created {pvtype} directory",
        path=os.path.dirname(volpath)
    ))

    # at times orchestrator will send same request if earlier request times
    # out and truncate file if doesn't exist since if we reach here the request
    # is a valid one
    if not os.path.exists(volpath_full):
        volpath_fd = os.open(volpath_full, os.O_CREAT | os.O_RDWR)
        os.close(volpath_fd)
        os.truncate(volpath_full, size)
        logging.debug(logf(
            "Truncated file to required size",
            path=volpath,
            size=size
        ))

        if pvtype == PV_TYPE_VIRTBLOCK:
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
        voltype=pvtype,
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


def create_subdir_volume(hostvol_mnt, volname, size, use_gluster_quota):
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
    # container picks it up (or) for external quota expansion
    save_pv_metadata(hostvol_mnt, volpath, size)

    if use_gluster_quota is True:
        return Volume(
            volname=volname,
            voltype=PV_TYPE_SUBVOL,
            volhash=volhash,
            hostvol=os.path.basename(hostvol_mnt),
            size=size,
            volpath=volpath,
        )

    # Wait for quota set
    # TODO: Handle Timeout
    pvsize_buffer = size * 0.05  # 5%
    pvsize_min = size - pvsize_buffer
    pvsize_max = size + pvsize_buffer
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
            acc.update_summary(mntdir_stat.f_blocks * mntdir_stat.f_bsize)
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


def update_subdir_volume(hostvol_mnt, hostvoltype, volname, expansion_requested_pvsize):
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
    pvsize_min = expansion_requested_pvsize - pvsize_buffer
    pvsize_max = expansion_requested_pvsize + pvsize_buffer
    logging.debug(logf(
        "Watching df of pv directory",
        pvdir=volpath,
        pvsize_buffer=pvsize_buffer,
    ))

    # Handle this case in calling function
    if hostvoltype == 'External':
        return None

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


def update_block_volume(pvtype, hostvol_mnt, volname, expansion_requested_pvsize):
    """Update block volume"""

    volhash = get_volname_hash(volname)
    volpath = get_volume_path(pvtype, volhash, volname)
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
    os.truncate(volpath_full, expansion_requested_pvsize)

    logging.debug(logf(
        "Truncated file to required size",
        path=volpath,
        size=expansion_requested_pvsize
    ))

    update_pv_metadata(hostvol_mnt, volpath, expansion_requested_pvsize)
    return Volume(
        volname=volname,
        voltype=pvtype,
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


# pylint: disable=too-many-locals,too-many-statements
def delete_volume(volname):
    """Delete virtual/raw block, sub directory volume, or External"""

    vol = search_volume(volname)
    if vol is None:
        logging.warning(logf(
            "Volume not found for delete",
            volname=volname
        ))
        return

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

    # Stop the delete operation if the reclaim policy is set to "retain"
    if pv_reclaim_policy == "retain":
        logging.info(logf(
            "'retain' reclaim policy, volume not deleted",
            volpath=volpath,
            voltype=vol.voltype
        ))
        return

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

        return

    # make sure last arg to join is an emtpy string so we get '/' appended to path
    hash_start = len(os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, vol.voltype, ''))
    end = len(volpath)

    try:
        if vol.voltype == PV_TYPE_SUBVOL:
            shutil.rmtree(volpath)
        else:
            os.remove(volpath)

        parent = os.path.dirname(volpath)
        # base case, delete upto but not including voltype dir
        while end > hash_start:
            os.rmdir(parent)
            parent = os.path.dirname(parent)
            end = len(parent)

    except (OSError, FileNotFoundError) as err:
        # neither rmtree nor remove raises OSError with reason 'empty dir'
        # however rmdir if dir isn't empty raises 'empty dir' and in current
        # scenario it's be raised only once in 16^4 cases ;)
        if err.args[1].find("not empty") != -1:
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
                                  "info", f"{vol.volpath}.json")

    hash_start = len(os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, "info", vol.voltype, ''))
    end = len(info_file_path)

    try:
        with open(info_file_path) as info_file:
            data = json.load(info_file)
            # We assume there would be a create before delete, but while
            # developing thats not true. There can be a delete request for
            # previously created pvc, which would be assigned to you once
            # you come up. We can't fail then.
            update_free_size(vol.hostvol, volname, data["size"])

        os.remove(info_file_path)
        parent = os.path.dirname(info_file_path)

        # base case, delete upto but not including voltype dir
        while end > hash_start:
            os.rmdir(parent)
            parent = os.path.dirname(parent)
            end = len(parent)

    except OSError as err:
        if err.args[1].find("not empty") != -1:
            logging.info(logf(
                "Error while removing the file",
                path=f"info/{vol.volpath}.json",
                hostvol=vol.hostvol,
                error=err,
            ))

    logging.debug(logf(
        "Removed volume metadata file",
        path=f"info/{vol.volpath}.json",
        hostvol=vol.hostvol
    ))

    return


def search_volume(volname):
    """Search for a Volume by name in all Hosting Volumes"""
    volhash = get_volname_hash(volname)
    subdir_path = get_volume_path(PV_TYPE_SUBVOL, volhash, volname)
    virtblock_path = get_volume_path(PV_TYPE_VIRTBLOCK, volhash, volname)
    rawblock_path = get_volume_path(PV_TYPE_RAWBLOCK, volhash, volname)

    host_volumes = get_pv_hosting_volumes({})
    for volume in host_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        mount_glusterfs(volume, mntdir)
        # Check for mount availability before checking the info file
        retry_errors(os.statvfs, [mntdir], [ENOTCONN])

        for info_path in [subdir_path, virtblock_path, rawblock_path]:
            info_path_full = os.path.join(mntdir, "info", info_path + ".json")

            if os.path.exists(info_path_full):
                data = {}
                with open(info_path_full) as info_file:
                    data = json.load(info_file)

                voltype = PV_TYPE_SUBVOL
                if info_path_full.find(PV_TYPE_VIRTBLOCK) != -1:
                    voltype = PV_TYPE_VIRTBLOCK
                elif info_path_full.find(PV_TYPE_RAWBLOCK) != -1:
                    voltype = PV_TYPE_RAWBLOCK

                return Volume(
                    volname=volname,
                    voltype=voltype,
                    volhash=volhash,
                    hostvol=hvol,
                    size=data["size"],
                    volpath=info_path,
                    single_pv_per_pool=get_single_pv_per_pool(data),
                    hostvoltype=volume.get('type', None),
                    ghost=volume.get('g_host', None),
                    gvolname=volume.get('g_volname', None),
                )
    return None


# TODO: Not being used, revisit and remove
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


# TODO: Not being used, revisit and remove
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
        if voltype is None or voltype == PV_TYPE_RAWBLOCK:
            get_subdir_virtblock_vols(mntdir, volumes, PV_TYPE_RAWBLOCK)

    return volumes


def mount_volume(pvpath, mountpoint, pvtype, fstype=None):
    """Mount a Volume"""

    # Create subvol dir if PV is manually created
    if not os.path.exists(pvpath):
        makedirs(pvpath)

    # TODO: Will losetup survive container reboot?
    if pvtype == PV_TYPE_RAWBLOCK:
        # losetup of truncated file
        cmd = ["losetup", "-f", "--show", pvpath]
        try:
            loop, _, _ = execute(*cmd)
        except CommandException as err:
            # Better not to create loop devices manually
            errmsg = "Please check availability of 'losetup' and 'loop' device"
            logging.error(logf(errmsg, cmd=cmd, error=format(err)))
            return False

        # Bind mount loop device to target_path, stage_path may not be needed
        makedirs(os.path.dirname(mountpoint))
        Path(mountpoint).touch(mode=0o777)
        execute(MOUNT_CMD, "--bind", loop, mountpoint)
        return True

    # Need this after kube 1.20.0
    makedirs(mountpoint)

    if pvtype == PV_TYPE_VIRTBLOCK:
        fstype = "xfs" if fstype is None else fstype
        execute(MOUNT_CMD, "-t", fstype, pvpath, mountpoint)
    else:
        execute(MOUNT_CMD, "--bind", pvpath, mountpoint)

    os.chmod(mountpoint, 0o777)
    return True


def unmount_glusterfs(mountpoint):
    """Unmount GlusterFS mount"""
    volname = os.path.basename(mountpoint)
    if is_gluster_mount_proc_running(volname, mountpoint):
        execute(UNMOUNT_CMD, "-l", mountpoint)


def unmount_volume(mountpoint):
    """Unmount a Volume"""
    if mountpoint.find("volumeDevices") != -1:
        # Should remove loop device as well or else duplicate loop devices will
        # be setup everytime
        if os.path.exists(mountpoint):
            cmd = ["findmnt", "-T", mountpoint, "-oSOURCE", "-n"]
            device, _, _ = execute(*cmd)
            if match := re.search(r'loop\d+', device):
                loop = match.group(0)
                cmd = ["losetup", "-d", f"/dev/{loop}"]
                execute(*cmd)

    if os.path.ismount(mountpoint):
        execute(UNMOUNT_CMD, "-l", mountpoint)


def expand_mounted_volume(mountpoint):
    """Expand a Volume"""
    if os.path.ismount(mountpoint):
        execute("xfs_growfs", "-d", mountpoint)


def mount_glusterfs(volume, mountpoint, is_client=False):
    """Mount Glusterfs Volume"""

    data = {}
    hosts = []
    volname = volume["name"]

    if volume['type'] == 'External':
        return handle_external_volume(volume, mountpoint, is_client, volume['g_host'])

    with open(os.path.join(VOLINFO_DIR, "%s.info" % volname)) as info_file:
        data = json.load(info_file)
    for brick in data["bricks"]:
        hosts.append(brick["node"])

    try:
        if not is_server_pod_reachable(hosts, 24007, 20):
            err = "Cannot establish socket connection with none of the hosts!"
            cmd = "sock.connect(hosts, 24007)"
            raise CommandException(-1, cmd, err)
    except CommandException:
        logging.error(logf(
            "None of the server pods are reachable",
            volume=volume
        ))

    # Ignore if already glusterfs process running for that volume
    if is_gluster_mount_proc_running(volname, mountpoint):
        logging.debug(logf(
            "Already mounted",
            mount=mountpoint
        ))
        return mountpoint

    # Ignore if already mounted
    if is_gluster_mount_proc_running(volname, mountpoint):
        logging.debug(logf(
            "Already mounted (2nd try)",
            mount=mountpoint
        ))
        return mountpoint

    if not os.path.exists(mountpoint):
        makedirs(mountpoint)

    with mount_lock:
        # Fix the log, so we can check it out later
        # log_file = "/var/log/gluster/%s.log" % mountpoint.replace("/", "-")
        log_file = "/var/log/gluster/gluster.log"

        cmd = [
            GLUSTERFS_CMD,
            "--process-name", "fuse",
            "-l", log_file,
            "--volfile-id", volname,
            "--fs-display-name", "kadalu:%s" % volname,
            mountpoint
        ]

        ## required for 'simple-quota'
        if not is_client:
            cmd.extend(["--client-pid", "-14"])

        # Use volfile server of bricks/storage_unit processes,
        # instead of volfile paths. Since now brick processes
        # supports serving of client volfiles.
        for host in hosts:
            cmd.extend(["--volfile-server", host])

        try:
            (_, err, _) = execute(*cmd)
        except CommandException as err:
            logging.error(logf(
                "error to execute command",
                volume=volume,
                cmd=cmd,
                error=format(err)
            ))
            raise err

    return mountpoint


def handle_external_volume(volume, mountpoint, is_client, hosts):
    """
    Handle mounting of volume with external host and setting of quota
    """

    volname = volume['g_volname']

    # Try to mount the Host Volume, handle failure if
    # already mounted
    if not is_gluster_mount_proc_running(volname, mountpoint):
        with mount_lock:
            mount_glusterfs_with_host(volname,
                                    mountpoint,
                                    hosts,
                                    volume['g_options'],
                                    is_client)
    else:
        logging.debug(logf(
            "Already mounted",
            mount=mountpoint
        ))
        return mountpoint

    use_gluster_quota = False
    if (os.path.isfile("/etc/secret-volume/ssh-privatekey")
        and "SECRET_GLUSTERQUOTA_SSH_USERNAME" in os.environ):
        use_gluster_quota = True
    secret_private_key = "/etc/secret-volume/ssh-privatekey"
    secret_username = os.environ.get('SECRET_GLUSTERQUOTA_SSH_USERNAME', None)

    if use_gluster_quota is False:
        logging.debug(logf("Do not set quota-deem-statfs"))
    else:
        # SSH into only first reachable host in volume['g_host'] entry
        g_host = reachable_host(hosts)

        if g_host is None:
            logging.error(logf("All hosts are not reachable"))
            return

        logging.debug(logf("Set quota-deem-statfs for gluster directory Quota"))
        quota_deem_cmd = [
            "ssh",
            "-oStrictHostKeyChecking=no",
            "-i",
            "%s" % secret_private_key,
            "%s@%s" % (secret_username, g_host),
            "sudo",
            "gluster",
            "volume",
            "set",
            "%s" % volume['g_volname'],
            "quota-deem-statfs",
            "on"
        ]
        try:
            execute(*quota_deem_cmd)
        except CommandException as err:
            errmsg = "Unable to set quota-deem-statfs via ssh"
            logging.error(logf(errmsg, error=err))
            raise err
    return mountpoint


# noqa # pylint: disable=unused-argument
def mount_glusterfs_with_host(volname, mountpoint, hosts, options=None, is_client=False):
    """Mount Glusterfs Volume"""

    if not os.path.exists(mountpoint):
        makedirs(mountpoint)

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

    g_ops = []
    if options:
        for option in options.split(","):
            g_ops.append(f"--{option}")

    logging.debug(logf(
        "glusterfs command",
        cmd=cmd,
        opts=g_ops,
        mountpoint=mountpoint,
    ))

    command = cmd + g_ops + [mountpoint]
    try:
        execute(*command)
    except CommandException as excep:
        if  excep.err.find("invalid option") != -1 or excep.err.find("unrecognized option") != -1:
            logging.warning(logf(
                "proceeding without supplied incorrect mount options",
                options=g_ops,
                ))
            command = cmd + [mountpoint]
            try:
                execute(*command)
            except CommandException as retry_err:
                logging.error(logf(
                    "mount command failed",
                    cmd=command,
                    error=retry_err,
                ))
                raise retry_err
        logging.error(logf(
            "mount command failed",
            cmd=command,
            error=excep,
        ))
        raise excep


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

        # For external volume both single_pv_per_pool,
        # g_volname and hosts should match
        # gluster_hosts is flattened to a string and can be compared as such
        # Assumptions:
        # 1. User will not reuse a gluster non-native volume
        if (get_single_pv_per_pool(vol) == get_single_pv_per_pool(params)
                and vol["g_volname"] == params["gluster_volname"]
                and vol["g_host"] == params["gluster_hosts"]):
            mntdir = os.path.join(HOSTVOL_MOUNTDIR, vol["name"])
            hvol = vol
            break

    if not mntdir:
        logging.warning("No host volume found to provide PV")
        return None

    mountpoint = mount_glusterfs(hvol, mntdir)

    if not mountpoint:
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


# Methods starting with 'yield_*' upon not a single entry raise StopIteration
# (via return "reason") and upon no entry for a specific scenario yields
# None. Caller should handle None gracefully based on the context the info is
# required, like:
# 1. Is it critical enough to serve the storage to user? Fail fast
# 2. Performing health checks or which can be eventually consistent (listvols)?
# Handle gracefully
def yield_hostvol_mount():
    """Yields mount directory where hostvol is mounted"""
    host_volumes = get_pv_hosting_volumes()
    info_exist = False
    for volume in host_volumes:
        hvol = volume['name']
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, hvol)
        try:
            mount_glusterfs(volume, mntdir)
        except CommandException as excep:
            logging.error(
                logf("Unable to mount volume", hvol=hvol, excep=excep.args))
            # We aren't able to mount this specific hostvol
            yield None
        logging.info(logf("Volume is mounted successfully", hvol=hvol))
        info_path = os.path.join(mntdir, 'info')
        if os.path.isdir(info_path):
            # After mounting a hostvol, start looking for PVC from '/mnt/<pool>/info'
            info_exist = True
            yield info_path
    if not info_exist:
        # A generator should yield "something", to signal "StopIteration" if
        # there's no info file on any pool, there should be empty yield
        # Note: raise StopIteration =~ return, but return with a reason is
        # better.
        return "No storage pool exists"


def yield_pvc_from_mntdir(mntdir):
    """Yields PVCs from a single mntdir"""
    # Max recursion depth is two subdirs (/<mntdir>/x/y/<pvc-name.json>)
    # If 'subvol/virtblock/rawblock' exist then max depth will be three subdirs
    if mntdir.endswith("info") and not os.path.isdir(mntdir):
        # There might be a chance that this function is used standalone and so
        # check for 'info' directory exists
        yield None
    for child in os.listdir(mntdir):
        name = os.path.join(mntdir, child)

        if os.path.isdir(name) and len(os.listdir(name)):
            yield from yield_pvc_from_mntdir(name)
        elif name.endswith('json'):
            # Base case we are interested in, the filename ending with '.json'
            # is 'PVC' name and contains it's size
            file_path = os.path.join(mntdir, name)
            with open(file_path) as handle:
                data = json.loads(handle.read().strip())
            logging.debug(
                logf("Found a PVC at", path=file_path, size=data.get("size")))
            data["name"] = name[name.rfind("/") + 1:name.rfind(".json")]
            yield data
        else:
            # If leaf is neither a json file nor a directory with contents
            yield None


def yield_pvc_from_hostvol():
    """Yields a single PVC sequentially from all the hostvolumes"""
    pvc_exist = False
    for mntdir in yield_hostvol_mount():
        if mntdir is not None:
            # Only yield PVC if we are able to mount corresponding pool
            pvc = yield_pvc_from_mntdir(mntdir)
            for data in pvc:
                if data is not None:
                    pvc_exist = True
                    data["mntdir"] = os.path.dirname(mntdir.strip("/"))
                    yield data
    if not pvc_exist:
        return "No PVC exist in any storage pool"


def wrap_pvc(pvc_gen):
    """Yields a tuple consisting value from gen and bool for last element"""
    # No need to get num of PVCs existing in Kadalu Storage, query them in real
    # time and yield PVC, True if current entry is the last of the PVC list
    # else yield PVC, False
    gen = pvc_gen()
    try:
        prev = next(gen)
        for value in gen:
            yield prev, False
            prev = value
        yield prev, True
    except StopIteration as errmsg:
        return errmsg


def yield_list_of_pvcs(max_entries=0):
    """Yields list of PVCs limited at 'max_entries'"""
    # List of dicts containing data of PVC from info_file (with extra keys,
    # 'name', 'mntdir')
    pvcs = []
    idx = -1
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
                return "Incorrect token supplied"
            logging.debug(
                logf("Yielding PVC set and next token is ",
                     token=token,
                     pvcs=pvcs))
            yield pvcs, token
            pvcs *= 0
    if idx == -1:
        return "No PVC exist in any storage pool"
