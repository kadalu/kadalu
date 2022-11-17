import logging
import os
import re

import uvicorn
from fastapi import FastAPI
from kadalulib import logf, logging_setup

metrics_app = FastAPI()

@metrics_app.get("/_api/metrics")
def metrics():
    """
    Gathers storage and pvcs metrics.
    Starts process by exposing the data collected in port 8050 at '/_api/metrics'.
    """

    data = {
        "pod": {}
    }

    memory_usage_in_bytes = 0
    # Return -1 if unable to fetch 'cgroup' data,
    # until new method is found to get CPU & Memory data in LXD containers.
    memory_usage_in_bytes = -1
    cpu_usage_in_nanoseconds = -1

    if os.path.exists('/sys/fs/cgroup/cgroup.controllers'):  # If exists -> cgroup2
        memory_usage_file_path = '/sys/fs/cgroup/system.slice/memory.current'
        cpu_usage_file_path = '/sys/fs/cgroup/cpu.stat'
    else:
       memory_usage_file_path = '/sys/fs/cgroup/memory/memory.usage_in_bytes'
       cpu_usage_file_path = '/sys/fs/cgroup/cpu/cpuacct.usage'

    if os.path.exists(memory_usage_file_path):
        with open(memory_usage_file_path, 'r') as memory_fd:
            memory_usage_in_bytes = int(memory_fd.read().strip())

    if os.path.exists('/sys/fs/cgroup/cgroup.controllers'):  # If exists -> cgroup2
        if os.path.exists(cpu_usage_file_path):
            with open(cpu_usage_file_path, 'r') as cpu_fd:
                for line in cpu_fd: # loop over all lines till we find usage_usec
                    if re.search('usage_usec', line):
                        cpu_usage_in_nanoseconds = int(line.split(' ')[1]) * 1000 # microseconds to nanoseconds
    else:
        if os.path.exists(cpu_usage_file_path):
            with open(cpu_usage_file_path, 'r') as cpu_fd:
                cpu_usage_in_nanoseconds = int(cpu_fd.read().strip())

    data["pod"] = {
        "memory_usage_in_bytes": memory_usage_in_bytes,
        "cpu_usage_in_nanoseconds": cpu_usage_in_nanoseconds
    }

    return data


if __name__ == "__main__":

    logging_setup()
    logging.info(logf(
        "Started metrics exporter process at port 8050"
    ))

    uvicorn.run("exporter:metrics_app", host="0.0.0.0", port=8050, log_level="info")
