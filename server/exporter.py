from fastapi import FastAPI
import uvicorn

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
    
    return data


if __name__ == "__main__":
    uvicorn.run("exporter:app", host="0.0.0.0", port=8050, log_level="info")
