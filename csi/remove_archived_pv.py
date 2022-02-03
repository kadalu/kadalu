import sys
import os
import shutil
from errno import ENOTCONN
from volumeutils import HOSTVOL_MOUNTDIR, update_free_size, yield_pvc_from_mntdir
from kadalulib import retry_errors

def get_names():
    storage_name = ""
    #PVC_NAME = ""
    try:
        if len(sys.argv) > 1:
            storage_name = sys.argv[5]
        # if len(sys.argv) >= 3:
        #     PVC_NAME = sys.argv[2]
        print(storage_name)
        sys.stdout.write("pass \n")
        return storage_name
    except IndexError as err:
        sys.stderr.write("error: Index out of range \n")
        sys.exit(-1)


def get_archived_pvs(storage_name):
    archived_pvs = {}
    mntdir = os.path.join(HOSTVOL_MOUNTDIR, storage_name)
    for pvc in yield_pvc_from_mntdir(mntdir):
        print(pvc)
        if pvc is not None and "pvc" in pvc["name"]:
            archived_pvs[pvc["name"]] = pvc
            return archived_pvs
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
    storage_name = get_names()
    archived_pvs = get_archived_pvs(storage_name)
    if archived_pvs:
        delete_archived_pv(storage_name, archived_pvs)


if __name__ == "__main__":
    main()
