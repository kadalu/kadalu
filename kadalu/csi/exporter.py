import logging
import os

import uvicorn
from fastapi import FastAPI

from kadalu.common.utils import logf, logging_setup
from kadalu.csi.volumeutils import POOL_MOUNTDIR, yield_pvc_from_mntdir

metrics_app = FastAPI()

@metrics_app.get("/_api/metrics")
def metrics():
    """
    Gathers storage and pvcs metrics.
    Starts process by exposing the data collected in port 8050 at '/_api/metrics'.
    """

    data = {
        "pod": {},
        "storages": []
    }

    # Return -1 if unable to fetch 'cgroup' data,
    # until new method is found to get CPU & Memory data in LXD containers.
    memory_usage_in_bytes = -1
    cpu_usage_in_nanoseconds = -1

    memory_usage_file_path = '/sys/fs/cgroup/memory/memory.usage_in_bytes'
    if os.path.exists(memory_usage_file_path):
        with open(memory_usage_file_path, 'r') as memory_fd:
            memory_usage_in_bytes = int(memory_fd.read().strip())

    cpu_usage_file_path = '/sys/fs/cgroup/cpu/cpuacct.usage'
    if os.path.exists(cpu_usage_file_path):
        with open(cpu_usage_file_path, 'r') as cpu_fd:
            cpu_usage_in_nanoseconds = int(cpu_fd.read().strip())

    data["pod"] = {
        "memory_usage_in_bytes": memory_usage_in_bytes,
        "cpu_usage_in_nanoseconds": cpu_usage_in_nanoseconds
    }

    if os.environ.get("CSI_ROLE", "-") == "nodeplugin":
        pod_name_path = '/etc/hostname'
        with open(pod_name_path, 'r') as pod_fd:
            pod_name = pod_fd.read().strip()
            data["pod"].update({"pod_name": pod_name})

    # Handle condition for no storage & PVC,
    # sometimes storage name is not shown at /mnt until server is mounted.
    if len(os.listdir(POOL_MOUNTDIR)) == 0:
        logging.debug(logf(
            "No storage-pool found! Try again by creating a storage.",
            POOL_MOUNTDIR=POOL_MOUNTDIR
        ))
        return data

    # Gathers metrics for each storage
    for dirname in os.listdir(POOL_MOUNTDIR):
        storage_path = os.path.join(POOL_MOUNTDIR, dirname)

        if os.path.ismount(storage_path):

            stat = os.statvfs(storage_path)

            # Storage Capacity
            total_capacity_bytes = stat.f_bsize * stat.f_blocks
            free_capacity_bytes = stat.f_bsize * stat.f_bavail
            used_capacity_bytes = total_capacity_bytes - free_capacity_bytes

            # Storage Inodes
            total_inodes = stat.f_files
            free_inodes = stat.f_favail
            used_inodes = total_inodes - free_inodes

            # TODO: Handle extracting Pool name from Mountpoint
            # when mount suffix is used or external Gluster
            # Volume(<pool>_<gluster_volname>)
            storage = {
                "name": dirname,
                "total_capacity_bytes": total_capacity_bytes,
                "free_capacity_bytes": free_capacity_bytes,
                "used_capacity_bytes": used_capacity_bytes,
                "total_inodes": total_inodes,
                "free_inodes": free_inodes,
                "used_inodes": used_inodes,
                "pvc": []
            }

            storage_info_path = os.path.join(storage_path, "info")
            if not os.path.exists(storage_info_path):
                data["storages"].append(storage)
                logging.warning(logf(
                    "No PVC found. Sending only storage metrics"
                ))
                return data

            # Gathers metrics for each subvol[PVC]
            for pvc in yield_pvc_from_mntdir(storage_info_path):

                # Handle condition when PVC is created and then deleted,
                # Leaving an empty leaf directory with path prefix.
                if pvc is None:
                    logging.warning(logf(
                        "PVC JSON file not found. PVC must have been deleted. Trying again!"
                    ))
                    # Skip loop for now and look for any new possible healthy PVC
                    continue

                pvcname = pvc.get("name")
                pvcpath = os.path.join(storage_path, pvc.get("path_prefix"), pvcname)

                stat = os.statvfs(pvcpath)

                # PVC Capacity
                total_pvc_capacity_bytes = stat.f_bsize * stat.f_blocks
                free_pvc_capacity_bytes = stat.f_bsize * stat.f_bavail
                used_pvc_capacity_bytes = total_pvc_capacity_bytes - free_pvc_capacity_bytes

                # PVC Inodes
                total_pvc_inodes = stat.f_files
                free_pvc_inodes = stat.f_favail
                used_pvc_inodes = total_pvc_inodes - free_pvc_inodes

                pvc = {
                    "pvc_name": pvcname,
                    "total_pvc_capacity_bytes": total_pvc_capacity_bytes,
                    "free_pvc_capacity_bytes": free_pvc_capacity_bytes,
                    "used_pvc_capacity_bytes": used_pvc_capacity_bytes,
                    "total_pvc_inodes": total_pvc_inodes,
                    "free_pvc_inodes": free_pvc_inodes,
                    "used_pvc_inodes": used_pvc_inodes
                }

                storage["pvc"].append(pvc)
            data["storages"].append(storage)

    return data


if __name__ == "__main__":

    logging_setup()
    logging.info(logf(
        "Started metrics exporter process at port 8050"
    ))

    uvicorn.run("exporter:metrics_app", host="0.0.0.0", port=8050, log_level="info")
