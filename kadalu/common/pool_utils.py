"""
Pool Utilities
"""
import json
import os
from types import SimpleNamespace
import threading
import logging
from errno import ENOTCONN

from kadalu.common.utils import (
    CommandException, SizeAccounting, execute,
    reachable_host, retry_errors,
    is_gluster_mount_proc_running, logf, makedirs,
    POOL_MODE_NATIVE,
    POOL_MODE_EXTERNAL_GLUSTER,
    POOL_MODE_EXTERNAL_KADALU
)

GLUSTERFS_CMD = "/opt/sbin/glusterfs"
MOUNT_CMD = "/bin/mount"
UNMOUNT_CMD = "/bin/umount"
MKFS_XFS_CMD = "/sbin/mkfs.xfs"
XFS_GROWFS_CMD = "/sbin/xfs_growfs"
RESERVED_SIZE_PERCENTAGE = 10
POOL_MOUNTDIR = "/mnt"
statfile_lock = threading.Lock()    # noqa # pylint: disable=invalid-name
mount_lock = threading.Lock()    # noqa # pylint: disable=invalid-name


def check_mount_availability(mountpoint):
    """
    Check for mount availability, Retry for
    ENOTCONN errors(Timeout 130 seconds)
    """
    return retry_errors(os.statvfs, [mountpoint], [ENOTCONN])


# TODO: raise exception instead of return error
def set_quota_deem_statfs(gluster_hosts, gluster_volname):
    """Set Quota Deem Statfs option"""

    gluster_host = reachable_host(gluster_hosts)
    if gluster_host is None:
        errmsg = "All hosts are not reachable"
        logging.error(logf(errmsg))
        raise Exception(errmsg)

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


class Pool:
    """Pool Object"""
    def __init__(self, **kwargs):
        self._data = SimpleNamespace(**kwargs)

    @property
    def subvol_storage_units_count(self):
        """Subvol size"""
        if self._data.type == "Replica1":
            return 1

        count = 3
        if self._data.type == "Replica2":
            count = 2

        if self._data.type == "Disperse":
            count = self.disperse_data + self.disperse_redundancy

        return count

    @classmethod
    def from_json(cls, data):
        """Parse the Pool JSON and convert to Object"""
        pool = Pool()
        pool._data = json.loads(data, object_hook=lambda d: SimpleNamespace(**d))

        return pool

    def to_json(self):
        """Parse the Pool JSON and convert to Object"""
        data = self._data.__dict__
        data.storage_units = []
        for storage_unit in self._data.storage_units:
            data.storage_units.append(storage_unit.__dict__)
        return json.dumps(data)

    def __getattr__(self, key):
        return getattr(self.data, key)

    @property
    def is_mode_external(self):
        """If the pool is external Gluster Volume or Kadalu Volume"""
        return self.is_mode_external_gluster or self.is_mode_external_kadalu

    @property
    def is_mode_external_gluster(self):
        """If the Pool is external Gluster Volume or not"""
        return self._data.mode == POOL_MODE_EXTERNAL_GLUSTER

    @property
    def is_mode_external_kadalu(self):
        """If the Pool is external Kadalu Volume or not"""
        return self._data.mode == POOL_MODE_EXTERNAL_KADALU

    @property
    def is_mode_native(self):
        """If the Pool is externally managed or not"""
        return self._data.mode == POOL_MODE_NATIVE

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
        if self.is_mode_external and self.name != self.external_volume_name:
            return os.path.join(
                POOL_MOUNTDIR,
                f"{self.name}_{self.external_volume_name}"
            )

        # /<mnt-dir>/<volname>
        return os.path.join(POOL_MOUNTDIR, f"{self.name}")

    @property
    def mount_src(self):
        """Mount Source path"""
        if self.is_mode_external_kadalu:
            return f"{self.external_pool_name}/{self.external_volume_name}"

        if self.is_mode_external_gluster:
            return f"gluster/{self.external_volume_name}"

        return f"kadalu/{self.name}"

    def _execute_mount_command(self, mountpoint, opts, extra_opts):
        cmd = [
            MOUNT_CMD,
            "-t", "kadalu",
            self.mount_src
        ]

        logging.debug(logf(
            "mount command",
            cmd=cmd,
            opts=extra_opts,
            mountpoint=mountpoint,
        ))
        command = cmd + ["-o", f"{','.join(opts + extra_opts)}"] + [mountpoint]
        if self.is_mode_external_gluster:
            set_quota_deem_statfs(self.external_volume_hosts,
                                  self.external_volume_name)
        try:
            execute(*command)

        except CommandException as excep:
            # Since the Mount options are already validated while
            # mounting in provisioner. This failure must be due to
            # extra options provided by the Storage Class.
            if  excep.err.find("invalid option") != -1:
                logging.info(logf(
                    "proceeding without supplied incorrect mount options",
                    options=extra_opts,
                    ))
                command = cmd + ["-o", ",".join(opts)] + [mountpoint]
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

    def mount(self, suffix="", extra_options="", extra_mount_options=""):
        """
        Mount Kadalu or Gluster Volume.
        Only Mount options are used with External Gluster Volume
        mount. Other Volume options are not supported yet. Mount Options
        provided during the Storage add will be merged with the Mount
        Options provided with Storage Class.
        """

        # If any mount option is provided then that means a seperate
        # mount is required compared to earlier mounts of the same Gluster
        # Volume. Add suffix to the mount path to make it a different mount.
        mountpoint = self.mountpoint + suffix

        # Ignore if already glusterfs process running for that volume
        if is_gluster_mount_proc_running(self.mount_src, mountpoint):
            logging.debug(logf(
                "Already mounted",
                mount=mountpoint
            ))
            return

        # Ignore if already mounted
        if is_gluster_mount_proc_running(self.mount_src, mountpoint):
            logging.debug(logf(
                "Already mounted (2nd try)",
                mount=mountpoint
            ))
            return

        makedirs(mountpoint)

        # TODO: Log file location change?
        log_file = "/var/log/gluster/gluster.log"

        pool_mount_opts = self.mount_options.split(",")

        # Add Volfile Servers
        volfile_servers = set()
        for host in self.external_volume_hosts:
            volfile_servers.add(host)

        for storage_unit in self.storage_units:
            volfile_servers.add(f"{storage_unit.node}:24007")

        pool_mount_opts.append(f"volfile-servers={' '.join(volfile_servers)}")
        pool_mount_opts.append(f"log-file={log_file}")

        if extra_mount_options != "":
            extra_mount_options = extra_mount_options.split(",")
        else:
            extra_mount_options = []

        # For Native and external Kadalu Volume, volfile-id is generated as
        # client-<POOL>-<VOLUME>. Gluster expects volfile-id
        # as Volume name only.
        if self.is_mode_external_gluster:
            pool_mount_opts += [
                f"volfile-id={self.external_volume_name}",
                "process-name=fuse"
            ]
        else:
            ## required for 'simple-quota'
            pool_mount_opts.append("client-pid=-14")

        if extra_options != "":
            logging.info(logf(
                "Only mount options are supported. "
                "Use Kadalu/Gluster CLI to set the Volume "
                "options",
                pool_name=self.name,
                pool_mode=self.mode,
                external_volume_name=self.external_volume_name
            ))

        self._execute_mount_command(
            mountpoint,
            pool_mount_opts,
            extra_mount_options
        )

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
        mountpoint = self.mountpoint + suffix

        if is_gluster_mount_proc_running(self.mount_src, mountpoint):
            execute(UNMOUNT_CMD, "-l", mountpoint)
