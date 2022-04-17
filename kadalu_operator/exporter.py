"""
Exporter gathers various metrics from various kadalu pod exporters
by connecting to their respective API Endpoints through IP
and makes available these aggregated metrics in JSON as metrics.json
and Prometheus as metrics at PORT=8050
"""

import json
import os
import logging
import requests
import uvicorn

from fastapi import FastAPI
from prometheus_client import make_asgi_app
import metrics as storage_metrics
from kadalulib import logf, logging_setup
from utils import CommandError, execute

metrics_app = FastAPI()

class Metrics:
    """ Metrics class with Kadalu Components """
    def __init__(self):
        self.operator = {}
        self.storages = []
        self.provisioner = {}
        self.nodeplugins = []


def get_pod_data():
    """ Get pod and container info of all Pods in kadalu namespace """

    cmd = ["kubectl", "get", "pods", "-nkadalu", "-ojson"]

    try:
        resp = execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to execute the command",
            command=cmd,
            error=err
        ))

    data = json.loads(resp.stdout)
    pod_data = {}

    for item in data["items"]:

        pod_name = item["metadata"]["name"]
        pod_phase = item["status"]["phase"]

        # Handle this as "Internal Server Err"
        ip_addr = "0"
        if "podIP" in item["status"]:
            ip_addr = item["status"]["podIP"]

        pod_data[pod_name] = {
            "ip_address": ip_addr,
            "pod_phase": pod_phase
        }

        # Container Information
        containers = []
        number_of_ready_containers = 0
        for container in item["status"]["containerStatuses"]:

            container_name = container["name"]
            is_ready = container["ready"]
            is_started = container["started"]
            start_time = 0

            if is_ready and is_started:
                number_of_ready_containers += 1
                start_time = container["state"]["running"].get("startedAt")

            container = {
                "container_name": container_name,
                "is_ready": is_ready,
                "is_started": is_started,
                "start_time": start_time
            }
            containers.append(container)

        pod_data[pod_name]["total_number_of_containers"] = len(containers)
        pod_data[pod_name]["number_of_ready_containers"] = number_of_ready_containers
        pod_data[pod_name]["containers"] = containers

    return pod_data


def get_storage_config_data():
    """
    Collects all storage related data such as list of storages, type data, bricks
    related data from configmap for all volumes
    """

    cmd = ["kubectl", "get", "configmap", "kadalu-info", "-nkadalu", "-ojson"]

    storage_config_data = {}
    try:
        resp = execute(cmd)
        config_data = json.loads(resp.stdout)

        data = config_data['data']

        list_of_storages = []
        brick_data = {}
        storage_type_data = {}

        for key, value in data.items():
            if key.endswith('info'):
                key = key.rstrip(".info")
                value = json.loads(value)

                # TODO: Add metrics for external storage type
                if value["type"] == "External":
                    continue

                list_of_storages.append(key)
                brick_data[key] = value["bricks"]
                storage_type_data[key] = value["type"]

        storage_config_data["list_of_storages"] = list_of_storages
        storage_config_data["brick_data"] = brick_data
        storage_config_data["storage_type_data"] = storage_type_data

        return storage_config_data

    except CommandError as err:
        logging.error(logf(
            "Failed to get brick data from configmap",
            error=err
        ))
        return None


def set_default_values(metrics):
    """
    Set default values for all pods to display default
    values in case of unable to reach the pod api
    """

    metrics.operator.update({"pod_phase": "unknown"})
    metrics.provisioner.update({
         "pod_name": "kadalu-csi-provisioner-0",
         "pod_phase": "unknown",
         "memory_usage_in_bytes": -1,
         "cpu_usage_in_nanoseconds": -1,
         "total_number_of_containers": -1,
         "number_of_ready_containers": -1,
    })

    pod_data = get_pod_data()
    for pod_name in pod_data.keys():
        if "nodeplugin" in pod_name:
            metrics.nodeplugins.append({
                "pod_name": pod_name,
                "pod_phase": "unknown",
                "memory_usage_in_bytes": -1,
                "cpu_usage_in_nanoseconds": -1,
                "total_number_of_containers": -1,
                "number_of_ready_containers": -1,
            })

    storage_config_data = get_storage_config_data()
    list_of_storages = storage_config_data["list_of_storages"]
    storage_type_data = storage_config_data["storage_type_data"]
    brick_data = storage_config_data["brick_data"]

    for storage in list_of_storages:

        storage_pool = {
            "name": storage,
            "type": storage_type_data[storage],
            "total_capacity_bytes": -1,
            "free_capacity_bytes": -1,
            "used_capacity_bytes": -1,
            "total_inodes": -1,
            "free_inodes": -1,
            "used_inodes": -1,
            "pvc": []
        }

        storage_pool.update({"bricks": brick_data[storage]})
        for brick in storage_pool.get("bricks"):
            brick.update({
                "pod_phase": "unknown",
                "memory_usage_in_bytes": -1,
                "cpu_usage_in_nanoseconds": -1,
                "total_number_of_containers": -1,
                "number_of_ready_containers": -1,
            })

        metrics.storages.append(storage_pool)


def set_operator_data(metrics):
    """Update operator related metrics"""

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

    metrics.operator = {
        "memory_usage_in_bytes": memory_usage_in_bytes,
        "cpu_usage_in_nanoseconds": cpu_usage_in_nanoseconds
    }


def set_nodeplugin_data(response, metrics, pod_name, pod_details):
    """ Update nodeplugin related metrics"""

    for nodeplugin in metrics.nodeplugins:
        if nodeplugin["pod_name"] in pod_name:
            nodeplugin.update(response.json()["pod"])
            nodeplugin.update(pod_details)


def set_provisioner_data(response, metrics, pod_name, pod_details):
    """ Update provisioner related metrics"""

    # Data from provisioner is the source of truth
    # Update only those metrics.storages data which is present in
    # provisioner, rest will remain with default values.
    storage_data_from_csi = response.json()["storages"]

    for index, storage in enumerate(metrics.storages):
        try:
            if storage["name"] == storage_data_from_csi[index]["name"]:
                storage.update(storage_data_from_csi[index])

        except IndexError:
            # skip comparing rest of storages in metrics[default],
            # since storage_data_from_csi has reached its end,
            # and it contains no more data from healthy storage-pools
            logging.debug(logf(
                "Reached end of list of storages from csi. Skip comparing the rest."
            ))
            break

    metrics.provisioner.update({"pod_name": pod_name})
    metrics.provisioner.update(response.json()["pod"])
    metrics.provisioner.update(pod_details)


def set_server_data(response, metrics, pod_name, pod_details):
    """ Updates server[storage-pool(s) & its brick(s)] related metrics"""

    # Assumes CSI Pod is healthy and able to retrieve server data from its mount points,
    # Else default values of storages will be used.
    for storage in metrics.storages:
        if storage["name"] in pod_name:

            for brick in storage["bricks"]:
                brick_name = brick["node"].rstrip("."+storage["name"])

                if brick_name in pod_name:
                    brick.update(response.json()["pod"])
                    brick.update(pod_details)


def collect_all_metrics():
    """ Collect all metrics data from different listening pods """

    metrics = Metrics()

    set_default_values(metrics)
    set_operator_data(metrics)

    pod_data = get_pod_data()
    for pod_name, pod_details in pod_data.items():

        # skip GET request to operator
        if "operator" in pod_name:
            metrics.operator.update({"pod_name": pod_name})
            metrics.operator.update(pod_details)
            continue

        try:
            response = requests.get(
                'http://'+ pod_details["ip_address"] +':8050/_api/metrics',
                timeout=10)

            if response.status_code == 200:
                if "nodeplugin" in pod_name:
                    set_nodeplugin_data(response, metrics, pod_name, pod_details)

                if "provisioner" in pod_name:
                    set_provisioner_data(response, metrics, pod_name, pod_details)

                if "server" in pod_name:
                    set_server_data(response, metrics, pod_name, pod_details)


        except requests.exceptions.RequestException as err:
            logging.error(logf(
                "Unable to reach the pod, displaying only default values",
                pod_name=pod_name,
                error=err
            ))

    return metrics


def collect_and_set_prometheus_metrics():
    """ Add all metrics data to prometheus labels """

    metrics = collect_all_metrics()

    # Operator Metrics
    storage_metrics.memory_usage.labels(
        metrics.operator["pod_name"]).set(metrics.operator["memory_usage_in_bytes"])
    storage_metrics.cpu_usage.labels(
        metrics.operator["pod_name"]).set(metrics.operator["cpu_usage_in_nanoseconds"])

    storage_metrics.total_number_of_containers.labels(
        metrics.operator["pod_name"]).set(metrics.operator["total_number_of_containers"])
    storage_metrics.number_of_ready_containers.labels(
        metrics.operator["pod_name"]).set(metrics.operator["number_of_ready_containers"])

    # Provisioner Metrics
    storage_metrics.memory_usage.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["memory_usage_in_bytes"])
    storage_metrics.cpu_usage.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["cpu_usage_in_nanoseconds"])

    storage_metrics.total_number_of_containers.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["total_number_of_containers"])
    storage_metrics.number_of_ready_containers.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["number_of_ready_containers"])

    # Nodeplugin(s) Metrics
    for nodeplugin in metrics.nodeplugins:
        storage_metrics.memory_usage.labels(
            nodeplugin["pod_name"]).set(nodeplugin["memory_usage_in_bytes"])
        storage_metrics.cpu_usage.labels(
            nodeplugin["pod_name"]).set(nodeplugin["cpu_usage_in_nanoseconds"])

        storage_metrics.total_number_of_containers.labels(
            nodeplugin["pod_name"]).set(nodeplugin["total_number_of_containers"])
        storage_metrics.number_of_ready_containers.labels(
            nodeplugin["pod_name"]).set(nodeplugin["number_of_ready_containers"])

    # Storage(s) Metrics
    for storage in metrics.storages:
        storage_metrics.total_capacity_bytes.labels(
            storage["name"]).set(storage["total_capacity_bytes"])
        storage_metrics.used_capacity_bytes.labels(
            storage["name"]).set(storage["used_capacity_bytes"])
        storage_metrics.free_capacity_bytes.labels(
            storage["name"]).set(storage["free_capacity_bytes"])

        storage_metrics.total_inodes.labels(
            storage["name"]).set(storage["total_inodes"])
        storage_metrics.used_inodes.labels(
            storage["name"]).set(storage["used_inodes"])
        storage_metrics.free_inodes.labels(
            storage["name"]).set(storage["free_inodes"])

        for pvc in storage["pvc"]:
            storage_metrics.total_pvc_capacity_bytes.labels(
                pvc["pvc_name"]).set(pvc["total_pvc_capacity_bytes"])
            storage_metrics.used_pvc_capacity_bytes.labels(
                pvc["pvc_name"]).set(pvc["used_pvc_capacity_bytes"])
            storage_metrics.free_pvc_capacity_bytes.labels(
                pvc["pvc_name"]).set(pvc["free_pvc_capacity_bytes"])

            storage_metrics.total_pvc_inodes.labels(
                pvc["pvc_name"]).set(pvc["total_pvc_inodes"])
            storage_metrics.used_pvc_inodes.labels(
                pvc["pvc_name"]).set(pvc["used_pvc_inodes"])
            storage_metrics.free_pvc_inodes.labels(
                pvc["pvc_name"]).set(pvc["free_pvc_inodes"])

        for brick in storage["bricks"]:
            storage_metrics.memory_usage.labels(
                brick["node"].rstrip("."+storage["name"])).set(brick["memory_usage_in_bytes"])
            storage_metrics.cpu_usage.labels(
                brick["node"].rstrip("."+storage["name"])).set(brick["cpu_usage_in_nanoseconds"])

            storage_metrics.total_number_of_containers.labels(
                brick["node"].rstrip("."+storage["name"])).set(brick["total_number_of_containers"])
            storage_metrics.number_of_ready_containers.labels(
                brick["node"].rstrip("."+storage["name"])).set(brick["number_of_ready_containers"])


@metrics_app.middleware("http")
async def collect_metrics(request, call_next):
    """ Collect metrics and set data to prometheus at /metrics """
    if request.url.path == "/metrics":
        collect_and_set_prometheus_metrics()

    return await call_next(request)


@metrics_app.get("/metrics.json")
async def metrics_json():
    """ Return collected metrics in JSON format at /metrics.json """
    return collect_all_metrics()


metrics_app.mount("/metrics", make_asgi_app())

if __name__ == "__main__":

    logging_setup()
    logging.info(logf(
        "Started metrics exporter process at port 8050"
    ))

    uvicorn.run("exporter:metrics_app", host="0.0.0.0", port=8050, log_level="info")
