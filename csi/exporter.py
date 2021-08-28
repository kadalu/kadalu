import os
import uvicorn
import logging
from fastapi import FastAPI
from volumeutils import (HOSTVOL_MOUNTDIR, PV_TYPE_SUBVOL,
                          yield_pvc_from_mntdir)
from kadalulib import logging_setup, logf

app = FastAPI()

@app.get("/_api/metrics")
def metrics():
    """
    Gathers storage and pvcs metrics. 
    Starts process by exposing the data collected in port 8050 at '/_api/metrics'.
    """
    
    data = {
        "pod": {},
        "storages": []
    }

    pod_name = ""
    memory_usage_in_bytes = 0
    cpu_usage_in_nanoseconds = 0

    pod_name_path = '/etc/hostname'
    with open(pod_name_path, 'r') as pod_fd:
        pod_name = pod_fd.read().strip()

    memory_usage_file_path = '/sys/fs/cgroup/memory/memory.usage_in_bytes'
    with open(memory_usage_file_path, 'r') as memory_fd:
        memory_usage_in_bytes = memory_fd.read().strip()

    cpu_usage_file_path = '/sys/fs/cgroup/cpu/cpuacct.usage'
    with open(cpu_usage_file_path, 'r') as cpu_fd:
        cpu_usage_in_nanoseconds = cpu_fd.read().strip()

    data["pod"] = {
        "pod_name": pod_name,
        "memory_usage_in_bytes": int(memory_usage_in_bytes),
        "cpu_usage_in_nanoseconds": int(cpu_usage_in_nanoseconds)
    }

    # Handle condition for no storage & PVC,
    # sometimes storage name is not shown until a PVC is created at /mnt 
    # Observations:
    # When there is a PVC previously created for now deployed storage-pool,
    # this behaviour is seen. [ Volume not found for deleted, delete response completed ]
    if len(os.listdir(HOSTVOL_MOUNTDIR)) == 0:
        logging.error(logf(
            "No storage-pool found! Try again by creating a storage.",
            HOSTVOL_MOUNTDIR=HOSTVOL_MOUNTDIR
        ))
        return data

    # Gathers metrics for each storage
    for dirname in os.listdir(HOSTVOL_MOUNTDIR):
        storage_path = os.path.join(HOSTVOL_MOUNTDIR, dirname)

        if os.path.ismount(storage_path):

            stat = os.statvfs(storage_path)

            # Storage Capacity
            total_capacity = stat.f_bsize * stat.f_blocks
            free_capacity = stat.f_bsize * stat.f_bavail
            used_capacity = total_capacity - free_capacity

            # Storage Inodes
            total_inodes = stat.f_files
            free_inodes = stat.f_favail
            used_inodes = total_inodes - free_inodes

            storage = {
                "name": dirname,
                "total_capacity": total_capacity,
                "free_capacity": free_capacity,
                "used_capacity": used_capacity,
                "total_inodes": total_inodes,
                "free_inodes": free_inodes,
                "used_inodes": used_inodes,
                "pvc": [] 
            }

            storage_info_path = os.path.join(storage_path, "info")
            if not os.path.exists(storage_info_path):
                data["storages"].append(storage)
                logging.error(logf(
                    "No PVC found. Sending only storage metrics",
                    storage=storage,
                    data=data
                ))
                return data

            # Gathers metrics for each subvol[PVC]
            for pvc in yield_pvc_from_mntdir(storage_info_path):
              
                # Handle condition when PVC is created and then deleted,
                # Leaving an empty leaf directory with path prefix.
                if pvc is None:
                    # DEBUG
                    logging.info(logf(
                        "PVC JSON file not found. PVC must have been deleted. Trying again!"
                    ))
                    # Skip loop for now and look for any new possible healthy PVC
                    continue

                # pvc[0]: name
                # pvc[1]: size
                # pvc[2]: path prefix
                pvcname = pvc[0]
                pvcpath = os.path.join(storage_path, pvc[2], pvcname)

                stat = os.statvfs(pvcpath)

                # PVC Capacity
                total_pvc_capacity = stat.f_bsize * stat.f_blocks
                free_pvc_capacity = stat.f_bsize * stat.f_bavail
                used_pvc_capacity = total_pvc_capacity - free_pvc_capacity

                # PVC Inodes
                total_pvc_inodes = stat.f_files
                free_pvc_inodes = stat.f_favail
                used_pvc_inodes = total_pvc_inodes - free_pvc_inodes

                pvc = {
                    "pvc_name": pvcname,
                    "pvc_size": pvc[1],
                    "total_pvc_capacity": total_pvc_capacity,
                    "free_pvc_capacity": free_pvc_capacity,
                    "used_pvc_capacity": used_pvc_capacity,
                    "total_pvc_inodes": total_pvc_inodes,
                    "free_pvc_inodes": free_pvc_inodes,
                    "used_pvc_inodes": used_pvc_inodes
                }

                storage["pvc"].append(pvc)
            data["storages"].append(storage)

    return data


if __name__ == "__main__":

    logging_setup()

    uvicorn.run("exporter:app", host="0.0.0.0", port=8050, log_level="info")
