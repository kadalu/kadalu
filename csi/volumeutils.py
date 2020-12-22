"""
Utility functions for Volume management
"""

import os
import json
import time
import logging
import threading
import shutil
from errno import ENOTCONN

from jinja2 import Template

from kadalulib import execute, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK, \
    get_volname_hash, get_volume_path, logf, makedirs, CommandException, \
    retry_errors, is_gluster_mount_proc_running, SizeAccounting


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
def get_pv_hosting_volumes(filters={}):
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
                "g_host": data.get("gluster_host", None),
                "g_options": data.get("gluster_options", None),
            }

            volumes.append(volume)

    # Need a different way to get external-kadalu volumes

    # If volume file is not yet available, ConfigMap may not be ready
    # or synced. Wait for some time and try again
    if total_volumes == 0:
        time.sleep(2)
        return get_pv_hosting_volumes()

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

    volpath = os.path.join(HOSTVOL_MOUNTDIR, vol.hostvol, vol.volpath)
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

    logging.debug(logf(
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

    host_volumes = get_pv_hosting_volumes()
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
    host_volumes = get_pv_hosting_volumes()
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


def mount_glusterfs(volume, mountpoint):
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
                                      volume['g_options'])
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
            "-f", "%s/%s.client.vol" % (VOLFILES_DIR, volume['name']),
            mountpoint
        ]
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

    return


# noqa # pylint: disable=unused-argument
def mount_glusterfs_with_host(volname, mountpoint, host, options=None):
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
        "-s", host,
        mountpoint
    ]
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
        if (vol["g_volname"] != params["gluster_volname"]) or \
           (vol["g_host"] != params["gluster_host"]):
            continue

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
