import json
import urllib3
import uvicorn
import logging
from utils import execute, CommandError
from fastapi import FastAPI
from prometheus_client import make_asgi_app, start_http_server, Gauge
from kadalulib import logf, logging_setup

# Define all metrics here
total_capacity_bytes = Gauge('kadalu_storage_total_capacity_bytes', 'Kadalu Total Storage Capacity', ['name'])
capacity_used_bytes = Gauge('kadalu_storage_used_capacity_bytes', 'Kadalu Total Storage Used Capacity', ['name'])
capacity_free_bytes = Gauge('kadalu_storage_free_capacity_bytes', 'Kadalu Total Storage Free Capacity', ['name'])

total_inodes = Gauge('kadalu_storage_total_inodes', 'Kadalu Total Storage Inodes', ['name'])
used_inodes = Gauge('kadalu_storage_used_inodes', 'Kadalu Total Storage Inodes Used', ['name'])
free_inodes = Gauge('kadalu_storage_free_inodes', 'Kadalu Total Storage Inodes Free', ['name'])

total_pvc_capacity_bytes = Gauge('kadalu_pvc_total_capacity_bytes', 'Kadalu Total PVC Capacity', ['name'])
capacity_pvc_used_bytes = Gauge('kadalu_pvc_used_capacity_bytes', 'Kadalu Total PVC Used Capacity', ['name'])
capacity_pvc_free_bytes = Gauge('kadalu_pvc_free_capacity_bytes', 'Kadalu Total PVC Free Capacity', ['name'])

total_pvc_inodes = Gauge('kadalu_pvc_total_inodes', 'Kadalu Total Total PVC Inodes', ['name'])
used_pvc_inodes = Gauge('kadalu_pvc_used_inodes', 'Kadalu Total Used PVC Inodes', ['name'])
free_pvc_inodes = Gauge('kadalu_pvc_free_inodes', 'Kadalu Total Free PVC Inodes', ['name'])


http = urllib3.PoolManager()
app = FastAPI()

def get_pod_ip_data():
    """ Get IP Addresses of all Pods in kadalu namespace """

    cmd = ["kubectl", "get", "pods", "-nkadalu", "-ojson"]

    try:
        resp = execute(cmd)
        data = json.loads(resp.stdout)
        pod_ip_data = {}

        for item in data["items"]:
            pod_name = item["metadata"]["name"]
            ip_addr = item["status"]["podIP"]
            pod_ip_data[pod_name] = ip_addr

        return pod_ip_data

    except CommandError as err:
        logging.error(logf(
            "Failed to get IP Addresses of pods in kadalu namespace",
            error=err
        ))
        return None


class Metrics:
    def __init__(self):
        self.operator = {}
        self.storages = []
        self.pods = []


def get_operator_data(metrics):
    """Update operator metrics"""

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

    pod = {
        "pod_name": pod_name,
        "memory_usage_in_bytes": int(memory_usage_in_bytes),
        "cpu_usage_in_nanoseconds": int(cpu_usage_in_nanoseconds)
    }

    metrics.pods.append(pod)
    return metrics


def collect_all_metrics():
    """ Collect all metrics data from different listening pods """

    metrics = Metrics()

    metrics = get_operator_data(metrics)

    pod_ip_data = get_pod_ip_data()

    for pod_name, ip_addr in pod_ip_data.items():

        #Skip GET request to operator
        # operator_str = "operator-"
        # if key != None and operator_str in str(key):
        #     continue

        # For now GET request only from csi-provisioner & server pods
        provisioner_str = "provisioner"
        server_str = "server"
        if provisioner_str in str(pod_name) or server_str in str(pod_name):

            r = http.request('GET', 'http://'+ ip_addr +':8050/_api/metrics')
            if r.status == 200:

                # Server has no storages details for now
                if provisioner_str in str(pod_name):
                    metrics.storages = json.loads(r.data)["storages"]
                metrics.pods.append(json.loads(r.data)["pod"])

    return metrics


def collect_and_set_prometheus_metrics():
    """ Add all metrics data to prometheus labels """

    metrics = collect_all_metrics()
    for storage in metrics.storages:

        total_capacity_bytes.labels(storage["name"]).set(storage["total_capacity"])
        capacity_used_bytes.labels(storage["name"]).set(storage["used_capacity"])
        capacity_free_bytes.labels(storage["name"]).set(storage["free_capacity"])

        total_inodes.labels(storage["name"]).set(storage["total_inodes"])
        used_inodes.labels(storage["name"]).set(storage["used_inodes"])
        free_inodes.labels(storage["name"]).set(storage["free_inodes"])

        for pvc in storage["pvc"]:

            total_pvc_capacity_bytes.labels(pvc["name"]).set(pvc["total_pvc_capacity"])
            capacity_pvc_used_bytes.labels(pvc["name"]).set(pvc["cused_pvc_capacity"])
            capacity_pvc_free_bytes.labels(pvc["name"]).set(pvc["free_pvc_capacity"])

            total_pvc_inodes.labels(pvc["name"]).set(pvc["total_pvc_inodes"])
            used_pvc_inodes.labels(pvc["name"]).set(pvc["used_pvc_inodes"])
            free_pvc_inodes.labels(pvc["name"]).set(pvc["free_pvc_inodes"])


@app.middleware("http")
async def collect_metrics(request, call_next):
    """ Collect metrics and set data to prometheus at /metrics """
    if request.url.path == "/metrics":
        collect_and_set_prometheus_metrics()

    return await call_next(request)


@app.get("/metrics.json")
async def metrics_json():
    """ Return collected metrics in JSON format at /metrics.json """
    return collect_all_metrics()

logging_setup()
app.mount("/metrics", make_asgi_app())

# RUN THIS ON OPERATOR TERMINAL at '/kadalu' TO START METRICS EXPORTER PROCESS
# uvicorn exporter:app --port XXXX
