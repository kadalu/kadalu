"""Utility Script to remove Archived PVs"""

import sys
import os
import shutil
import argparse

from errno import ENOTCONN
from kadalu.csi.volumeutils import PersistentVolume
from kadalu.common.utils import retry_errors


def get_archived_pvs(pool_name, pv_name):
    """ Return all or specified archived_pvcs based on agrs """

    archived_pvs = []
    try:
        for pvol in PersistentVolume.list(pool_name):
            if pvol is not None:
                # With --pvc arg
                if pv_name is not None and pv_name == pvol.name:
                    archived_pvs.append(pvol)
                    return archived_pvs

                # Check for all archived pvcs
                if pv_name is None and "archived-" in pvol.name:
                    archived_pvs.append(pvol)

        # Return -1 if no matched specified pvc
        if pv_name is not None:
            sys.stderr.write(f"Specified PV {pv_name} is not found")
            return -1

        # This return is for without --pvc.
        return archived_pvs

    except FileNotFoundError:
        sys.stderr.write(f"Storage pool {pool_name} is not found")
        return -1


def delete_archived_pvs(archived_pvs):
    """ Delete all archived pvs in archived_pvs """

    for pvol in archived_pvs:

        # Check for mount availablity before deleting info file & PVC
        retry_errors(os.statvfs, [pvol.pool.mountpoint], [ENOTCONN])

        # Remove PV in stat.db
        pvol.pool.update_free_size(pvol.name.replace("archived-", ""), pvol.size)

        # Delete info file
        shutil.rmtree(os.path.dirname(pvol.infopath))

        # Delete PVC
        shutil.rmtree(os.path.dirname(pvol.abspath))


def main():
    """ main """

    parser = argparse.ArgumentParser()
    parser.add_argument("pool_name", help="name of storage-pool")
    parser.add_argument("--pv", default=None,
                        help="name of archived pv belonging to specified storage-pool")

    args = parser.parse_args()

    if args.pv and not args.pv.startswith("archived-"):
        sys.stderr.write("Passing of non archived PV not allowed.")
        sys.exit()

    archived_pvs = get_archived_pvs(args.pool_name, args.pv)
    if archived_pvs == -1:
        sys.exit()

    if archived_pvs:
        sys.stdout.write(f"Found archived PVs at storage pool {args.pool_name}\n")
        delete_archived_pvs(archived_pvs)
        sys.stdout.write(f"Completed deletion of archived pv(s) of storage-pool {args.pool_name}\n")
    else:
        sys.stderr.write(f"No archived PVCs found at storage-pool {args.pool_name}")


if __name__ == "__main__":
    main()
