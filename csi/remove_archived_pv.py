import sys
import os
import shutil
import argparse

from errno import ENOTCONN
from volumeutils import PV
from kadalulib import retry_errors


def get_archived_pvs(pool_name, pv_name):
    """ Return all or specified archived_pvcs based on agrs """

    archived_pvs = []
    try:
        for pvol in PV.list(pool_name=pool_name):
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
            sys.stderr.write("Specified PV %s is not found" % pv_name)
            return -1

        # This return is for without --pvc.
        return archived_pvs

    except FileNotFoundError:
        sys.stderr.write("Storage pool %s is not found" % pool_name)
        return -1


def delete_archived_pvs(pool_name, archived_pvs):
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
        sys.stdout.write("Found archived PVs at storage pool %s\n" % args.pool_name)
        delete_archived_pvs(args.pool_name, archived_pvs)
        sys.stdout.write("Completed deletion of archived pv(s) of storage-pool %s\n" %args.pool_name)
    else:
        sys.stderr.write("No archived PVCs found at storage-pool %s" % args.pool_name)


if __name__ == "__main__":
    main()
