import json
import urllib3
import uvicorn
import logging
from utils import execute, CommandError
from fastapi import FastAPI
from prometheus_client import make_asgi_app, start_http_server, Gauge
from kadalulib import logf, logging_setup
import metrics as storage_metrics

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

            # Skip pods which are not "Running"
            #if item["status"]["phase"] == "Pending":
            #    continue

            pod_name = item["metadata"]["name"]
            pod_phase = item["status"]["phase"]
            ip_addr = item["status"]["podIP"]

            pod_ip_data[pod_name] = {
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
                    number_of_ready_containers = number_of_ready_containers + 1
                    start_time = container["state"]["running"].get("startedAt")

                container = {
                    "container_name": container_name,
                    "is_ready": is_ready,
                    "is_started": is_started,
                    "start_time": start_time
                }
                containers.append(container)

            pod_ip_data[pod_name]["total_number_of_containers"] = len(containers)
            pod_ip_data[pod_name]["number_of_ready_containers"] = number_of_ready_containers
            pod_ip_data[pod_name]["containers"] = containers

        logging.info(logf(
            "Pod Data",
            pod_ip_data=pod_ip_data
        ))

        return pod_ip_data

    except (CommandError, KeyError) as err:
        logging.error(logf(
            "Failed to get IP Addresses of pods in kadalu namespace",
            error=err
        ))



class Metrics:
    def __init__(self):
        self.operator = {}
        self.storages = []
        self.provisioner = {}
        self.nodeplugins = []


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
        memory_usage_in_bytes = int(memory_fd.read().strip())

    cpu_usage_file_path = '/sys/fs/cgroup/cpu/cpuacct.usage'
    with open(cpu_usage_file_path, 'r') as cpu_fd:
        cpu_usage_in_nanoseconds = int(cpu_fd.read().strip())

    metrics.operator = {
        "pod_name": pod_name,
        "memory_usage_in_bytes": memory_usage_in_bytes,
        "cpu_usage_in_nanoseconds": cpu_usage_in_nanoseconds
    }

    return metrics


def collect_brick_data():
    """ Collects all bricks related data from configmap for all volumes """

    cmd = ["kubectl", "get", "configmap", "kadalu-info", "-nkadalu", "-ojson"]

    try:
        resp = execute(cmd)
        config_data = json.loads(resp.stdout)

        data = config_data['data']

        key_data = []
        brick_data = {}

        for key, value in data.items():
            if key.endswith('info'):
                key_data.append(key)

        for key in key_data:
            storage_data = json.loads(data[key])
            brick_data[key.rstrip(".info")] = storage_data.get("bricks")
            #brick_data.append(storage_data.get("bricks"))

        return brick_data

    except CommandError as err:
        logging.error(logf(
            "Failed to get brick data from configmap",
            error=err
        ))
        return None


def collect_all_metrics():
    """ Collect all metrics data from different listening pods """

    metrics = Metrics()

    metrics = get_operator_data(metrics)

    pod_ip_data = get_pod_ip_data()

    storage_count = 0
    for k,v in pod_ip_data.items():

        #Skip GET request to operator
        # operator_str = "operator-"
        if "operator" in k:
            metrics.operator.update(v)
            continue

        # For now GET request only from csi-provisioner, nodeplugin & server pods
        nodeplugin_str = "nodeplugin"
        provisioner_str = "provisioner"
        server_str = "server"

        r = http.request('GET', 'http://'+ v["ip_address"] +':8050/_api/metrics')
        if r.status == 200:

            if nodeplugin_str in k:

                metrics.nodeplugins.append(json.loads(r.data)["pod"])
                # Is for reqd here?? Maybe yes... Multiple node not tested
                for nodeplugin in metrics.nodeplugins:
                    if nodeplugin["pod_name"] in k:
                        nodeplugin.update(v)

            if provisioner_str in k:

                #storage_pool_name = json.loads(r.data)["storages"]["name"]
                #metrics.storages[storage_pool_name] = json.loads(r.data)["storages"]
                metrics.storages = json.loads(r.data)["storages"]
                metrics.provisioner.update(json.loads(r.data)["pod"])
                metrics.provisioner.update(v)
                logging.info(logf(
                    "storages in provisioner",
                    storages=metrics.storages
                ))

            if server_str in k:
                brick_data = collect_brick_data()
                logging.info(logf(
                    "v value",
                    v=v,
                    storage_count=storage_count,
                    collect_brick_data=brick_data
                ))

                for storage in metrics.storages:
                # TODO
                # add bricks by checking if current k(pod) is there in any of the storage pools
                # add pod details of each bricks["pod_phase", "container statues etc"] from collect bricks data
                # add pod cpu, memory usage from pod_ip_data rename to pod_data later


                    if storage["name"] in k:
                        if not storage.get("bricks"):
                            storage.update({"bricks": brick_data[storage["name"]]})
                        for brick in storage["bricks"]:
                            brick_name = brick["node"].rstrip("."+storage["name"])
                            if brick_name in k:
                                logging.info(logf(
                                    "inside if brick_name in k",
                                    k=k,
                                    brick=brick,
                                    brick_name=brick_name
                                ))
                                # why getting updated to only last brick when bricks > 1
                                brick.update(json.loads(r.data)["pod"])
                                brick.update(v)



                # 1st try with arrays as brick_data
                # else
                # storage_name = metrics.storages[storage_count]["name"]
                # if storage_name in k:
                #   metrics.storage[storage_count].update({"bricks": brick_data[storage_name]})
                # if str(metrics.storages[storage_count]["name"]) in k:
                #     metrics.storages[storage_count].update({"bricks": brick_data[storage_count]})

                #     #check node name[brick name + storage-pool name] in bricks and add respective pod details
                #     bricks = metrics.storages[storage_count]["bricks"]
                #     for brick in bricks:
                #         brick_name = brick["node"].rstrip("."+metrics.storages[storage_count]["name"])
                #         logging.info(logf(
                #             "brick_name",
                #             brick_name=brick_name,
                #             k=k,
                #             type=type(brick)
                #         ))
                #         if str(brick_name) in k:
                #             logging.info(logf(
                #                 "inside if of brick check",
                #                 brick_name=brick_name,
                #                 k=k
                #             ))
                #             brick.update(v)
                #             storage_count+=1


                ## Problem is in replica 3
                ## there are 3 server pods as in 'k,v' coming in
                ## but storage_count will update +1 every time, it should not.
                ## Since there is only one storage in top level which is storage[0]
                ## up

                #metrics.storages[storage_count].update(v)
                #metrics.storages.insert(storage_count,update(v))
                #storage_count = storage_count + 1
                #server_pod_data = json.loads(r.data)["pod"]
                # if str(metrics.storages[storage_count].get("name")) in str(server_pod_data.get("pod_name")):

                #     for k,v in metrics.storages[storage_count]["bricks"]:
                #         if
                #     metrics.storages[storage_count]["bricks"].update(server_pod_data)

    logging.info(logf(
        "metrics output",
        metrics=metrics.storages
    ))
    return metrics


def collect_and_set_prometheus_metrics():
    """ Add all metrics data to prometheus labels """

    metrics = collect_all_metrics()

    storage_metrics.memory_usage.labels(
        metrics.operator["pod_name"]).set(metrics.operator["memory_usage_in_bytes"])
    storage_metrics.cpu_usage.labels(
        metrics.operator["pod_name"]).set(metrics.operator["cpu_usage_in_nanoseconds"])

    storage_metrics.memory_usage.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["memory_usage_in_bytes"])
    storage_metrics.cpu_usage.labels(
        metrics.provisioner["pod_name"]).set(metrics.provisioner["cpu_usage_in_nanoseconds"])

    for nodeplugin in metrics.nodeplugins:
        storage_metrics.memory_usage.labels(
            nodeplugin["pod_name"]).set(nodeplugin["memory_usage_in_bytes"])
        storage_metrics.cpu_usage.labels(
            nodeplugin["pod_name"]).set(nodeplugin["cpu_usage_in_nanoseconds"])

    for storage in metrics.storages:
        storage_metrics.total_capacity_bytes.labels(storage["name"]).set(storage["total_capacity_bytes"])
        storage_metrics.used_capacity_bytes.labels(storage["name"]).set(storage["used_capacity_bytes"])
        storage_metrics.free_capacity_bytes.labels(storage["name"]).set(storage["free_capacity_bytes"])

        storage_metrics.total_inodes.labels(storage["name"]).set(storage["total_inodes"])
        storage_metrics.used_inodes.labels(storage["name"]).set(storage["used_inodes"])
        storage_metrics.free_inodes.labels(storage["name"]).set(storage["free_inodes"])

        for pvc in storage["pvc"]:
            storage_metrics.total_pvc_capacity_bytes.labels(pvc["pvc_name"]).set(pvc["total_pvc_capacity_bytes"])
            storage_metrics.used_pvc_capacity_bytes.labels(pvc["pvc_name"]).set(pvc["used_pvc_capacity_bytes"])
            storage_metrics.free_pvc_capacity_bytes.labels(pvc["pvc_name"]).set(pvc["free_pvc_capacity_bytes"])

            storage_metrics.total_pvc_inodes.labels(pvc["pvc_name"]).set(pvc["total_pvc_inodes"])
            storage_metrics.used_pvc_inodes.labels(pvc["pvc_name"]).set(pvc["used_pvc_inodes"])
            storage_metrics.free_pvc_inodes.labels(pvc["pvc_name"]).set(pvc["free_pvc_inodes"])


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


app.mount("/metrics", make_asgi_app())

if __name__ == "__main__":

    logging_setup()

    uvicorn.run("exporter:app", host="0.0.0.0", port=9003, log_level="info")
