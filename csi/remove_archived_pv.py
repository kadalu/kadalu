import sys
import os
import shutil
import argparse
from errno import ENOTCONN
from volumeutils import HOSTVOL_MOUNTDIR, update_free_size, yield_pvc_from_mntdir
from kadalulib import retry_errors


def get_archived_pvs(storage_name, pvc_name):
    archived_pvs = {}
    mntdir = os.path.join(HOSTVOL_MOUNTDIR, storage_name)
    try:
        for pvc in yield_pvc_from_mntdir(mntdir):
            print(pvc)

            if None not in (pvc_name, pvc) and pvc_name == pvc["name"]:
                archived_pvs[pvc["name"]] = pvc
                return archived_pvs

            if pvc is not None and "pvc" in pvc["name"]:
                archived_pvs[pvc["name"]] = pvc
                return archived_pvs
    except FileNotFoundError as err:
        sys.stderr.write("Storage pool %s is not found" % storage_name)
        return -1

    return None


def delete_archived_pv(storage_name, archived_pvs):
    for pvname, values in archived_pvs.items():

        print(pvname, values)

        # Check for mount availablity before deleting info file & PVC
        mntdir = os.path.join(HOSTVOL_MOUNTDIR, storage_name)
        retry_errors(os.statvfs, [mntdir], [ENOTCONN])

        # Remove PV in stat.db
        update_free_size(storage_name, pvname, values["size"])

        # Delete info file
        info_file_path = os.path.join(mntdir, "info", values["path_prefix"], pvname + ".json")
        shutil.rmtree(os.path.dirname(info_file_path))

        # Delete PVC
        pvc_path = os.path.join(mntdir, values["path_prefix"], pvname)
        shutil.rmtree(os.path.dirname(pvc_path))


def main():

    parser = argparse.ArgumentParser()
    parser.add_argument("name", help="name of storage-pool")
    parser.add_argument("--pvc", help="name of archived pvc belonging to specified storage-pool", default=None)

    args = parser.parse_args()
    sys.stdout.write(args.name)
    print(args.name)
    if args.pvc:
        print(args.pvc)

    archived_pvs = get_archived_pvs(args.name, args.pvc)
    if archived_pvs is not (None, -1):
        sys.stdout.write("Found archived PVCs at storage pool %s" % args.name)
        delete_archived_pv(args.name, archived_pvs)
    else:
        sys.stderr.write("No archived PVCs found at storage-pool %s" % args.name)
        # Cannot capture -1
        # return -1


if __name__ == "__main__":
    main()
