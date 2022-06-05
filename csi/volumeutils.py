"""
Utility functions for Volume management
"""

import json
import logging
import os
import re
import shutil
import tempfile
import threading
import time
from errno import ENOTCONN
from pathlib import Path

import csi_pb2
import xxhash
from jinja2 import Template
from kadalulib import (PV_TYPE_RAWBLOCK, PV_TYPE_SUBVOL, PV_TYPE_VIRTBLOCK,
                       CommandException, SizeAccounting, execute,
                       is_gluster_mount_proc_running, logf, makedirs,
                       reachable_host, retry_errors)

GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/bin/mount"
UNMOUNT_CMD = "/bin/umount"
MKFS_XFS_CMD = "/sbin/mkfs.xfs"
XFS_GROWFS_CMD = "/sbin/xfs_growfs"
RESERVED_SIZE_PERCENTAGE = 10
POOL_MOUNTDIR = "/mnt"
VOLFILES_DIR = "/kadalu/volfiles"
TEMPLATES_DIR = "/kadalu/templates"
POOLINFO_DIR = "/var/lib/gluster"
SECRET_PRIVATE_KEY = "/etc/secret-volume/ssh-privatekey"

# This variable contains in-memory map of all glusterfs processes (hash of volfile and pid)
# Used while sending SIGHUP during any modifcation to storage config
POOL_DATA = {}

statfile_lock = threading.Lock()    # noqa # pylint: disable=invalid-name
mount_lock = threading.Lock()    # noqa # pylint: disable=invalid-name
SINGLE_NODE_WRITER = getattr(csi_pb2.VolumeCapability.AccessMode,
                             "SINGLE_NODE_WRITER")

MULTI_NODE_MULTI_WRITER = getattr(csi_pb2.VolumeCapability.AccessMode,
                                  "MULTI_NODE_MULTI_WRITER")
LATEST_VOLUME_CONTEXT_VERSION = "2"


def pv_info_file_path(mountpath, pvtype, pvname):
    """
    PV info file path. Format: <mnt>/info/<path>
    """
    return f"{mountpath}/info/{pv_path(pvtype, pvname)}.json"


def options_based_pool_mount_suffix(opts, mnt_opts):
    """
    If additional Options provided via Storage Class then
    generate a suffix that can be used while mounting the Pool.
    This allows to have multiple mounts of the same Pool with
    different Volfile Options or Mount Options.
    """
    all_opts = ""
    if opts != "":
        all_opts += opts
    if mnt_opts != "":
        all_opts += mnt_opts

    if all_opts != "":
        return "_" + xxhash.xxh64_hexdigest(all_opts)

    return ""


def pv_path(pvtype, pvname):
    """
    PV Path is based on Hash of PV name and PV type.
    Format: <pvtype>/<pvhash[0:2]>/<pvhash[2:4]>/<pvname>
    """
    pvhash = xxhash.xxh64_hexdigest(pvname)

    return f"{pvtype}/{pvhash[0:2]}/{pvhash[2:4]}/{pvname}"


def pv_abspath(mountpoint, pvpath, mount_suffix=""):
    """Absolute Path of the PV including Pool mount path"""
    return f"{mountpoint}{mount_suffix}/{pvpath}"


def check_mount_availability(mountpoint):
    """
    Check for mount availability, Retry for
    ENOTCONN errors(Timeout 130 seconds)
    """
    return retry_errors(os.statvfs, [mountpoint], [ENOTCONN])


class PvException(Exception):
    """
    All Exceptions related to PV create, mount, expand and delete.
    """


def upgraded_csi_request_parameters(params):
    """
    For Storage class backward compatibility.
    """
    # To support different field names for Pool type
    pool_type = params.get("hostvol_type", None)
    pool_type = params.get("storage_type", pool_type)
    pool_type = params.get("pool_type", pool_type)

    # Pool mode is new field. Derive from pool type
    # Or use if user actually specified one
    pool_mode = None
    if pool_type is not None and pool_type.lower() == "external":
        pool_mode = "external"
        pool_type = None
    pool_mode = params.get("pool_mode", pool_mode)

    pool_name = params.get("storage_name", None)
    pool_name = params.get("pool_name", pool_name)

    gluster_hosts = params.get("gluster_host", None)
    gluster_hosts = params.get("gluster_hosts", gluster_hosts)

    kformat = params.get('kadalu_format', None)
    single_pv_per_pool = None
    if kformat is not None:
        single_pv_per_pool = kformat != "native"

    val = params.get("single_pv_per_pool", None)
    if val is not None:
        single_pv_per_pool = val.lower() in ["true", "yes", "1", "on"]

    return {
        "pool_type": pool_type,
        "pool_mode": pool_mode,
        "pool_name": pool_name,
        "gluster_volname": params.get("gluster_volname", None),
        "supported_pvtype": params.get("supported_pvtype", None),
        "gluster_hosts": gluster_hosts,
        "single_pv_per_pool": single_pv_per_pool,
        "node_affinity": params.get("node_affinity", None)
    }


def mount_rawblock_pv(pvpath, mountpoint):
    """Mount Rawblock PV to the given Path"""
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


# noqa # pylint: disable=too-many-public-methods
# noqa # pylint: disable=too-many-instance-attributes
class PersistentVolume:
    """
    PV object
    """
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.type = kwargs.get("type", "")
        self.size = kwargs.get("size", 0)
        self.hash = None
        self._path = kwargs.get("path", None)
        self.pool = kwargs.get("pool", None)
        self.sc_options = ""
        self.sc_mount_options = ""
        self._pool_mount_suffix = None
        self.fstype = None
        self.access_mode = None
        self.sc_parameters = {}

    @property
    def pool_mount_suffix(self):
        """
        New mount is required in Node plugin if any Options or Mount
        Options are customized via Storage Class. Only Mount Options
        are available with External Gluster Volume.

        Example (Mount a PV):

        ```
        pvol = PersistentVolume.from_volume_context(ctx)
        pvol.pool.mount(suffix=pvol.pool_mount_suffix)
        pvol.mount()
        ```
        """
        if self._pool_mount_suffix is not None:
            return self._pool_mount_suffix

        self._pool_mount_suffix = options_based_pool_mount_suffix(
            self.sc_options, self.sc_mount_options
        )

        return self._pool_mount_suffix

    @property
    def path(self):
        """Path relative to Pool Mount"""
        if self._path is None:
            self._path = pv_path(self.type, self.name)

        return self._path

    @property
    def abspath(self):
        """Absolute Path of the PV including Pool mount path"""
        return pv_abspath(
            self.pool.mountpoint, self.path, mount_suffix="")

    def valid_block_access_mode(self):
        """To check if the access mode provided is valid for block PV"""
        if self.type in [PV_TYPE_VIRTBLOCK, PV_TYPE_RAWBLOCK] and \
           self.access_mode != SINGLE_NODE_WRITER:
            return False

        return True

    @classmethod
    def from_csi_request(cls, req):
        """
        Parse the CSI PV create request and build PV object
        """
        pvol = PersistentVolume(name=req.name,
                                size=req.capacity_range.required_bytes)
        pvol.sc_options = req.parameters.get("storage_options", "")
        pvol.sc_options = req.parameters.get("options", pvol.sc_options)
        pvol.sc_mount_options = req.parameters.get("mount_options", "")
        pvol.type = PV_TYPE_SUBVOL

        # Mounted BlockVolume is requested via Storage Class.
        # GlusterFS File Volume may not be useful for some workloads
        # they can request for the Virtual Block formated and mounted
        # as default MountVolume.
        if req.parameters.get("pv_type", "").lower() == "block":
            pvol.type = PV_TYPE_VIRTBLOCK

        # RawBlock volume is requested via PVC
        for vol_capability in req.volume_capabilities:
            if vol_capability.WhichOneof("access_type") == "block":
                pvol.type = PV_TYPE_RAWBLOCK
                break

        for vol_capability in req.volume_capabilities:
            # TODO: A PVC can be asked with multiple access modes
            pvol.access_mode = vol_capability.access_mode.mode
            break

        # Add everything from parameter as filter item
        parameters = upgraded_csi_request_parameters(req.parameters)
        for pkey, pvalue in parameters.items():
            pvol.sc_parameters[pkey] = pvalue

        return pvol

    @classmethod
    def _create_block_pv(cls, req):
        """Create Virtual Block or Raw block PV"""
        pvol = PersistentVolume(name=req.name,
                                type=req.type, pool=req.pool, size=req.size)
        logging.debug(logf("PV path", pv_path=pvol.path))

        # Check for mount availability before creating virtblock volume
        check_mount_availability(pvol.pool.mountpoint)

        # Create a file with required size
        makedirs(os.path.dirname(pvol.abspath))
        logging.debug(logf(
            f"Created {req.type} directory",
            path=os.path.dirname(pvol.path)
        ))

        # at times orchestrator will send same request if earlier request times
        # out and truncate file if doesn't exist since if we reach here the request
        # is a valid one
        if not os.path.exists(pvol.abspath):
            volpath_fd = os.open(pvol.abspath, os.O_CREAT | os.O_RDWR)
            os.close(volpath_fd)
            os.truncate(pvol.abspath, req.size)
            logging.debug(logf(
                "Truncated file to required size",
                path=pvol.path,
                size=req.size
            ))

            if req.type == PV_TYPE_VIRTBLOCK:
                # TODO: Multiple FS support based on volume_capability mount option
                execute(MKFS_XFS_CMD, pvol.abspath)
                logging.debug(logf(
                    "Created Filesystem",
                    path=pvol.path,
                    command=MKFS_XFS_CMD
                ))

            pvol.save_metadata()

        return pvol

    @classmethod
    def _create_subdir_pv(cls, req):
        """Create a Sub directory based PV"""
        pvol = PersistentVolume(name=req.name, type=req.type,
                                pool=req.pool, size=req.size)
        logging.debug(logf("PV path", pv_path=pvol.path))

        # Check for mount availability before creating subdir volume
        check_mount_availability(pvol.pool.mountpoint)

        # Create a subdir
        makedirs(os.path.join(pvol.pool.mountpoint, pvol.path))
        logging.debug(logf(
            "Created PV directory",
            pvdir=pvol.path
        ))

        # Write info file so that Storage Unit's quotad sidecar
        # container picks it up (or) for external quota expansion
        pvol.save_metadata()

        pvol.set_quota()

        return pvol

    @classmethod
    def create(cls, req):
        """Create PV"""
        if req.type == PV_TYPE_SUBVOL:
            pvol = cls._create_subdir_pv(req)
        else:
            pvol = cls._create_block_pv(req)

        pvol.pool.update_free_size(req.name, -req.size)
        return pvol

    @property
    def use_gluster_quota(self):
        """Gluster Quota is enabled or not"""
        return (os.path.isfile(SECRET_PRIVATE_KEY)
                and "SECRET_GLUSTERQUOTA_SSH_USERNAME" in os.environ)

    def _set_gluster_quota(self):
        """Set Gluster Quota via SSH for external Gluster volume"""
        secret_username = os.environ.get('SECRET_GLUSTERQUOTA_SSH_USERNAME', None)

        logging.debug(logf("Set Quota using gluster directory Quota"))
        return execute_gluster_quota_command(
            SECRET_PRIVATE_KEY, secret_username, self.pool.gluster_hosts,
            self.pool.gluster_volname, self.path, self.size)

    def _set_simple_quota(self):
        """Set Kadalu Simple Quota"""
        #setfattr -n trusted.glusterfs.namespace -v true
        #setfattr -n trusted.gfs.squota.limit -v size
        try:
            retry_errors(os.setxattr,
                         [self.abspath,
                          "trusted.glusterfs.namespace",
                          "true".encode()],
                         [ENOTCONN])
            retry_errors(os.setxattr,
                         [self.abspath,
                          "trusted.gfs.squota.limit",
                          str(self.size).encode()],
                         [ENOTCONN])
            return
        # noqa # pylint: disable=broad-except
        except Exception as err:
            raise PvException(
                f"Failed to set quota using simple-quota. Error: {err}"
            ) from err

    def set_quota(self):
        """Set Quota if PV type is sub directory"""
        if self.type != PV_TYPE_SUBVOL:
            return

        if self.use_gluster_quota:
            return self._set_gluster_quota()

        return self._set_simple_quota()

    @property
    def infopath(self):
        """PV info file path"""
        return pv_info_file_path(self.pool.mountpoint, self.type, self.name)

    def save_metadata(self):
        """Save PV metadata in info file"""
        # Create info dir if not exists
        retry_errors(makedirs, [os.path.dirname(self.infopath)], [ENOTCONN])
        logging.debug(logf(
            "Created metadata directory",
            metadata_dir=os.path.dirname(self.infopath)
        ))

        with open(self.infopath, "w") as info_file:
            info_file.write(json.dumps({
                "size": self.size,
                "path_prefix": os.path.dirname(self.path)
            }))
            logging.debug(logf(
                "Metadata saved",
                metadata_file=self.infopath,
            ))

    def _expand_subdir_pv(self, requested_pvsize):
        """Expand Subdirectory PV"""
        logging.debug(logf(
            "Volume hash",
            volhash=self.hash
        ))

        # Check for mount availability before updating subdir volume
        check_mount_availability(self.pool.mountpoint)

        # Create a subdir
        makedirs(self.abspath)
        logging.debug(logf(
            "Updated PV directory",
            pvdir=self.path
        ))

        self.size = requested_pvsize

        # Write info file so that Storage Unit's quotad sidecar
        # container picks it up.
        self.save_metadata()

    def _expand_block_pv(self, requested_pvsize):
        """Expand Block PV"""
        # Check for mount availability before updating virtblock volume
        check_mount_availability(self.pool.mountpoint)

        # Update the file with required size
        makedirs(os.path.dirname(self.abspath))
        logging.debug(logf(
            "Updated virtblock directory",
            path=os.path.dirname(self.path)
        ))

        volpath_fd = os.open(self.abspath, os.O_CREAT | os.O_RDWR)
        os.close(volpath_fd)
        os.truncate(self.abspath, requested_pvsize)

        logging.debug(logf(
            "Truncated file to required size",
            path=self.path,
            size=requested_pvsize
        ))

        self.size = requested_pvsize
        self.save_metadata()
        if self.type == PV_TYPE_VIRTBLOCK:
            if os.path.ismount(self.abspath):
                execute("xfs_growfs", "-d", self.abspath)

    def expand(self, size):
        """Expand PV"""
        if self.type == PV_TYPE_SUBVOL:
            self._expand_subdir_pv(size)
        else:
            self._expand_block_pv(size)

        sizechange = size - self.size

        # Update the size after expanding the PV
        self.size = size

        # Set Quota if applicable
        self.set_quota()

        # sizechanged is the additional change to be
        # subtracted from storage-pool
        self.pool.update_free_size(self.name, -sizechange)

    @classmethod
    def search_by_name(cls, pv_name):
        """Search PV in all Pools"""
        pvol = PersistentVolume(name=pv_name)

        for pool in Pool.list():
            pool.mount()

            # Check for mount availability before checking the info file
            check_mount_availability(pool.mountpoint)

            possible_pv_info_paths = [
                pv_info_file_path(pool.mountpoint, PV_TYPE_SUBVOL, pv_name),
                pv_info_file_path(pool.mountpoint, PV_TYPE_VIRTBLOCK, pv_name),
                pv_info_file_path(pool.mountpoint, PV_TYPE_RAWBLOCK, pv_name)
            ]

            for idx, infopath in enumerate(possible_pv_info_paths):
                if not os.path.exists(infopath):
                    continue

                data = {}
                with open(infopath) as info_file:
                    data = json.load(info_file)

                pvol.type = PV_TYPE_SUBVOL
                if idx == 1:
                    pvol.type = PV_TYPE_VIRTBLOCK
                elif idx == 2:
                    pvol.type = PV_TYPE_RAWBLOCK

                pvol.pool = pool
                pvol.size = data["size"]
                return pvol

        return pvol

    def mount(self, mountpoint):
        """Mount PV"""
        # Mount the Pool if not mounted already
        self.pool.mount(suffix=self.pool_mount_suffix,
                        extra_options=self.sc_options,
                        extra_mount_options=self.sc_mount_options)

        # Mount path is different if Pool Options provided in Storage Class
        pvpath = pv_abspath(
            self.pool.mountpoint,
            self.path,
            mount_suffix=self.pool_mount_suffix
        )

        if not os.path.exists(pvpath):
            makedirs(pvpath)

        # TODO: Will losetup survive container reboot?
        if self.type == PV_TYPE_RAWBLOCK:
            return mount_rawblock_pv(pvpath, mountpoint)

        # Need this after kube 1.20.0
        makedirs(mountpoint)

        if self.type == PV_TYPE_VIRTBLOCK:
            fstype = "xfs" if self.fstype is None else self.fstype
            execute(MOUNT_CMD, "-t", fstype, pvpath, mountpoint)
        else:
            execute(MOUNT_CMD, "--bind", pvpath, mountpoint)

        os.chmod(mountpoint, 0o777)
        return True

    @classmethod
    def unmount(cls, mountpoint=None):
        """Unmount PV"""
        if mountpoint.find("volumeDevices"):
            # Should remove loop device as well or else duplicate loop devices will
            # be setup everytime
            cmd = ["findmnt", "-T", mountpoint, "-oSOURCE", "-n"]
            device, _, _ = execute(*cmd)
            if match := re.search(r'loop\d+', device):
                loop = match.group(0)
                cmd = ["losetup", "-d", f"/dev/{loop}"]
                execute(*cmd)

        if os.path.ismount(mountpoint):
            execute(UNMOUNT_CMD, "-l", mountpoint)

    @classmethod
    def from_volume_context(cls, ctx):
        """
        Parse Volume context and build PV object. This is used while
        mounting the PV in CSI node plugin.
        """
        ctx = upgraded_volume_context(ctx)
        pvol = PersistentVolume(name=ctx.get("name", ""),
                                type=ctx.get("type", ""),
                                path=ctx.get("path", None),
                                fstype=ctx.get("fs", "xfs"))
        pvol.pool = Pool.by_name(ctx.get("pool_name", ""))
        pvol.sc_options = ctx.get("options", "")
        pvol.sc_mount_options = ctx.get("mount_options", "")

        return pvol

    def to_volume_context(self):
        """Build Volume Context from PV object"""
        return {
            "version": LATEST_VOLUME_CONTEXT_VERSION,
            "pool_mode": self.pool.mode,
            "pool_name": self.pool.name,
            "type": self.type,
            "fs": "xfs",
            "single_pv_per_pool": f"{self.pool.single_pv_per_pool}".lower(),
            "path": self.path,
            "options": self.sc_options,
            "mount_options": self.sc_mount_options
        }

    def archive(self):
        """Archive PV"""
        archive_pv = PersistentVolume(name=f"archived-{self.name}",
                                      pool=self.pool.name)

        # Rename directory & files that are to be archived
        try:
            # Storage_unit/PVC
            os.rename(self.abspath, archive_pv.abspath)

            # Info-File
            os.rename(self.infopath, archive_pv.infopath)

            logging.info(logf(
                "PV archived",
                pv_name=self.name,
                archived_pv_name=archive_pv.name
            ))

        except OSError as err:
            logging.info(logf(
                "Error while archiving PV",
                pv_name=self.name,
                pv_path=self.path,
                pv_type=self.type,
                error=err,
            ))

    def delete(self):
        """Delete PV"""
        # Check for mount availability before deleting the volume
        check_mount_availability(self.pool.mountpoint)

        # Stop the delete operation if the reclaim policy is set to "retain"
        if self.pool.pv_reclaim_policy == "retain":
            logging.info(logf(
                "'retain' reclaim policy, volume not deleted",
                pv_path=self.path,
                pv_type=self.type
            ))
            return

        if self.pool.pv_reclaim_policy == "archive":
            return self.archive()

        try:
            # Remove PV Path <mnt>/<pvtype>/<hash[0:2]>/<hash[2:4]>/<pvname>
            if self.type == PV_TYPE_SUBVOL:
                shutil.rmtree(self.abspath)
            else:
                os.remove(self.abspath)

            # Remove PV Hash dirs <mnt>/<pvtype>/<hash[0:2]>/<hash[2:4]>
            # and <mnt>/<pvtype>/<hash[0:2]> and
            # PV type dir <mnt>/<pvtype>
            remove_path = self.abspath
            for _i in range(0, 3):
                remove_path = os.path.dirname(remove_path)
                os.rmdir(remove_path)
        except (OSError, FileNotFoundError) as err:
            # neither rmtree nor remove raises OSError with reason 'empty dir'
            # however rmdir if dir isn't empty raises 'empty dir' and in current
            # scenario it's be raised only once in 16^4 cases ;)
            if err.args[1].find("not empty") != -1:
                logging.info(logf(
                    "Error while deleting volume",
                    pv_path=self.abspath,
                    voltype=self.type,
                    error=err,
                ))

        logging.info(logf(
            "Volume deleted",
            pv_path=self.abspath,
            pv_type=self.type
        ))

        try:
            with open(self.infopath) as info_file:
                data = json.load(info_file)
                # We assume there would be a create before delete, but while
                # developing thats not true. There can be a delete request for
                # previously created pvc, which would be assigned to you once
                # you come up. We can't fail then.
                self.pool.update_free_size(self.name, data["size"])

            os.remove(self.infopath)

            # Remove PV Hash dirs <mnt>/info/<pvtype>/<hash[0:2]>/<hash[2:4]>
            # and <mnt>/info/<pvtype>/<hash[0:2]> and
            # PV type dir <mnt>/info/<pvtype>
            remove_path = self.infopath
            for _i in range(0, 3):
                remove_path = os.path.dirname(remove_path)
                os.rmdir(remove_path)

        except OSError as err:
            if err.args[1].find("not empty") != -1:
                logging.info(logf(
                    "Error while removing the file",
                    path=self.infopath,
                    pool_name=self.pool.name,
                    error=err,
                ))

        logging.debug(logf(
            "Removed volume metadata file",
            path=self.infopath,
            pool_name=self.pool.name
        ))

        return

    def mount_and_select_pool(self, pools):
        """
        Mount each pool if not mounted and assign a Pool
        based on the size availability.
        """
        for pool in pools:
            pool.mount()
            if pool.is_size_available(self.size):
                self.pool = pool
                return


pool_filters = []

def pool_filter(func):
    """
    Decorator function that just adds the
    function to list of filters.
    Example:
    ```
    @pool_filter
    def filter_node_affinity(pool, filters):
        ...
    ```
    """
    pool_filters.append(func)

    # Return function as is if direct call is required.
    return func

@pool_filter
def filter_node_affinity(pool, filters):
    """
    Filter Pool based on node affinity provided
    """
    node_name = filters.get("node_affinity", None)
    if node_name is not None:
        # Node affinity is only applicable for Replica1 Volumes
        if pool.type != "Replica1":
            return None

        # Volume is not from the requested node
        if node_name != pool.storage_units[0].kube_hostname:
            return None

    return pool


@pool_filter
def filter_pool_name(pool, filters):
    """
    filter Pool based on the name provided in filter
    """
    pool_name = filters.get("pool_name", None)
    if pool_name is not None and pool_name != pool.name:
        return None

    return pool


@pool_filter
def filter_pool_type(pool, filters):
    """
    If Pool type is specified then only get the Pools
    that belongs to requested types
    """
    pool_type = filters.get("pool_type", None)
    if pool_type is not None and pool_type != pool.type:
        return None

    return pool


@pool_filter
def filter_pool_mode(pool, filters):
    """
    If Pool mode is specified then only get the hosting
    volumes which belongs to requested types
    """
    mode = filters.get("pool_mode", None)
    if mode is not None and mode != pool.mode:
        return None

    return pool


@pool_filter
def filter_supported_pvtype(pool, filters):
    """
    If a storageclass created by specifying supported_pvtype
    then only include those Pools.
    This is useful when different Pool option needs to be
    set to host virtblock PVs
    """
    f_supported_pvtype = filters.get("supported_pvtype", None)

    if pool.supported_pvtype == "all":
        return pool

    if f_supported_pvtype is not None \
       and f_supported_pvtype != pool.supported_pvtype:
        return None

    return pool


@pool_filter
def filter_external_pool(pool, filters):
    """Filter External Storage Pools (Gluster Volumes)"""
    single_pv_per_pool = filters.get("single_pv_per_pool", None)
    g_volname = filters.get("gluster_volname", None)
    g_hosts = filters.get("gluster_hosts", None)

    # For external volume both kformat, g_volname and hosts should match
    # gluster_hosts is flattened to a string and can be compared as such
    # Assumptions:
    # 1. User will not reuse a gluster non-native volume
    if pool.is_mode_external and (
            single_pv_per_pool is None or \
            g_volname is None or \
            g_hosts is None
    ):
        return None

    if single_pv_per_pool is not None and pool.single_pv_per_pool != single_pv_per_pool:
        return None

    if g_volname is not None and pool.gluster_volname != g_volname:
        return None

    if g_hosts is not None and pool.gluster_hosts != g_hosts:
        return None

    return pool


# noqa # pylint: disable=too-many-arguments
def register_pool_mount(mountpoint, pool_name, mount_suffix, opts,
                        mount_opts, pid):
    """
    Register the Pool mounts globally. This info is
    used while reloading the mounts
    """
    if POOL_DATA.get(pool_name, None) is None:
        POOL_DATA[pool_name] = {}

    POOL_DATA[pool_name][mountpoint] = {
        "name": pool_name,
        "options": opts,
        "mount_options": mount_opts,
        "mount_suffix": mount_suffix,
        "pid": pid
    }


# noqa # pylint: disable=too-few-public-methods
class StorageUnit:
    """Storage Unit Object"""
    def __init__(self):
        self.path = ""
        self.kube_hostname = ""
        self.node = ""
        self.node_id = ""
        self.host_path = ""
        self.device = ""
        self.pvc_name = ""
        self.device_dir = ""
        self.decommissioned = ""
        self.index = 0


class Pool:
    """Pool Object"""
    def __init__(self, **kwargs):
        self.name = kwargs.get("name", "")
        self.id = ""  # noqa # pylint: disable=invalid-name
        self.pv_reclaim_policy = "delete"
        self.storage_units = []
        self.type = ""
        self.mode = ""
        self.disperse_data = 0
        self.disperse_redundancy = 0
        self.gluster_volname = None
        self.gluster_hosts = []
        self.options = ""
        self.mount_options = ""
        self.single_pv_per_pool = False
        self.supported_pvtype = "all"
        self.dht_subvol = []
        self.distribute_count = 1
        self.subvol_storage_units_count = 1
        self.decommissioned = ""

    def set_dependent_fields(self):
        """Set dependent fields of the Pool"""
        decommissioned = []
        if self.type == "Replica1":
            for storage_unit in self.storage_units:
                storage_unit_name = f"{self.name}-client-{storage_unit.index}"
                self.dht_subvol.append(storage_unit_name)
                if storage_unit.decommissioned != "":
                    decommissioned.append(storage_unit_name)
        else:
            count = 3
            if self.type == "Replica2":
                count = 2

            if self.type == "Disperse":
                count = self.disperse_data + self.disperse_redundancy

            self.subvol_storage_units_count = count
            for i in range(0, int(len(self.storage_units) / count)):
                storage_unit_name = "%s-%s-%d" % (
                    self.name,
                    "disperse" if self.type == "Disperse" else "replica",
                    i
                )
                self.dht_subvol.append(storage_unit_name)
                if self.storage_units[(i * count)].decommissioned != "":
                    decommissioned.append(storage_unit_name)

        self.decommissioned = ",".join(decommissioned)

    @classmethod
    def by_name(cls, name):
        """
        Parsed Poolinfo from the info JSON file created
        by the Operator during Storage add.
        """
        with open(os.path.join(POOLINFO_DIR, name + ".info")) as info_file:
            data = json.load(info_file)

        pinfo = Pool()
        pinfo.name = data["volname"]
        pinfo.id = data["volume_id"]
        pinfo.pv_reclaim_policy = data["pvReclaimPolicy"]
        pinfo.storage_units = []
        pinfo.type = "" if data["type"].lower() == "external" else data["type"]
        pinfo.mode = "external" if data["type"].lower() == "external" else "native"
        pinfo.gluster_volname = data.get("gluster_volname", None)
        pinfo.gluster_hosts = data.get("gluster_hosts", [])
        pinfo.mount_options = data.get("gluster_options", "")
        pinfo.mount_options = data.get("mount_options", pinfo.mount_options)
        pinfo.options = data.get("options", {})
        pinfo.options = ",".join(
            [f"{key}={value}" for key, value in pinfo.options.items()]
        )
        pinfo.single_pv_per_pool = data.get("kadalu_format", "native") != "native"
        pinfo.disperse_data = data.get("disperse", {}).get("data", 0)
        pinfo.disperse_redundancy = data.get("disperse", {}).get("redundancy", 0)

        for storage_unit_data in data.get("bricks", []):
            storage_unit = StorageUnit()
            storage_unit.path = storage_unit_data["brick_path"]
            storage_unit.kube_hostname = storage_unit_data["kube_hostname"]
            storage_unit.node = storage_unit_data["node"]
            storage_unit.node_id = storage_unit_data["node_id"]
            storage_unit.host_path = storage_unit_data["host_brick_path"]
            storage_unit.device = storage_unit_data["brick_device"]
            storage_unit.pvc_name = storage_unit_data["pvc_name"]
            storage_unit.device_dir = storage_unit_data["brick_device_dir"]
            storage_unit.decommissioned = storage_unit_data["decommissioned"]
            storage_unit.index = storage_unit_data["brick_index"]

            pinfo.storage_units.append(storage_unit)

        pinfo.set_dependent_fields()
        return pinfo

    @property
    def is_mode_external(self):
        """If the Pool is externally managed or not"""
        return self.mode == "external"

    def is_size_available(self, size):
        """
        Check if the requested size is available in the Pool
        to create or expand the PV.
        """
        with statfile_lock:
            # Stat done before `os.path.exists` to prevent ignoring
            # file not exists even in case of ENOTCONN
            mntdir_stat = check_mount_availability(self.mountpoint)
            with SizeAccounting(self.name, self.mountpoint) as acc:
                acc.update_summary(mntdir_stat.f_bavail * mntdir_stat.f_bsize)
                pv_stats = acc.get_stats()
                reserved_size = pv_stats["free_size_bytes"] * RESERVED_SIZE_PERCENTAGE/100

            if size < (pv_stats["free_size_bytes"] - reserved_size):
                return True

            return False

    @property
    def mountpoint(self):
        """
        Predictable mountpoint of the Pool.

        All natively managed Pools are mounted as /mnt/<pool-name>

        Externally managed Pools (External Gluster Volumes) can have
        pool name different than Gluster volume name. This is supported
        because External Gluster Volume name can have the same name as
        one of the internally managed Pool name.
        """
        # If Pool name and external Gluster Volume name is same then
        # use only pool name as mount path else use pool name and
        # gluster volume name.
        # /<mnt-dir>/<pool-name>_<gluster_volname>
        if self.is_mode_external and self.name != self.gluster_volname:
            return os.path.join(
                POOL_MOUNTDIR,
                f"{self.name}_{self.gluster_volname}"
            )

        # /<mnt-dir>/<volname>
        return os.path.join(POOL_MOUNTDIR, f"{self.name}")

    def _mount_external_gluster(self, suffix="", extra_options="",
                                extra_mount_options=""):
        """
        Mount External Gluster Volume.
        Only Mount options are used with External Gluster Volume
        mount. Other Volume options are not supported yet. Mount Options
        provided during the Storage add will be merged with the Mount
        Options provided with Storage Class.
        """

        # If any mount option is provided then that means a seperate
        # mount is required compared to earlier mounts of the same Gluster
        # Volume. Add suffix to the mount path to make it a different mount.
        mountpoint = self.mountpoint
        if suffix != "":
            mountpoint += suffix

        if not os.path.exists(mountpoint):
            makedirs(mountpoint)

        log_file = "/var/log/gluster/gluster.log"

        cmd = [
            GLUSTERFS_CMD,
            "--process-name", "fuse",
            "-l", log_file,
            "--volfile-id", self.gluster_volname,
        ]

        for host in self.gluster_hosts.split(','):
            cmd.extend(["--volfile-server", host])

        pool_mount_opts_str = self.mount_options
        if extra_mount_options != "":
            if pool_mount_opts_str != "":
                pool_mount_opts_str += ","
            pool_mount_opts_str += f"{extra_mount_options}"
        g_ops = []

        if extra_options != "":
            logging.info(logf(
                "Only mount options are supported. "
                "Use Gluster CLI to set the Volume "
                "options of External Gluster Volume",
                pool_name=self.name,
                gluster_volume_name=self.gluster_volname
            ))

        if pool_mount_opts_str != "":
            for option in pool_mount_opts_str.split(","):
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
            set_quota_deem_statfs(self.gluster_hosts, self.gluster_volname)
        except CommandException as excep:
            if  excep.err.find("invalid option") != -1:
                logging.info(logf(
                    "proceeding without supplied incorrect mount options",
                    options=g_ops,
                    ))
                command = cmd + [mountpoint]
                try:
                    execute(*command)
                except CommandException as excep1:
                    logging.info(logf(
                        "mount command failed",
                        cmd=command,
                        error=excep1,
                    ))
                return
            logging.info(logf(
                "mount command failed",
                cmd=command,
                error=excep,
            ))
        return

    def client_volfile_path(self, suffix=""):
        """Client Volfile Path"""
        return os.path.join(
            VOLFILES_DIR,
            f"{self.name}{suffix}.client.vol"
        )

    # noqa # pylint: disable=too-many-locals
    def _mount_native(self, suffix="", extra_options="",
                      extra_mount_options="", is_client=False):
        """
        Mount GlusterFS in native(Kadalu) way.
        Mount options are not used with native mounts. Use Volume Options
        to customize the Pool Mount.
        """

        # If any option is provided then that means a seperate
        # mount is required compared to earlier mounts of the same Gluster
        # Volume(Kadalu). Add suffix to the mount path
        # to make it a different mount.
        mountpoint = self.mountpoint
        if suffix != "":
            mountpoint += suffix

        # Generate the Client Volfile, later if Options
        # are provided then modify the Volfile with all the
        # Options included.
        self.generate_client_volfile()

        pool_opts_str = self.options
        if extra_options != "":
            if pool_opts_str != "":
                pool_opts_str += ","
            pool_opts_str += f"{extra_options}"

        if extra_mount_options != "":
            logging.info(logf(
                "Mount options are not supported.",
                pool_name=self.name
            ))

        # Update the options and get the updated path of Client Volfile file
        self.update_options_to_client_volfile(pool_opts_str, suffix)

        # Ignore if already glusterfs process running for that volume
        if is_gluster_mount_proc_running(self.name, mountpoint):
            self.reload_process()
            logging.debug(logf(
                "Already mounted",
                mount=mountpoint
            ))
            return mountpoint

        # Ignore if already mounted
        if is_gluster_mount_proc_running(self.name, mountpoint):
            self.reload_process()
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
                "--volfile-id", self.name,
                "--fs-display-name", f"kadalu:{self.name}",
                "-f", self.client_volfile_path(suffix=suffix),
                mountpoint
            ]

            ## required for 'simple-quota'
            if not is_client:
                cmd.extend(["--client-pid", "-14"])

            try:
                (_, err, pid) = execute(*cmd)
                register_pool_mount(mountpoint, self.name, suffix,
                                    pool_opts_str, "", pid)
            except CommandException as err:
                logging.error(logf(
                    "error to execute command",
                    pool_name=self.name,
                    cmd=cmd,
                    error=format(err)
                ))
                raise err

        return mountpoint

    def mount(self, suffix="", extra_options="",
              extra_mount_options="", is_client=False):
        """Mount the Storage Pool"""
        if self.is_mode_external:
            return self._mount_external_gluster(
                suffix, extra_options, extra_mount_options)

        return self._mount_native(
            suffix, extra_options, extra_mount_options, is_client)

    @classmethod
    def apply_pool_filter(cls, pool_name, filters):
        """Apply Pool filters if applicable and return Pool/None"""
        # If no filter is provided
        if filters is None:
            return Pool.by_name(pool_name)

        # Apply name filter separately than other filters available
        # to avoid opening the Info file and JSON Serialize
        filtered = filter_pool_name(Pool(name=pool_name), filters)
        if filtered is None:
            logging.debug(
                logf("Pool doesn't match the filter",
                     _pool_name=pool_name,
                     **filters))
            return None

        pool = Pool.by_name(pool_name)

        filtered_data = True
        for filter_func in pool_filters:
            filtered = filter_func(pool, filters)
            # Node affinity is not matching for this Volume,
            # Try other volumes
            if filtered is None:
                filtered_data = False
                logging.debug(
                    logf("Pool doesn't match the filter",
                         _pool_name=pool.name,
                         **filters))
                break

        if not filtered_data:
            return None

        return pool

    @classmethod
    def list(cls, filters=None, iteration=40):
        """List of Storage Pools. Apply filters when provided."""
        pools = []
        total_pools = 0

        for filename in os.listdir(POOLINFO_DIR):
            if not filename.endswith(".info"):
                continue

            total_pools += 1
            pool_name = filename.replace(".info", "")

            pool = cls.apply_pool_filter(pool_name, filters)
            if pool is not None:
                pools.append(pool)

        # If pool info file is not yet available, ConfigMap may not be ready
        # or synced. Wait for some time and try again
        # Lets just give maximum 2 minutes for the config map to come up!
        if total_pools == 0 and iteration > 0:
            time.sleep(3)
            iteration -= 1
            return Pool.list(filters, iteration)

        return pools

    def update_free_size(self, pvname, sizechange):
        """Update the free size in respective host volume's stats.db file"""

        # Check for mount availability before updating the free size
        check_mount_availability(self.mountpoint)

        with statfile_lock:
            with SizeAccounting(self.name, self.mountpoint) as acc:
                # Reclaim space
                if sizechange > 0:
                    acc.remove_pv_record(pvname)
                else:
                    acc.update_pv_record(pvname, -sizechange)

    def unmount(self, suffix=""):
        """Unmount the Storage Pool"""
        if suffix != "":
            mountpoint = self.mountpoint + suffix

        if is_gluster_mount_proc_running(self.name, mountpoint):
            execute(UNMOUNT_CMD, "-l", mountpoint)

    def reload_process(self):
        """Mount Glusterfs Volume"""
        if self.is_mode_external:
            return False

        if not POOL_DATA.get(self.name, None):
            return False

        # Ignore if already glusterfs process running for that volume
        with mount_lock:
            if not self.generate_client_volfile():
                return False

            # Fetch data of all mounts of the Pool and
            # Update the Volume options to Volfile if provided.
            mounts_data = POOL_DATA[self.name]
            for _mountpoint, mdata in mounts_data.items():
                self.update_options_to_client_volfile(
                    mdata["options"], mdata["mount_suffix"]
                )

            # TODO: ideally, keep the pid in structure for easier access
            # pid = POOL_DATA[volname]["pid"]
            # cmd = ["kill", "-HUP", str(pid)]
            cmd = ["ps", "--no-header", "-ww", "-o", "pid,command", "-C", "glusterfs"]

            try:
                out, err, _ = execute(*cmd)
                send_signal_to_process(self.name, out, "-HUP")
            except CommandException as err:
                logging.error(logf(
                    "error to execute command",
                    pool_name=self.name,
                    cmd=cmd,
                    error=format(err)
                ))
                return False

        return True

    def generate_client_volfile(self):
        """Generate Client Volfile for Glusterfs Volume"""
        # Tricky to get this right, but this solves all the elements of distribute in code :-)
        template_file_path = os.path.join(
            TEMPLATES_DIR,
            f"{self.type}.client.vol.j2"
        )
        client_volfile = os.path.join(
            VOLFILES_DIR,
            f"{self.name}.client.vol"
        )
        content = ""
        with open(template_file_path) as template_file:
            content = template_file.read()

        Template(content).stream(gvol=self).dump(client_volfile)
        return True

    def update_options_to_client_volfile(self, pool_opts_str, suffix):
        """
        Update the Volume options to already generated Client Volfile
        """
        if pool_opts_str == "":
            return

        # Construct 'dict' from passed storage-options in 'str'
        pool_options = pool_options_parse(pool_opts_str)

        # Keep the default volfile untouched
        tmp_volfile_path = tempfile.mkstemp()[1]
        shutil.copy(self.client_volfile_path(), tmp_volfile_path)

        # Parse the client-volfile, update passed storage-options & save
        parsed_client_volfile_path = Volfile.parse(tmp_volfile_path)
        parsed_client_volfile_path.update_options_by_type(pool_options)
        parsed_client_volfile_path.save()

        os.rename(tmp_volfile_path, self.client_volfile_path(suffix=suffix))
        return


def send_signal_to_process(volname, out, sig):
    """Sends the signal to one of the process"""

    for line in out.split("\n"):
        parts = line.split()
        pid = parts[0]
        for part in parts:
            if part.startswith("--volume-id="):
                if part.split("=")[-1] == volname:
                    cmd = [ "kill", sig, pid ]
                    try:
                        execute(*cmd)
                    except CommandException as err:
                        logging.error(logf(
                            "error to execute command",
                            volume=volname,
                            cmd=cmd,
                            error=format(err)
                        ))
                    return

    logging.debug(logf(
        "Sent SIGHUP to glusterfs process",
        volname=volname
    ))
    return


# noqa # pylint: disable=too-many-locals
# noqa # pylint: disable=too-many-statements
# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=too-many-branches
class VolfileElement:
    """Class to represent multiple elements within a volfile"""

    def __init__(self, name):
        self.name = name
        self.type = None
        self.options = {}
        self.subvolumes = None


class Volfile:
    """Class with volfile utils methods"""

    def __init__(self, volfile, elements):
        self.volfile = volfile
        self.elements = elements

    @classmethod
    def parse(cls, volfile):
        """Parse volfile into multiple volfile elements"""

        element = None
        elements = []
        with open(volfile) as volf:
            for line in volf:
                line = line.strip()
                if line.startswith("volume "):
                    element = VolfileElement(line.split()[-1])
                elif line == "end-volume":
                    elements.append(element)
                    element = None
                elif line.startswith("option "):
                    _, name, value = line.split()
                    element.options[name] = value
                elif line.startswith("subvolumes "):
                    element.subvolumes = line.split(" ", 1)[-1]
                elif line.startswith("type "):
                    element.type = line.split()[-1]
        return Volfile(volfile, elements)


    def update_options_by_type(self, opts):
        """
        Update existing storage-options with the options
        passed by user through storage-class
        """

        for element in self.elements:
            if opts.get(element.type, None) is not None:
                element.options.update(opts.get(element.type, {}))


    def save(self, volfile=None):
        """
        Reconstruct and saves the volfile
        with changes made to its elements
        """

        filepath = self.volfile
        if volfile is not None:
            filepath = volfile

        with open(f"{filepath}.tmp", "w") as volf:
            for element in self.elements:
                volf.write(f"volume {element.name}\n")
                volf.write(f"    type {element.type}\n")
                for name, value in element.options.items():
                    volf.write(f"    option {name} {value}\n")
                if element.subvolumes is not None:
                    volf.write(f"    subvolumes {element.subvolumes}\n")
                volf.write("end-volume\n\n")

        os.rename(filepath + ".tmp", filepath)


def pool_options_parse(opts_raw):
    """
    Parse the storage options specified in 'str' and
    construct to much more usable 'dict' format
    """

    opts_list = [opt.strip() for opt in opts_raw.split(",") if opt.strip() != ""]
    opts = {}
    for opt in opts_list:
        key, value = opt.split(":")
        xlator, opt_name = key.split(".")
        xlator = xlator.strip()
        opt_name = opt_name.strip()
        value = value.strip()
        if opts.get(xlator, None) is None:
            opts[xlator] = {}

        opts[xlator][opt_name] = value
    return opts


# TODO: raise exception instead of return error
def set_quota_deem_statfs(gluster_hosts, gluster_volname):
    """Set Quota Deem Statfs option"""

    gluster_host = reachable_host(gluster_hosts)
    if gluster_host is None:
        errmsg = "All hosts are not reachable"
        logging.error(logf(errmsg))
        return errmsg

    use_gluster_quota = False
    if (os.path.isfile("/etc/secret-volume/ssh-privatekey")
        and "SECRET_GLUSTERQUOTA_SSH_USERNAME" in os.environ):
        use_gluster_quota = True
        secret_private_key = "/etc/secret-volume/ssh-privatekey"
        secret_username = os.environ.get('SECRET_GLUSTERQUOTA_SSH_USERNAME', None)

    if use_gluster_quota is False:
        logging.debug(logf("Do not set quota-deem-statfs"))
        return

    logging.debug(logf("Set quota-deem-statfs for gluster directory Quota"))

    quota_deem_cmd = [
        "ssh",
        "-oStrictHostKeyChecking=no",
        "-i",
        secret_private_key,
        f"{secret_username}@{gluster_host}",
        "sudo",
        "gluster",
        "volume",
        "set",
        gluster_volname,
        "quota-deem-statfs",
        "on"
    ]
    try:
        execute(*quota_deem_cmd)
    except CommandException as err:
        errmsg = "Unable to set quota-deem-statfs via ssh"
        logging.error(logf(errmsg, error=err))
        raise err


# Methods starting with 'yield_*' upon not a single entry raise StopIteration
# (via return "reason") and upon no entry for a specific scenario yields
# None. Caller should handle None gracefully based on the context the info is
# required, like:
# 1. Is it critical enough to serve the storage to user? Fail fast
# 2. Performing health checks or which can be eventually consistent (listvols)?
# Handle gracefully
def yield_pool_mount():
    """Yields mount directory where pool is mounted"""
    pools = Pool.list()
    info_exist = False
    for pool in pools:
        try:
            pool.mount()
        except CommandException as excep:
            logging.error(
                logf("Unable to mount the Pool", pool_name=pool.name, excep=excep.args))
            # We aren't able to mount this specific hostvol
            yield None
        logging.info(logf("Pool is mounted successfully", pool_name=pool.name))
        info_path = os.path.join(pool.mountpoint, 'info')
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
    for mntdir in yield_pool_mount():
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
    for idx, value in enumerate(wrap_pvc(yield_pvc_from_pool)):
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


# noqa # pylint: disable=too-many-arguments
def execute_gluster_quota_command(privkey, user, host, gvolname, path, size):
    """
    Function to execute the GlusterFS's quota command on external cluster
    """
    # 'size' can always be parsed as integer with no errors
    size = int(size) * 0.95

    host = reachable_host(host)
    if host is None:
        errmsg = "All hosts are not reachable"
        logging.error(logf(errmsg))
        return errmsg

    quota_cmd = [
        "ssh",
        "-oStrictHostKeyChecking=no",
        "-i",
        privkey,
        f"{user}@{host}",
        "sudo",
        "gluster",
        "volume",
        "quota",
        gvolname,
        "limit-usage",
        f"/{path}",
        f"{size}",
    ]
    try:
        execute(*quota_cmd)
    except CommandException as err:
        errmsg = "Unable to set Gluster Quota via ssh"
        logging.error(logf(errmsg, error=err))
        return errmsg

    return None


def upgraded_volume_context(ctx):
    """
    Upgrade the Volume Context with propper field names
    """
    # Already using the upgraded version
    if ctx.get("version", "1") >= LATEST_VOLUME_CONTEXT_VERSION:
        return ctx

    return {
        "version": LATEST_VOLUME_CONTEXT_VERSION,
        "pool_mode": "external" if ctx["type"] == "External" else "native",
        "pool_name": ctx["hostvol"],
        "type": ctx["pvtype"],
        "fs": ctx["fstype"],
        "single_pv_per_pool": f'{ctx["kformat"] != "native"}'.lower(),
        "path": ctx["path"],
        "options": ctx.get("options", ""),
        "mount_options": ctx.get("storage_options", ""),
        "gluster_volume_name": ctx["gvolname"],
        "gluster_volfile_servers": ctx["gserver"]
    }
