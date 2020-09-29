"""Utility functions"""

import subprocess
import logging
import sys
import os
import time
import sqlite3

import xxhash

CREATE_TABLE_1 = """CREATE TABLE IF NOT EXISTS summary (
    volname    VARCHAR PRIMARY KEY,
    size       INTEGER,
    created_at REAL DEFAULT (datetime('now', 'localtime')),
    updated_at REAL
)"""

CREATE_TABLE_2 = """CREATE TABLE IF NOT EXISTS pv_stats (
    pvname     VARCHAR PRIMARY KEY,
    hash       VARCHAR,
    size       INTEGER,
    created_at REAL DEFAULT (datetime('now', 'localtime')),
    updated_at REAL
)"""

DB_NAME = "stat.db"
PV_TYPE_VIRTBLOCK = "virtblock"
PV_TYPE_SUBVOL = "subvol"

KADALU_VERSION = os.environ.get("KADALU_VERSION", "latest")


class TimeoutOSError(OSError):
    """Timeout after retries"""
    pass  # noqa # pylint: disable=unnecessary-pass


def retry_errors(func, args, errors, timeout=130, interval=2):
    """Retries given function in case of specified errors"""
    starttime = int(time.time())

    while True:
        try:
            return func(*args)
        except (OSError, IOError) as err:
            currtime = int(time.time())
            if (currtime - starttime) >= timeout:
                raise TimeoutOSError(err.errno, err.strerror) from None

            if err.errno in errors:
                time.sleep(interval)
                continue

            # Reraise the same error
            raise


def is_gluster_mount_proc_running(volname, mountpoint):
    """
    Check if glusterfs process is running for the given Volume name
    to confirm Glusterfs process is mounted
    """
    cmd = (
        r'ps ax | grep -w "/usr/sbin/glusterfs" '
        r'| grep -w "\-\-volfile\-id %s" '
        r'| grep -w -q "%s"' % (volname, mountpoint)
    )

    proc = subprocess.Popen(cmd, shell=True, stderr=None,
                            stdout=None, universal_newlines=True)
    proc.communicate()
    return proc.returncode == 0


def makedirs(dirpath):
    """exist_ok=True parameter will raise exception even if directory
    exists with different attributes. Handle EEXIST gracefully."""
    try:
        os.makedirs(dirpath)
    except FileExistsError:
        pass


class CommandException(Exception):
    """Custom exception for command execution"""
    def __init__(self, ret, out, err):
        self.ret = ret
        self.out = out
        self.err = err
        msg = "[%d] %s %s" % (ret, out, err)
        super().__init__(msg)


def get_volname_hash(volname):
    """XXHash based on Volume name"""
    return xxhash.xxh64_hexdigest(volname)


def get_volume_path(voltype, volhash, volname):
    """Volume path based on hash"""
    return "%s/%s/%s/%s" % (
        voltype,
        volhash[0:2],
        volhash[2:4],
        volname
    )


def execute(*cmd):
    """
    Execute command. Returns output and error.
    Raises CommandException on error
    """
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE,
                            universal_newlines=True)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise CommandException(proc.returncode, out.strip(), err.strip())
    return (out.strip(), err.strip())


def logf(msg, **kwargs):
    """Formats message for Logging"""
    if kwargs:
        msg += "\t"

    for msg_key, msg_value in kwargs.items():
        msg += " %s=%s" % (msg_key, msg_value)

    return msg


def logging_setup():
    """Logging Setup"""
    root = logging.getLogger()
    # verbose = os.environ.get("VERBOSE", False)
    verbose = True
    root.setLevel(logging.INFO)
    if verbose:
        root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.INFO)
    if verbose:
        handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter("[%(asctime)s] %(levelname)s "
                                  "[%(module)s - %(lineno)s:%(funcName)s] "
                                  "- %(message)s")
    handler.setFormatter(formatter)
    root.addHandler(handler)



def send_analytics_tracker(name, uid=None):
    """Send setup events to Google analytics"""

    # This function is not required anymore as we expect
    # users to report usage through github issues, or by
    # giving a 'star'.
    # Only thing we learnt from this is, External, Replica3
    # and Replica1 are preferred in that order (So far,
    # as of Sept 2020)

    return (name, uid)

class SizeAccounting:
    """
    Context manager to read and update Volume size and PV size info

    Usage:

    with SizeAccounting("storage-pool-1", "/mnt/storage-pool-1") as acc:
        acc.update_pv_record("pv1", 20000000)
    """

    def __init__(self, volname, mount_path):
        self.mount_path = mount_path
        self.volname = volname
        self.conn = None
        self.cursor = None

    def __enter__(self):
        """Initialize the Db Connection"""
        self.conn = sqlite3.connect(os.path.join(self.mount_path, DB_NAME))
        self.cursor = self.conn.cursor()
        self._create_tables()
        return self

    def __exit__(self, exc_type, exc_value, exc_traceback):
        """Close Db connection on exit of the Context manager"""
        self.conn.close()

    def _create_tables(self):
        """Create required tables"""
        self.cursor.execute(CREATE_TABLE_1)
        self.cursor.execute(CREATE_TABLE_2)

    def update_summary(self, size):
        """Update the total available size in storage pool"""

        # To retain the old value of created_at, select from existing
        query = """
        INSERT OR REPLACE INTO summary (
            volname, size, created_at, updated_at
        )
        VALUES (
            ?,
            ?,
            COALESCE((SELECT created_at FROM summary WHERE volname = ?),
                     datetime('now', 'localtime')),
            datetime('now', 'localtime')
        )
        """

        self.cursor.execute(query, (self.volname, size, self.volname))
        self.conn.commit()

    def update_pv_record(self, pvname, size):
        """Update Each PV size"""

        # To retain the old value of created_at, select from existing
        query = """
        INSERT OR REPLACE INTO pv_stats (
            pvname, size, hash, created_at, updated_at
        )
        VALUES (
            ?,
            ?,
            ?,
            COALESCE((SELECT created_at FROM pv_stats WHERE pvname = ?),
                     datetime('now', 'localtime')),
            datetime('now', 'localtime')
        )
        """
        pv_hash = get_volname_hash(pvname)
        self.cursor.execute(query, (pvname, size, pv_hash, pvname))
        self.conn.commit()

    def remove_pv_record(self, pvname):
        """Remove PV related entry when PV is deleted"""

        self.cursor.execute("DELETE FROM pv_stats WHERE pvname = ?", (pvname, ))
        self.conn.commit()

    def get_stats(self):
        """Get Statistics: total/used/free size, number of pvs"""
        self.cursor.execute("SELECT COUNT(pvname), SUM(size) FROM pv_stats")
        number_of_pvs, used_size_bytes = self.cursor.fetchone()

        self.cursor.execute("SELECT volname, size FROM summary")
        _, total_size_bytes = self.cursor.fetchone()

        if total_size_bytes is None:
            total_size_bytes = 0

        if used_size_bytes is None:
            used_size_bytes = 0

        if number_of_pvs is None:
            number_of_pvs = 0

        return {
            "number_of_pvs": number_of_pvs,
            "total_size_bytes": total_size_bytes,
            "used_size_bytes": used_size_bytes,
            "free_size_bytes": total_size_bytes - used_size_bytes
        }
