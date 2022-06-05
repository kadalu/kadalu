"""
KaDalu Operator: Once started, deploys required CSI drivers,
bootstraps the ConfigMap and waits for the CRD update to create
Server pods
"""
import json
import logging
import os
import re
import sys
import time
import uuid

import urllib3
from jinja2 import Template
from kadalulib import CommandException
from kadalulib import execute as lib_execute
from kadalulib import (is_host_reachable, logf, logging_setup,
                       send_analytics_tracker)
from kubernetes import client, config, watch
from urllib3.exceptions import NewConnectionError, ProtocolError
from utils import CommandError
from utils import execute as utils_execute

NAMESPACE = os.environ.get("KADALU_NAMESPACE", "kadalu")
VERSION = os.environ.get("KADALU_VERSION", "latest")
K8S_DIST = os.environ.get("K8S_DIST", "kubernetes")
IMAGES_HUB = os.environ.get("IMAGES_HUB", "docker.io")
KUBELET_DIR = os.environ.get("KUBELET_DIR")
VERBOSE = os.environ.get("VERBOSE", "no")
MANIFESTS_DIR = "/kadalu/templates"
KUBECTL_CMD = "/usr/bin/kubectl"
KADALU_CONFIG_MAP = "kadalu-info"
CSI_POD_PREFIX = "csi-"
STORAGE_CLASS_NAME_PREFIX = "kadalu."
# TODO: Add ThinArbiter
VALID_PV_RECLAIM_POLICY_TYPES = ["delete", "archive", "retain"]
POOL_TYPE_EXTERNAL = "External"
POOL_TYPE_REPLICA_1 = "Replica1"
POOL_TYPE_REPLICA_2 = "Replica2"
POOL_TYPE_REPLICA_3 = "Replica3"
POOL_MODE_NATIVE = "Native"
POOL_MODE_EXTERNAL_GLUSTER = "ExternalGluster"
POOL_MODE_EXTERNAL_KADALU = "ExternalKadalu"
POOL_TYPE_DISPERSE = "Disperse"
VALID_POOL_TYPES = [
    POOL_TYPE_REPLICA_1, POOL_TYPE_REPLICA_2, POOL_TYPE_REPLICA_3,
    POOL_TYPE_DISPERSE, POOL_TYPE_EXTERNAL
]
VALID_POOL_MODES = [
    POOL_MODE_NATIVE, POOL_MODE_EXTERNAL_GLUSTER,
    POOL_MODE_EXTERNAL_KADALU
]
CREATE_CMD = "create"
APPLY_CMD = "apply"
DELETE_CMD = "delete"
PATCH_CMD = "patch"

NODE_PLUGIN = "kadalu-csi-nodeplugin"

def template(filename, **kwargs):
    """Substitute the template with provided fields"""
    content = ""
    with open(filename + ".j2") as template_file:
        content = template_file.read()

    if kwargs.get("render", False):
        return Template(content).render(**kwargs)

    return Template(content).stream(**kwargs).dump(filename)


def storage_units_validation(storage_units):
    """Validate Storage Unit path and node options"""
    ret = True
    for idx, storage_unit in enumerate(storage_units):
        if not ret:
            break

        if storage_unit.get("pvc", None) is not None:
            continue

        if storage_unit.get("path", None) is None and \
           storage_unit.get("device", None) is None:
            logging.error(logf("Storage path/device not specified",
                               number=idx+1))
            ret = False

        if storage_unit.get("node", None) is None:
            logging.error(logf("Storage node not specified", number=idx+1))
            ret = False

    return ret


def spec_keys_valid(details, keys):
    valid = True
    for key in keys:
        if details.get(key, None) is None:
            valid = False
            break

    return valid


def validate_ext_mode_details(obj):
    """Validate external Pool details"""
    valid = True
    if obj["spec"]["mode"] == POOL_MODE_EXTERNAL_GLUSTER:
        details = obj["spec"].get("gluster_volume", None)
        if not details:
            logging.error(logf("External Gluster Volume details not given."))
            return False
        valid = spec_keys_valid(details, ["hosts", "volume_name"])
    else:
        details = obj["spec"].get("kadalu_volume", None)
        if not details:
            logging.error(logf("External Kadalu Volume details not given."))
            return False
        valid = spec_keys_valid(
            details, ["mgr_url", "pool_name", "volume_name"])

    if not valid:
        logging.error(logf("Incomplete Pool details provided."))
        return False

    logging.debug(logf("External Storage %s successfully validated" % \
                       obj["metadata"].get("name", "<unknown>")))
    return True


# pylint: disable=too-many-return-statements
# pylint: disable=too-many-branches
def validate_pool_request(obj):
    """Validate the Pool request for Replica options, number of Storage Units etc"""
    if not obj.get("spec", None):
        logging.error("Storage 'spec' not specified")
        return False

    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    if pv_reclaim_policy not in VALID_PV_RECLAIM_POLICY_TYPES:
        logging.error("PV Reclaim Policy not valid")
        return False

    pool_type = obj["spec"].get("type", None)
    pool_mode = obj["spec"].get("mode", None)
    if pool_type is None:
        logging.error("Storage type not specified")
        return False

    if pool_type not in VALID_POOL_TYPES:
        logging.error(logf("Invalid Storage type",
                           valid_types=",".join(VALID_POOL_TYPES),
                           provided_type=pool_type))
        return False

    if pool_mode in [POOL_MODE_EXTERNAL_GLUSTER, POOL_MODE_EXTERNAL_KADALU]:
        return validate_ext_mode_details(obj)

    storage_units = obj["spec"].get("storage", [])
    if not storage_units_validation(storage_units):
        return False

    decommissioned = ""
    subvol_storage_units_count = 1
    if pool_type == POOL_TYPE_REPLICA_2:
        subvol_storage_units_count = 2
    elif pool_type == POOL_TYPE_REPLICA_3:
        subvol_storage_units_count = 3

    if pool_type == POOL_TYPE_DISPERSE:
        disperse_config = obj["spec"].get("disperse", None)
        if disperse_config is None:
            logging.error("Disperse Pool data and redundancy "
                          "count is not specified")
            return False

        data_storage_units = disperse_config.get("data", 0)
        redundancy_storage_units = disperse_config.get("redundancy", 0)
        if data_storage_units == 0 or redundancy_storage_units == 0:
            logging.error("Disperse Pool data or redundancy "
                          "count is not specified")
            return False

        subvol_storage_units_count = data_storage_units + redundancy_storage_units
        # redundancy must be greater than 0, and the total number
        # of storage units must be greater than 2 * redundancy. This
        # means that a dispersed pool must have a minimum of 3 storage units.
        if subvol_storage_units_count <= (2 * redundancy_storage_units):
            logging.error("Invalid redundancy for the Disperse Pool")
            return False

        # stripe_size = (storage_units_count - redundancy) * 512
        # Using combinations of #Storage units/redundancy that give a power
        # of two for the stripe size will make the disperse pool
        # perform better in most workloads because it's more typical
        # to write information in blocks that are multiple of two
        # https://docs.gluster.org/en/latest/Administrator-Guide
        #    /Setting-Up-Volumes/#creating-dispersed-volumes
        if data_storage_units % 2 != 0:
            logging.error("Disperse Configuration is not Optimal")
            return False

    if len(storage_units) % subvol_storage_units_count != 0:
        logging.error("Invalid number of storage directories/devices"
                      " specified")
        return False

    if subvol_storage_units_count > 1:
        for i in range(0, int(len(storage_units) / subvol_storage_units_count)):
            decommissioned = ""
            for k in range(0, subvol_storage_units_count):
                storage_unit_idx = (i * subvol_storage_units_count) + k
                storage_unit = storage_units[storage_unit_idx]
                decom = storage_unit.get("decommissioned", "")
                if k == 0:
                    decommissioned = decom
                    continue
                if decom != decommissioned:
                    logging.error(logf(
                        "All of distribute subvolume should be marked decommissioned",
                        storage_unit=storage_unit, storage_unit_index=storage_unit_idx))
                    return False

    # If we are here, decommissioned option is properly given.

    if pool_type == POOL_TYPE_REPLICA_2:
        tiebreaker = obj["spec"].get("tiebreaker", None)
        if tiebreaker and (not tiebreaker.get("node", None) or
                           not tiebreaker.get("path", None)):
            logging.error(logf("'tiebreaker' provided for replica2 "
                               "config is not valid"))
            return False

    logging.debug(logf("Storage %s successfully validated" % \
                       obj["metadata"].get("name", "<unknown>")))
    return True


def get_storage_unit_device_dir(storage_unit):
    """If custom file is passed as storage unit device then the
    parent directory needs to be mounted as is
    in server container"""
    device_dir = ""
    logging.info(repr(storage_unit))
    storage_unit_dev = storage_unit.get("device", "")
    logging.info(storage_unit_dev)
    if storage_unit_dev != "" and not storage_unit_dev.startswith("/dev/"):
        device_dir = os.path.dirname(storage_unit_dev)

    return device_dir


def get_storage_unit_hostname(pool_name, idx, suffix=True):
    """Storage Unit hostname is <statefulset-name>-<ordinal>.<service-name>
    statefulset name is the one which is visible when the
    `get pods` command is run, so the format used for that name
    is "server-<pool_name>-<idx>". Escape dots from the
    hostname from the input otherwise will become invalid name.
    Service is created with name as Pool name. For example,
    storage_unit_hostname will be "server-spool1-0-0.spool1" and
    server pod name will be "server-spool1-0"
    """
    tmp_pool_name = pool_name.replace("-", "_")
    dns_friendly_pool_name = re.sub(r'\W+', '', tmp_pool_name).replace("_", "-")
    hostname = f"server-{dns_friendly_pool_name}-{idx}"
    if suffix:
        return "{hostname}-0.{pool_name}"

    return hostname


def poolinfo_from_crd_spec(obj):
    pool_type = obj["spec"]["type"]
    pool_mode = obj["spec"].get("mode", POOL_MODE_NATIVE)
    data = {
        "name": obj["metadata"]["name"],
        "mode": pool_mode,
        "id": obj["spec"].get("pool_id", str(uuid.uuid1())),
        "type": pool_type,
        "pvReclaimPolicy": obj["spec"].get("pvReclaimPolicy", "delete"),
        # CRD would set 'native' but just being cautious
        "kadalu_format": obj["spec"].get("kadalu_format", "native")
    }

    if pool_mode == POOL_MODE_EXTERNAL_KADALU:
        details = obj["spec"]["kadalu_volume"]
        data["mgr_url"] = details["mgr_url"]
        data["external_volume_name"] = details["volume_name"]
        data["external_volume_options"] = details.get("volume_options", "")
    elif pool_mode == POOL_MODE_EXTERNAL_GLUSTER:
        details = obj["spec"]["gluster_volume"]
        data["hosts"] = details["hosts"]
        data["external_volume_name"] = details["volume_name"]
        data["external_volume_options"] = details.get("volume_options", "")
    else:
        # Parse Poolinfo of internally managed
        # Kadalu Storage Volumes.
        pool_type = obj["spec"]["type"]
        disperse_config = obj["spec"].get("disperse", {})
        data["options"] = obj["spec"].get("options", "")
        data["disperse"] = {
            "data": disperse_config.get("data", 0),
            "redundancy": disperse_config.get("redundancy", 0)
        }
        data["storage_units"] = []
        storage_units = obj["spec"]["storage"]
        for idx, storage in enumerate(storage_units):
            data["storage_units"].append({
                "path": f"/storages/{data['name']}/storage",
                "kube_hostname": storage.get("node", ""),
                "node": get_storage_unit_hostname(data["name"], idx),
                "node_id": storage.get("node_id", f"node-{idx}" % idx),
                "host_path": storage.get("path", ""),
                "device": storage.get("device", ""),
                "pvc_name": storage.get("pvc", ""),
                "device_dir": get_storage_unit_device_dir(storage),
                "decommissioned": storage.get("decommissioned", ""),
                "index": idx
            })

        if pool_type == POOL_TYPE_REPLICA_2:
            tiebreaker = obj["spec"].get("tiebreaker", None)
            if not tiebreaker:
                logging.warning(logf("No 'tiebreaker' provided for replica2 "
                                     "config. Using default tie-breaker.kadalu.io:/mnt",
                                     pool_name=data["name"]))
                # Add default tiebreaker if no tie-breaker option provided
                tiebreaker = {
                    "node": "tie-breaker.kadalu.io",
                    "path": "/mnt",
                }
                if not tiebreaker.get("port", None):
                    tiebreaker["port"] = 24007

            data["tiebreaker"] = tiebreaker

    return data


def is_pool_mode_external(mode):
    return mode in [POOL_MODE_EXTERNAL_GLUSTER, POOL_MODE_EXTERNAL_KADALU]


def upgrade_storage_pods(core_v1_client):
    """
    Upgrade the Storage pods after operator pod upgrade
    """
    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    for key in configmap_data.data:
        if ".info" not in key:
            continue

        # TODO: Upgrade poolinfo and call Kadalu Storage Volume API/CLI

        pool_name = key.replace('.info', '')
        data = json.loads(configmap_data.data[key])

        logging.info(logf("config map", pool_name=pool_name, data=data))
        if is_pool_mode_external(data['mode']):
            # nothing to be done for upgrade, say we are good.
            logging.debug(logf(
                "pool type external, nothing to upgrade",
                pool_name=pool_name,
                data=data))
            continue

        if data['type'] == POOL_TYPE_REPLICA_1:
            # No promise of high availability, upgrade
            logging.debug(logf(
                "pool type Replica1, calling upgrade",
                pool_name=pool_name,
                data=data))
            # TODO: call upgrade

        # Replica 2 and Replica 3 needs to check for self-heal
        # count 0 before going ahead with upgrade.

        # glfsheal volname --file-path=/template/file info-summary
        obj = {}
        obj["metadata"] = {}
        obj["spec"] = {}
        obj["metadata"]["name"] = pool_name
        obj["spec"]["type"] = data['type']
        obj["spec"]["pvReclaimPolicy"] = data.get("pvReclaimPolicy", "delete")
        obj["spec"]["pool_id"] = data["pool_id"]
        obj["spec"]["storage"] = []

        # Need this loop so below array can be constructed in the proper order
        for val in data["storage_units"]:
            obj["spec"]["storage"].append({})

        # Set Node ID for each storage device from configmap
        for val in data["storage_units"]:
            idx = val["storage_unit_index"]

            obj["spec"]["storage"][idx]["node_id"] = val["node_id"]
            obj["spec"]["storage"][idx]["path"] = val["host_storage_unit_path"]
            obj["spec"]["storage"][idx]["node"] = val["kube_hostname"]
            obj["spec"]["storage"][idx]["device"] = val["storage_unit_device"]
            obj["spec"]["storage"][idx]["pvc"] = val["pvc_name"]

        if data['type'] == POOL_TYPE_REPLICA_2:
            if "tie-breaker.kadalu.io" not in data['tiebreaker']['node']:
                obj["spec"]["tiebreaker"] = data['tiebreaker']

        # TODO: call upgrade_pods_with_heal_check() here
        deploy_server_pods(obj)


def update_config_map(core_v1_client, obj):
    """
    Poolinfo of new Pool is generated and updated to ConfigMap
    """
    pool_name = obj["metadata"]["name"]
    pool_type = obj["spec"]["type"]
    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    pool_id = obj["spec"]["pool_id"]
    disperse_config = obj["spec"].get("disperse", {})

    data = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "name": pool_name,
        "id": pool_id,
        "kadalu_format": obj["spec"].get("kadalu_format", "native"),
        "type": pool_type,
        "pv_reclaim_policy" : pv_reclaim_policy,
        "storage_units": [],
        "disperse": {
            "data": disperse_config.get("data", 0),
            "redundancy": disperse_config.get("redundancy", 0)
        },
        "options": obj["spec"].get("options", {})
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    # For each, storage unit add storage unit path and node id
    storage_units = obj["spec"]["storage"]
    for idx, storage in enumerate(storage_units):
        data["storage_units"].append({
            "storage_unit_path": "/storages/%s/data/storage" % pool_name,
            "kube_hostname": storage.get("node", ""),
            "node": get_storage_unit_hostname(pool_name, idx),
            "node_id": storage["node_id"],
            "host_storage_unit_path": storage.get("path", ""),
            "storage_unit_device": storage.get("device", ""),
            "pvc_name": storage.get("pvc", ""),
            "storage_unit_device_dir": get_storage_unit_device_dir(storage),
            "decommissioned": storage.get("decommissioned", ""),
            "storage_unit_index": idx
        })

    if pool_type == POOL_TYPE_REPLICA_2:
        tiebreaker = obj["spec"].get("tiebreaker", None)
        if not tiebreaker:
            logging.warning(logf("No 'tiebreaker' provided for replica2 "
                                 "config. Using default tie-breaker.kadalu.io:/mnt",
                                 pool_name=pool_name))
            # Add default tiebreaker if no tie-breaker option provided
            tiebreaker = {
                "node": "tie-breaker.kadalu.io",
                "path": "/mnt",
            }
        if not tiebreaker.get("port", None):
            tiebreaker["port"] = 24007

        data["tiebreaker"] = tiebreaker

    poolinfo_file = "%s.info" % pool_name
    configmap_data.data[poolinfo_file] = json.dumps(data)

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf("Updated configmap", name=KADALU_CONFIG_MAP,
                      pool_name=pool_name))


def deploy_server_pods(obj):
    """
    Deploy server pods depending on type of
    Pool and other options specified
    """
    # Deploy server pod
    pool_name = obj["metadata"]["name"]
    pool_type = obj["spec"]["type"]
    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    tolerations = obj["spec"].get("tolerations")
    docker_user = os.environ.get("DOCKER_USER", "kadalu")

    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "images_hub": IMAGES_HUB,
        "docker_user": docker_user,
        "pool_name": pool_name,
        "pool_type": pool_type,
        "pv_reclaim_policy": pv_reclaim_policy,
        "pool_id": obj["spec"]["pool_id"]
    }

    # One StatefulSet per Storage Unit
    for idx, storage in enumerate(obj["spec"]["storage"]):
        template_args["host_storage_unit_path"] = storage.get("path", "")
        template_args["kube_hostname"] = storage.get("node", "")
        # TODO: Understand the need, and usage of suffix
        serverpod_name = get_storage_unit_hostname(
            pool_name,
            idx,
            suffix=False
        )
        template_args["serverpod_name"] = serverpod_name
        template_args["storage_unit_path"] = "/storages/%s/data/storage" % pool_name
        template_args["storage_unit_index"] = idx
        template_args["storage_unit_device"] = storage.get("device", "")
        template_args["pvc_name"] = storage.get("pvc", "")
        template_args["storage_unit_device_dir"] = get_storage_unit_device_dir(storage)
        template_args["storage_unit_node_id"] = storage["node_id"]
        template_args["k8s_dist"] = K8S_DIST
        template_args["verbose"] = VERBOSE

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
        logging.info(logf("Deployed Server pod",
                          pool_name=pool_name,
                          manifest=filename,
                          node=storage.get("node", "")))
        add_tolerations("statefulsets", serverpod_name, tolerations)
    add_tolerations("daemonset", NODE_PLUGIN, tolerations)


def handle_external_storage_addition(core_v1_client, obj):
    """Deploy service(One service per Pool)"""
    pool_name = obj["metadata"]["name"]
    details = obj["spec"]["details"]
    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    tolerations = obj["spec"].get("tolerations")

    hosts = []
    ghost = details.get("gluster_host", None)
    ghosts = details.get("gluster_hosts", None)
    if ghost:
        hosts.append(ghost)
    if ghosts:
        hosts.extend(ghosts)

    data = {
        "pool_name": pool_name,
        "pool_id": obj["spec"]["volume_id"],
        "type": POOL_TYPE_EXTERNAL,
        "pv_reclaim_policy": pv_reclaim_policy,
        # CRD would set 'native' but just being cautious
        "kadalu_format": obj["spec"].get("kadalu_format", "native"),
        "gluster_hosts": details["hosts"],
        "gluster_volname": details["gluster_volname"],
        "gluster_options": details.get("gluster_options", ""),
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)
    poolinfo_file = f"{pool_name}.info"
    configmap_data.data[poolinfo_file] = json.dumps(data)

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf("Updated configmap", name=KADALU_CONFIG_MAP,
                      pool_name=pool_name))
    filename = os.path.join(MANIFESTS_DIR, "external-storageclass.yaml")
    template(filename, **data)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed External StorageClass", pool_name=pool_name, manifest=filename))
    add_tolerations("daemonset", NODE_PLUGIN, tolerations)


def get_server_pod_status():

    cmd = ["kubectl", "get", "pods", "-nkadalu", "-ojson"]

    try:
        resp = utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to execute the command",
            command=cmd,
            error=err
        ))

    data = json.loads(resp.stdout)
    pod_status = {}

    for item in data["items"]:

        if "server" in item["metadata"]["name"]:
            pod_name = item["metadata"]["name"]
            pod_phase = item["status"]["phase"]

            pod_status[pod_name] = pod_phase

    return pod_status


def wait_till_pod_start():

    timeout = 60
    start_time = time.time()
    server_pods_ready = 0
    while True:
        pod_status = get_server_pod_status()
        for k,v in pod_status.items():
            curr_time = time.time()

            if curr_time >= start_time + timeout:
                logging.info(logf(
                    "Timeout waiting for server pods to start"
                ))
                return -1

            if len(pod_status.keys()) == server_pods_ready:
                return 0

            if v in ["ImagePullBackOff", "CrashLoopBackOff"]:
                logging.info(logf(
                    "Server pod has crashed"
                ))
                return -1
            elif "Running" in v:
                server_pods_ready+=1
                continue
            else:
                time.sleep(5)
    return 0


def backup_kadalu_storage_config_to_configmap():
    # Create a Snapshot
    cmd = ["kadalu", "config-snapshot", "create", "latest", "--overwrite"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to take Config Snapshot of Kadalu Storage.",
            error=err
        ))
        sys.exit(-1)

    # Create Archive (Change workdir to /var/lib/kadalu/config-snapshots)
    cmd = ["tar", "cvzf", "latest.tar.gz", "latest"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to archive of Kadalu Storage Config Snapshot.",
            error=err
        ))
        sys.exit(-1)

    # Create/Update ConfigMap entry
    # TODO: Handle if the backup file size is more that 1MiB.
    cmd = ["kubectl", "create", "configmap", "kadalu-mgr",
           "--from-file=/var/lib/kadalu/config-snapshots/latest.tar.gz"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to add Kadalu Storage Config backup to Configmap.",
            error=err
        ))
        sys.exit(-1)


def handle_added(core_v1_client, obj):
    """
    New Pool is requested. Update the configMap and deploy
    """

    if not validate_pool_request(obj):
        # TODO: Delete Custom resource
        logging.debug(logf(
            "validation of pool request failed",
            yaml=obj
        ))
        return

    # Ignore if already deployed
    pool_name = obj["metadata"]["name"]
    pods = core_v1_client.list_namespaced_pod(NAMESPACE)
    for pod in pods.items:
        if pod.metadata.name.startswith("server-" + pool_name + "-"):
            logging.debug(logf(
                "Ignoring already deployed server statefulsets",
                pool_name=pool_name
            ))
            return

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    if configmap_data.data.get("%s.info" % pool_name, None):
        # Pool already exists
        logging.debug(logf(
            "Ignoring already updated pool config",
            pool_name=pool_name
        ))
        return

    # Generate new Pool ID
    if obj["spec"].get("pool_id", None) is None:
        obj["spec"]["pool_id"] = str(uuid.uuid1())
    # Apply existing Pool ID to recreate storage pool from existing device/path
    else:
        logging.info(logf(
            "Applying existing pool id",
            pool_id=obj["spec"]["pool_id"]
        ))

    pool_type = obj["spec"]["type"]
    if pool_type == POOL_TYPE_EXTERNAL:
        handle_external_storage_addition(core_v1_client, obj)
        return

    # Generate Node ID for each storage device.
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = "node-%d" % idx

    # Storage Class
    deploy_storage_class(obj)

    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    # TODO: Add intelligence to reach unreachable pods again
    if wait_till_pod_start() == -1:
        logging.info(logf("Server pods were not properly deployed"))
        return

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, pool_name=pool_name)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed Service", pool_name=pool_name, manifest=filename))

    # Time required for service to start
    time.sleep(40)

    poolinfo = poolinfo_from_crd_spec(obj)
    cmd = [
        "kadalu", "volume", "create",
        "--auto-create-pool", "--auto-add-nodes",
        f"kadalu-storage/{poolinfo['name']}"
    ]

    cmd += [
        f"{storage_unit['node']}:{storage_unit['path']}:24007"
        for storage_unit in poolinfo["storage_units"]
    ]

    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to create kadalu volume",
            error=err
        ))

    # Dump Kadalu Storage configurations to Configmap.
    # So that Operator can restore the Configurations
    # on every start.
    backup_kadalu_storage_config_to_configmap()


def handle_modified(core_v1_client, obj):
    """
    Handle when Pool option is updated or Pool
    state is changed to maintenance
    """
    # TODO: Handle Volume maintenance mode

    pool_name = obj["metadata"]["name"]

    pool_mode = obj["spec"].get("mode", POOL_MODE_NATIVE)
    if is_pool_mode_external(pool_mode):
        # Modification of 'External' volume mode is not supported
        logging.info(logf(
            "Modification of 'External' volume mode is not supported",
            pool_name=pool_name
        ))
        return

    if not validate_pool_request(obj):
        logging.debug(logf(
            "validation of pool request failed",
            yaml=obj
        ))
        return

    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    if not configmap_data.data.get(f"{pool_name}.info", None):
        logging.warning(logf(
            "Pool config not found",
            pool_name=pool_name
        ))
        # Volume doesn't exist yet, so create it
        handle_added(core_v1_client, obj)
        return

    # Pool ID (uuid) is already generated, re-use
    cfgmap = json.loads(configmap_data.data[pool_name + ".info"])
    # Get pool-id from config map
    obj["spec"]["pool_id"] = cfgmap["pool_id"]

    # Set Node ID for each storage device from configmap
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = "node-%d" % idx

    # Add new entry in the existing config map
    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, pool_name=pool_name)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed Service", volname=pool_name, manifest=filename))


def handle_deleted(core_v1_client, obj):
    """
    If number of pvs provisioned from that Pool
    is zero - Delete the respective server pods
    If number of pvs is not zero, wait or periodically
    check for num_pvs. Delete Server pods only when pvs becomes zero.
    """

    pool_name = obj["metadata"]["name"]

    storage_info_data = get_configmap_data(pool_name)

    logging.info(logf("Delete requested", pool_name=pool_name))

    pv_count = get_num_pvs(storage_info_data)

    if pv_count == -1:
        logging.error(
            logf("Storage delete failed. Failed to get PV count",
                 number_of_pvs=pv_count,
                 pool_name=pool_name))
        return

    if pv_count != 0:

        logging.warning(
            logf("Storage delete failed. Storage is not empty",
                 number_of_pvs=pv_count,
                 pool_name=pool_name))

    elif pv_count == 0:

        pool_type = storage_info_data.get("type")
        pool_mode = storage_info_data.get("mode")

        # We can't delete external pool but cleanup StorageClass and Configmap
        # Delete Configmap and Storage class for both Native & External
        delete_storage_class(pool_name, pool_type)
        delete_config_map(core_v1_client, obj)

        if not is_pool_mode_external(pool_mode):
            delete_server_pods(storage_info_data, obj)
            filename = os.path.join(MANIFESTS_DIR, "services.yaml")
            template(filename, namespace=NAMESPACE, volname=pool_name)
            lib_execute(KUBECTL_CMD, DELETE_CMD, "-f", filename)
            logging.info(
                logf("Deleted Service", pool_name=pool_name, manifest=filename))

    return


def get_configmap_data(pool_name):
    """
    Get storage info data from kadalu configmap
    """

    cmd = ["kubectl", "get", "configmap", "kadalu-info", "-nkadalu", "-ojson"]

    try:
        resp = utils_execute(cmd)
        config_data = json.loads(resp.stdout)

        data = config_data['data']
        storage_name = "%s.info" % pool_name
        storage_info_data = data[storage_name]

        # Return data in 'dict' format
        return json.loads(storage_info_data)

    except CommandError as err:
        logging.error(logf(
            "Failed to get details from configmap",
            error=err
        ))
        return None


def get_num_pvs(storage_info_data):
    """
    Get number of PVs provisioned from
    pool requested for deletion
    through configmap.
    """

    pool_name = storage_info_data['name']
    cmd = None
    if is_pool_mode_external(storage_info_data.get("mode")):
        # We can't access external cluster and so query existing PVs which are
        # using external storageclass
        pool_name = "kadalu." + pool_name
        jpath = ('jsonpath=\'{range .items[?(@.spec.storageClassName=="%s")]}'
                 '{.spec.storageClassName}{"\\n"}{end}\'' % pool_name)
        cmd = ["kubectl", "get", "pv", "-o", jpath]
    else:
        storage_units = storage_info_data['storage_units']
        dbpath = "/storages/" + pool_name + "/data/storage/stat.db"
        query = ("select count(pvname) from pv_stats;")
        cmd = [
            "kubectl", "exec", "-i",
            storage_units[0]['node'].replace("." + pool_name, ""), "-c", "server",
            "-nkadalu", "--", "sqlite3", dbpath, query
        ]

    try:
        resp = utils_execute(cmd)
        parts = resp.stdout.strip("'").split()
        if is_pool_mode_external(storage_info_data.get("mode")):
            return len(parts)
        pv_count = int(parts[0])
        return pv_count

    except CommandError as msg:
        # 1. If storage is created but no PV is carved then pv_stats table is not
        # created in SQLITE3
        # 2. If we fail to create 'server' pod then there'll be no 'server'
        # container (this'll be hit if supplied 'storageClass' is invalid)
        # 3. If 'server' pod does not have a host assigned,
        # TODO: find out root cause, repro - use incorrect device and edit with
        # correct device later
        if msg.stderr.find("no such table") != -1 or msg.stderr.find(
                "container not found") != -1 or msg.stderr.find(
                "not have a host assigned") != -1:
            # We are good to delete server pods
            return 0
        logging.error(
            logf("Failed to get size details of the "
                 "storage \"%s\"" % pool_name,
                 error=msg))
        # Return error as its -1
        return -1


def delete_server_pods(storage_info_data, obj):
    """
    Delete server pods depending on type of
    Pool and other options specified
    """

    pool_name = obj["metadata"]["name"]
    pool_type = storage_info_data['type']
    pool_id = storage_info_data['pool_id']

    docker_user = os.environ.get("DOCKER_USER", "kadalu")

    shd_required = False
    if pool_type in (POOL_TYPE_REPLICA_3, POOL_TYPE_REPLICA_2):
        shd_required = True

    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "docker_user": docker_user,
        "images_hub": IMAGES_HUB,
        "pool_name": pool_name,
        "pool_type": pool_type,
        "pool_id": pool_id,
        "shd_required": shd_required
    }

    storage_units = storage_info_data['storage_units']

    # Traverse all storage units from configmap
    for storage_unit in storage_units:

        idx = storage_unit['storage_unit_index']
        template_args["host_path"] = storage_unit['host_path']
        template_args["kube_hostname"] = storage_unit['kube_hostname']
        template_args["serverpod_name"] = get_storage_unit_hostname(
            pool_name,
            idx,
            suffix=False
        )
        template_args["storage_unit_path"] = "/storages/%s/data/storage" % pool_name
        template_args["storage_unit_index"] = idx
        template_args["storage_unit_device"] = storage_unit['device']
        template_args["pvc_name"] = storage_unit['pvc_name']
        template_args["storage_unit_device_dir"] = storage_unit['device_dir']
        template_args["storage_unit_node_id"] = storage_unit['node_id']
        template_args["k8s_dist"] = K8S_DIST

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        lib_execute(KUBECTL_CMD, DELETE_CMD, "-f", filename)
        logging.info(logf(
            "Deleted Server pod",
            pool_name=pool_name,
            manifest=filename,
            node=storage_unit['node']
        ))


def delete_config_map(core_v1_client, obj):
    """
    Poolinfo of existing Pool is generated and ConfigMap is deleted
    """

    pool_name = obj["metadata"]["name"]

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    poolinfo_file = "%s.info" % pool_name
    configmap_data.data[poolinfo_file] = None

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf(
        "Deleted configmap",
        name=KADALU_CONFIG_MAP,
        pool_name=pool_name
    ))


def delete_storage_class(pool_name, _):
    """
    Deletes deployed External and Custom StorageClass
    """

    sc_name = "kadalu." + pool_name
    lib_execute(KUBECTL_CMD, DELETE_CMD, "sc", sc_name)
    logging.info(logf(
        "Deleted Storage class",
        pool_name=pool_name
    ))


def csi_driver_object_api_version():
    """
    Return API Version of CSI Driver object"
    """

    cmd = ["kubectl", "get", "csidriver", "kadalu", "-ojson"]

    try:
        resp = utils_execute(cmd)
        csi_driver_data = json.loads(resp.stdout)
        version = csi_driver_data["apiVersion"]
        return version[version.rfind("/")+1:]

    except CommandError as err:
        logging.error(logf(
            "Failed to get version of csi driver object",
            error=err
        ))
        return None


def watch_stream(core_v1_client, k8s_client):
    """
    Watches kubernetes event stream for kadalustorages in Kadalu namespace
    """
    crds = client.CustomObjectsApi(k8s_client)
    k8s_watch = watch.Watch()
    resource_version = ""
    for event in k8s_watch.stream(crds.list_cluster_custom_object,
                                  "kadalu-operator.storage",
                                  "v1alpha1",
                                  "kadalustorages",
                                  resource_version=resource_version):
        obj = event["object"]
        operation = event['type']
        spec = obj.get("spec")
        if not spec:
            continue
        metadata = obj.get("metadata")
        resource_version = metadata['resourceVersion']
        logging.debug(logf("Event", operation=operation, object=repr(obj)))
        if operation == "ADDED":
            handle_added(core_v1_client, obj)
        elif operation == "MODIFIED":
            handle_modified(core_v1_client, obj)
        elif operation == "DELETED":
            handle_deleted(core_v1_client, obj)


def crd_watch(core_v1_client, k8s_client):
    """
    Watches the CRD to provision new Pool
    """
    while True:
        try:
            watch_stream(core_v1_client, k8s_client)
        except (ProtocolError, NewConnectionError):
            # It might so happen that this'll be logged for every hit in k8s
            # event stream in kadalu namespace and better to log at debug level
            logging.debug(
                logf(
                    "Watch connection broken and restarting watch on the stream"
                ))
            time.sleep(30)


def deploy_csi_pods(core_v1_client):
    """
    Look for CSI pods, if any one CSI pod found then
    that means it is deployed
    """
    pods = core_v1_client.list_namespaced_pod(
        NAMESPACE)
    for pod in pods.items:
        if pod.metadata.name.startswith(CSI_POD_PREFIX):
            logging.info("Updating already deployed CSI pods")

    # Deploy CSI Pods
    api_instance = client.VersionApi().get_code()

    if api_instance.major > "1" or api_instance.major == "1" and \
       api_instance.minor >= "22":

        csi_driver_version = csi_driver_object_api_version()
        if csi_driver_version is not None and \
           csi_driver_version != "v1":
            lib_execute(KUBECTL_CMD, DELETE_CMD, "csidriver", "kadalu")
            logging.info(logf(
                "Deleted existing CSI Driver object",
                csi_driver_version=csi_driver_version
            ))

        filename = os.path.join(MANIFESTS_DIR, "csi-driver-object-v1.yaml")
        template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
        lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)

    elif api_instance.major > "1" or api_instance.major == "1" and \
       api_instance.minor >= "14":
        filename = os.path.join(MANIFESTS_DIR, "csi-driver-object.yaml")
        template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
        lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)

    filename = os.path.join(MANIFESTS_DIR, "csi.yaml")
    docker_user = os.environ.get("DOCKER_USER", "kadalu")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION,
             docker_user=docker_user, k8s_dist=K8S_DIST,
             images_hub=IMAGES_HUB,
             kubelet_dir=KUBELET_DIR, verbose=VERBOSE,)

    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed CSI Pods", manifest=filename))


def deploy_config_map(core_v1_client):
    """Deploys the template configmap if not exists"""

    configmaps = core_v1_client.list_namespaced_config_map(
        NAMESPACE)
    uid = uuid.uuid4()
    upgrade = False
    for item in configmaps.items:
        if item.metadata.name == KADALU_CONFIG_MAP:
            logging.info(logf(
                "Found existing configmap. Updating",
                name=item.metadata.name
            ))

            # Don't overwrite UID info.
            configmap_data = core_v1_client.read_namespaced_config_map(
                KADALU_CONFIG_MAP, NAMESPACE)
            if configmap_data.data.get("uid", None):
                uid = configmap_data.data["uid"]
                upgrade = True
            # Keep the config details required to be preserved.

    # Deploy Config map
    filename = os.path.join(MANIFESTS_DIR, "configmap.yaml")
    template(filename,
             namespace=NAMESPACE,
             kadalu_version=VERSION,
             uid=uid)

    if not upgrade:
        lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
    logging.info(logf("ConfigMap Deployed", manifest=filename, uid=uid, upgrade=upgrade))
    return uid, upgrade


def deploy_storage_class(obj):
    """Deploys the default and custom storage class for KaDalu if not exists"""

    # Deploy defalut Storage Class
    api_instance = client.StorageV1Api()
    scs = api_instance.list_storage_class()
    sc_names = []
    for tmpl in os.listdir(MANIFESTS_DIR):
        if tmpl.startswith("storageclass-") and tmpl.endswith(".j2"):
            sc_names.append(
                tmpl.replace("storageclass-", "").replace(".yaml.j2", "")
            )

    installed_scs = [item.metadata.name for item in scs.items]
    for sc_name in sc_names:
        filename = os.path.join(MANIFESTS_DIR, "storageclass-%s.yaml" % sc_name)
        if sc_name in installed_scs:
            logging.info(logf("StorageClass already present, continuing with Apply",
                              manifest=filename))

        template(filename, namespace=NAMESPACE, kadalu_version=VERSION,
                 pool_name=obj["metadata"]["name"],
                 kadalu_format=obj["spec"].get("kadalu_format", "native"))
        lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
        logging.info(logf("Deployed StorageClass", manifest=filename))

def add_tolerations(resource, name, tolerations):
    """Adds tolerations to kubernetes resource/name object"""
    if tolerations is None:
        return
    patch = {"spec": {"template": {"spec": {"tolerations": tolerations}}}}
    try:
        lib_execute(KUBECTL_CMD, PATCH_CMD, resource, name, "-p", json.dumps(patch), "--type=merge")
    except CommandException as err:
        errmsg = f"Unable to patch {resource}/{name} with tolerations \
        {str(tolerations)}"
        logging.error(logf(errmsg, error=err))
    logging.info(logf("Added tolerations", resource=resource, name=name,
        tolerations=str(tolerations)))
    return


def create_and_login_kadalu_storage_user(username, password):
    cmd = ["kadalu","user", "create", username, f"--password={password}"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        # Do not exit on this error. If User creation failed with
        # already exists error then the next command will succeed.
        # Any other error here will also cause error for the next command.
        logging.warning(logf("Failed to create user", error=err))

    cmd = ["kadalu", "user", "login", "admin", "--password=kadalu"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf("Failed to login user", error=err))
        sys.exit(-1)


def main():
    """Main"""
    config.load_incluster_config()

    # As per the issue https://github.com/kubernetes-client/python/issues/254
    clnt = client.Configuration() #go and get a copy of the default config
    clnt.verify_ssl = False #set verify_ssl to false in that config
    client.Configuration.set_default(clnt) #make that config the default for all new clients

    core_v1_client = client.CoreV1Api()
    k8s_client = client.ApiClient()

    # TODO: Get password from k8's secret
    create_and_login_kadalu_storage_user("admin", "kadalu")

    # ConfigMap
    uid, upgrade = deploy_config_map(core_v1_client)

    # CSI Pods
    deploy_csi_pods(core_v1_client)

    if upgrade:
        logging.info(logf("Upgrading to ", version=VERSION))
        upgrade_storage_pods(core_v1_client)

    # Send Analytics Tracker
    # The information from this analytics is available for
    # developers to understand and build project in a better
    # way
    send_analytics_tracker("operator", uid)

    # Watch CRD
    crd_watch(core_v1_client, k8s_client)


if __name__ == "__main__":
    logging_setup()

    # This not advised in general, but in kadalu's operator, it is OK to
    # ignore these warnings as we know to make calls only inside of
    # kubernetes cluster
    urllib3.disable_warnings()

    main()
