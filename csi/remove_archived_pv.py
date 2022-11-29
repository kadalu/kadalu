import sys
import os
import shutil
import argparse
from errno import ENOTCONN
from volumeutils import HOSTVOL_MOUNTDIR, update_free_size, yield_pvc_from_mntdir
from kadalulib import retry_errors


def get_archived_pvs(storage_name, pvc_name):
    """ Return all or specified archived_pvcs based on agrs """

    archived_pvs = {}

    mntdir = os.path.join(HOSTVOL_MOUNTDIR, storage_name, "info")
    if not os.path.isdir(mntdir):
        sys.stderr.write(f"Metadata for storagepool {storage_name} is not found")
        return -1

    try:
        for pvc in yield_pvc_from_mntdir(mntdir):
            if pvc is not None:

                # With --pvc arg
                if pvc_name is not None and pvc_name == pvc["name"]:
                    archived_pvs[pvc["name"]] = pvc
                    return archived_pvs

                # Check for all archived pvcs
                if pvc_name is None and "archived-" in pvc["name"]:
                    archived_pvs[pvc["name"]] = pvc

        # Return -1 if no matched specified pvc
        if pvc_name is not None:
            sys.stderr.write("Specified PVC %s is not found" % pvc_name)
            return -1

        # This return is for without --pvc.
        return archived_pvs

    except FileNotFoundError:
        sys.stderr.write("Storage pool %s is not found" % storage_name)
        return -1


def delete_archived_pvs(storage_name, archived_pvs):
    """ Delete all archived pvcs in archived_pvs """

    for pvname, values in archived_pvs.items():

        # Check for mount availablity before deleting info file & PVC
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, storage_name)
        retry_errors(os.statvfs, [mntdir], [ENOTCONN])

        # Remove PV in stat.db
        update_free_size(storage_name, pvname.replace("archived-", ""), values["size"])

        # Delete info file
        info_file_path = os.path.join(mntdir, "info", values["path_prefix"], pvname + ".json")
        shutil.rmtree(os.path.dirname(info_file_path))

        # Delete PVC
        pvc_path = os.path.join(mntdir, values["path_prefix"], pvname)
        shutil.rmtree(os.path.dirname(pvc_path))


def main():
    """ main """

    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="name of storage-pool")
    parser.add_argument("--pvc", default=None,
                        help="name of archived pvc belonging to specified storage-pool")

    args = parser.parse_args()

    if args.pvc and not args.pvc.startswith("archived-"):
        sys.stderr.write("Passing of non archived PVC not allowed.")
        sys.exit()

    archived_pvs = get_archived_pvs(args.name, args.pvc)
    if archived_pvs == -1:
        sys.exit()

    if archived_pvs:
        sys.stdout.write("Found archived PVCs at storage pool %s\n" % args.name)
        delete_archived_pvs(args.name, archived_pvs)
        sys.stdout.write("Completed deletion of archived pvc(s) of storage-pool %s\n" %args.name)
    else:
        sys.stderr.write("No archived PVCs found at storage-pool %s" % args.name)


if __name__ == "__main__":
    main()
