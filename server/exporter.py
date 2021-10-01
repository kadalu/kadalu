import logging
import uvicorn
from fastapi import FastAPI
from kadalulib import logging_setup, logf

app = FastAPI()

@app.get("/_api/metrics")
def metrics():
    """
    Gathers storage and pvcs metrics.
    Starts process by exposing the data collected in port 8050 at '/_api/metrics'.
    """

    data = {
        "pod": {}
    }

    memory_usage_in_bytes = 0
    cpu_usage_in_nanoseconds = 0

    memory_usage_file_path = '/sys/fs/cgroup/memory/memory.usage_in_bytes'
    with open(memory_usage_file_path, 'r') as memory_fd:
        memory_usage_in_bytes = int(memory_fd.read().strip())

    cpu_usage_file_path = '/sys/fs/cgroup/cpu/cpuacct.usage'
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

    uvicorn.run("exporter:app", host="0.0.0.0", port=8050, log_level="info")
