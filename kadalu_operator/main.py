"""
KaDalu Operator: Once started, deploys required CSI drivers,
bootstraps the ConfigMap and waits for the CRD update to create
Server pods
"""
import json
import logging
import os
import re
import time
import uuid

import urllib3
from jinja2 import Template

from kadalulib import CommandException
from kadalulib import execute as lib_execute
from kadalulib import (is_host_reachable, logf, logging_setup,
                       send_analytics_tracker, get_single_pv_per_pool)
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
VALID_HOSTING_VOLUME_TYPES = ["Replica1", "Replica2", "Replica3",
                              "Disperse", "External", "Arbiter"]
VALID_PV_RECLAIM_POLICY_TYPES = ["delete", "archive", "retain"]
VOLUME_TYPE_REPLICA_1 = "Replica1"
VOLUME_TYPE_REPLICA_2 = "Replica2"
VOLUME_TYPE_REPLICA_3 = "Replica3"
VOLUME_TYPE_EXTERNAL = "External"
VOLUME_TYPE_DISPERSE = "Disperse"
VOLUME_TYPE_ARBITER = "Arbiter"

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


# TODO: Validate given options using kadalu/volgen API
def options_validation(options):
    """ Validate Pool Options """

    for option in options:
        if option.get("key", None) is None and \
           option.get("value", None) is None:
            logging.error(logf("Key/Value not specified for Storage Pool Options"))
            return False

    return True


def bricks_validation(bricks):
    """Validate Brick path and node options"""
    ret = True
    for idx, brick in enumerate(bricks):
        if not ret:
            break

        if brick.get("pvc", None) is not None:
            continue

        if brick.get("path", None) is None and \
           brick.get("device", None) is None:
            logging.error(logf("Storage path/device not specified",
                               number=idx+1))
            ret = False

        if brick.get("node", None) is None:
            logging.error(logf("Storage node not specified", number=idx+1))
            ret = False

    return ret


def validate_ext_details(obj):
    """Validate external Volume details"""
    cluster = obj["spec"].get("details", None)
    if not cluster:
        logging.error(logf("External Cluster details not given."))
        return False

    valid = 0
    ghosts = []
    gport = 24007
    if cluster.get('gluster_hosts', None):
        valid += 1
        hosts = cluster.get('gluster_hosts')
        ghosts.extend(hosts)
    if cluster.get('gluster_host', None):
        valid += 1
        ghosts.append(cluster.get('gluster_host'))
    if cluster.get('gluster_volname', None):
        valid += 1
    if cluster.get('gluster_port', None):
        gport = cluster.get('gluster_port', 24007)

    if valid < 2:
        logging.error(logf("No 'host' and 'volname' details provided."))
        return False

    if not is_host_reachable(ghosts, gport):
        logging.error(logf("gluster server not reachable: on %s:%d" %
                           (ghosts, gport)))
        #  Noticed that there may be glitches in n/w during this time.
        #  Not good to fail the validation, instead, just log here, so
        #  we are aware this is a possible reason.
        #return False

    logging.debug(logf("External Storage %s successfully validated" % \
                       obj["metadata"].get("name", "<unknown>")))
    return True


# pylint: disable=too-many-return-statements
# pylint: disable=too-many-branches
# pylint: disable=too-many-statements
# pylint: disable=too-many-locals
def validate_volume_request(obj):
    """Validate the Volume request for Replica options, number of bricks etc"""
    if not obj.get("spec", None):
        logging.error("Storage 'spec' not specified")
        return False

    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    if pv_reclaim_policy not in VALID_PV_RECLAIM_POLICY_TYPES:
        logging.error("PV Reclaim Policy not valid")
        return False

    voltype = obj["spec"].get("type", None)
    if voltype is None:
        logging.error("Storage type not specified")
        return False

    if voltype not in VALID_HOSTING_VOLUME_TYPES:
        logging.error(logf("Invalid Storage type",
                           valid_types=",".join(VALID_HOSTING_VOLUME_TYPES),
                           provided_type=voltype))
        return False

    if voltype == VOLUME_TYPE_EXTERNAL:
        return validate_ext_details(obj)

    options = obj["spec"].get("options", [])
    if not options_validation(options):
        return False

    bricks = obj["spec"].get("storage", [])
    if not bricks_validation(bricks):
        return False

    decommissioned = ""
    subvol_bricks_count = 1
    if voltype == VOLUME_TYPE_REPLICA_2:
        subvol_bricks_count = 2
    elif voltype == VOLUME_TYPE_REPLICA_3:
        subvol_bricks_count = 3

    if voltype == VOLUME_TYPE_DISPERSE:
        disperse_config = obj["spec"].get("disperse", None)
        if disperse_config is None:
            logging.error("Disperse Volume data and redundancy "
                          "count is not specified")
            return False

        data_bricks = disperse_config.get("data", 0)
        redundancy_bricks = disperse_config.get("redundancy", 0)
        if data_bricks == 0 or redundancy_bricks == 0:
            logging.error("Disperse Volume data or redundancy "
                          "count is not specified")
            return False

        subvol_bricks_count = data_bricks + redundancy_bricks
        # redundancy must be greater than 0, and the total number
        # of bricks must be greater than 2 * redundancy. This
        # means that a dispersed volume must have a minimum of 3 bricks.
        if subvol_bricks_count <= (2 * redundancy_bricks):
            logging.error("Invalid redundancy for the Disperse Volume")
            return False

        # stripe_size = (bricks_count - redundancy) * 512
        # Using combinations of #Bricks/redundancy that give a power
        # of two for the stripe size will make the disperse volume
        # perform better in most workloads because it's more typical
        # to write information in blocks that are multiple of two
        # https://docs.gluster.org/en/latest/Administrator-Guide
        #    /Setting-Up-Volumes/#creating-dispersed-volumes
        if data_bricks % 2 != 0:
            logging.error("Disperse Configuration is not Optimal")
            return False

    if len(bricks) % subvol_bricks_count != 0:
        logging.error("Invalid number of storage directories/devices"
                      " specified")
        return False

    if subvol_bricks_count > 1:
        for i in range(0, int(len(bricks) / subvol_bricks_count)):
            decommissioned = ""
            for k in range(0, subvol_bricks_count):
                brick_idx = (i * subvol_bricks_count) + k
                brick = bricks[brick_idx]
                decom = brick.get("decommissioned", "")
                if k == 0:
                    decommissioned = decom
                    continue
                if decom != decommissioned:
                    logging.error(logf(
                        "All of distribute subvolume should be marked decommissioned",
                        brick=brick, brick_index=brick_idx))
                    return False

    # If we are here, decommissioned option is properly given.

    if voltype == VOLUME_TYPE_REPLICA_2:
        tiebreaker = obj["spec"].get("tiebreaker", None)
        if tiebreaker and (not tiebreaker.get("node", None) or
                           not tiebreaker.get("path", None)):
            logging.error(logf("'tiebreaker' provided for replica2 "
                               "config is not valid"))
            return False

    if voltype == VOLUME_TYPE_ARBITER:
        # Arbiter volume require atleast 2 data bricks and atmost 1 arbiter brick,
        # Per each distribute group.
        subvol_bricks_count = 2 + 1
        if len(bricks) < 3 or len(bricks) % subvol_bricks_count != 0:
            logging.error("Invalid number of storage directories/devices"
                          " specified for volume type 'Arbiter'")
            return False

    logging.debug(logf("Storage %s successfully validated" % \
                       obj["metadata"].get("name", "<unknown>")))
    return True


def get_brick_device_dir(brick):
    """If custom file is passed as brick device then the
    parent directory needs to be mounted as is
    in server container"""
    brick_device_dir = ""
    logging.info(repr(brick))
    brickdev = brick.get("device", "")
    logging.info(brickdev)
    if brickdev != "" and not brickdev.startswith("/dev/"):
        brick_device_dir = os.path.dirname(brickdev)

    return brick_device_dir


def get_brick_hostname(volname, idx, suffix=True):
    """Brick hostname is <statefulset-name>-<ordinal>.<service-name>
    statefulset name is the one which is visible when the
    `get pods` command is run, so the format used for that name
    is "server-<volname>-<idx>". Escape dots from the
    hostname from the input otherwise will become invalid name.
    Service is created with name as Volume name. For example,
    brick_hostname will be "server-spool1-0-0.spool1" and
    server pod name will be "server-spool1-0"
    """
    tmp_vol = volname.replace("-", "_")
    dns_friendly_volname = re.sub(r'\W+', '', tmp_vol).replace("_", "-")
    hostname = "server-%s-%d" % (dns_friendly_volname, idx)
    if suffix:
        return "%s-0.%s" % (hostname, volname)

    return hostname


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

        volname = key.replace('.info', '')
        data = json.loads(configmap_data.data[key])

        logging.info(logf("config map", volname=volname, data=data))
        if data['type'] == VOLUME_TYPE_EXTERNAL:
            # nothing to be done for upgrade, say we are good.
            logging.debug(logf(
                "volume type external, nothing to upgrade",
                volname=volname,
                data=data))
            continue

        if data['type'] == VOLUME_TYPE_REPLICA_1:
            # No promise of high availability, upgrade
            logging.debug(logf(
                "volume type Replica1, calling upgrade",
                volname=volname,
                data=data))
            # TODO: call upgrade

        # Replica 2 and Replica 3 needs to check for self-heal
        # count 0 before going ahead with upgrade.

        # glfsheal volname --file-path=/template/file info-summary
        obj = {}
        obj["metadata"] = {}
        obj["spec"] = {}
        obj["metadata"]["name"] = volname
        obj["spec"]["type"] = data['type']
        obj["spec"]["pvReclaimPolicy"] = data.get("pvReclaimPolicy", "delete")
        obj["spec"]["volume_id"] = data["volume_id"]
        obj["spec"]["storage"] = []

        # Need this loop so below array can be constructed in the proper order
        for val in data["bricks"]:
            obj["spec"]["storage"].append({})

        # Set Node ID for each storage device from configmap
        for val in data["bricks"]:
            idx = val["brick_index"]

            obj["spec"]["storage"][idx]["node_id"] = val["node_id"]
            obj["spec"]["storage"][idx]["path"] = val["host_brick_path"]
            obj["spec"]["storage"][idx]["node"] = val["kube_hostname"]
            obj["spec"]["storage"][idx]["device"] = val["brick_device"]
            obj["spec"]["storage"][idx]["pvc"] = val["pvc_name"]

        # TODO: call upgrade_pods_with_heal_check() here
        deploy_server_pods(obj)


def update_config_map(core_v1_client, obj):
    """
    Volinfo of new hosting Volume is generated and updated to ConfigMap
    """
    volname = obj["metadata"]["name"]
    voltype = obj["spec"]["type"]
    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    volume_id = obj["spec"]["volume_id"]
    disperse_config = obj["spec"].get("disperse", {})

    data = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "volname": volname,
        "volume_id": volume_id,
        "single_pv_per_pool": get_single_pv_per_pool(obj["spec"]),
        "type": voltype,
        "pvReclaimPolicy" : pv_reclaim_policy,
        "bricks": [],
        "disperse": {
            "data": disperse_config.get("data", 0),
            "redundancy": disperse_config.get("redundancy", 0)
        },
        "options": {}
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    # Add options entry as key:value
    if obj["spec"].get("options", None):
        options = obj["spec"]["options"]
        for option in options:
            data["options"].update({
                option.get("key"): option.get("value")
            })

    # For each brick, add brick path and node id
    bricks = obj["spec"]["storage"]
    for idx, storage in enumerate(bricks):
        data["bricks"].append({
            "brick_path": "/bricks/%s/data/brick" % volname,
            "kube_hostname": storage.get("node", ""),
            "node": get_brick_hostname(volname, idx),
            "node_id": storage["node_id"],
            "host_brick_path": storage.get("path", ""),
            "brick_device": storage.get("device", ""),
            "pvc_name": storage.get("pvc", ""),
            "brick_device_dir": get_brick_device_dir(storage),
            "decommissioned": storage.get("decommissioned", ""),
            "brick_index": idx
        })

    if voltype == VOLUME_TYPE_REPLICA_2:
        tiebreaker = obj["spec"].get("tiebreaker", None)
        if not tiebreaker:
            data["tiebreaker"] = {}
        else:
            if not tiebreaker.get("port", None):
                tiebreaker["port"] = 24007

            data["tiebreaker"] = tiebreaker

    volinfo_file = "%s.info" % volname
    configmap_data.data[volinfo_file] = json.dumps(data)

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf("Updated configmap", name=KADALU_CONFIG_MAP,
                      volname=volname))


def deploy_server_pods(obj):
    """
    Deploy server pods depending on type of Hosting
    Volume and other options specified
    """
    # Deploy server pod
    volname = obj["metadata"]["name"]
    voltype = obj["spec"]["type"]
    pv_reclaim_policy = obj["spec"].get("pvReclaimPolicy", "delete")
    tolerations = obj["spec"].get("tolerations")
    docker_user = os.environ.get("DOCKER_USER", "kadalu")

    shd_required = False
    if voltype in (VOLUME_TYPE_REPLICA_3, VOLUME_TYPE_REPLICA_2,
                   VOLUME_TYPE_DISPERSE):
        shd_required = True

    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "images_hub": IMAGES_HUB,
        "docker_user": docker_user,
        "volname": volname,
        "voltype": voltype,
        "pvReclaimPolicy": pv_reclaim_policy,
        "volume_id": obj["spec"]["volume_id"],
        "shd_required": shd_required
    }

    # One StatefulSet per Brick
    for idx, storage in enumerate(obj["spec"]["storage"]):
        template_args["host_brick_path"] = storage.get("path", "")
        template_args["kube_hostname"] = storage.get("node", "")
        # TODO: Understand the need, and usage of suffix
        template_args["serverpod_name"] = get_brick_hostname(
            volname,
            idx,
            suffix=False
        )
        template_args["brick_path"] = "/bricks/%s/data/brick" % volname
        template_args["brick_index"] = idx
        template_args["brick_device"] = storage.get("device", "")
        template_args["pvc_name"] = storage.get("pvc", "")
        template_args["brick_device_dir"] = get_brick_device_dir(storage)
        template_args["brick_node_id"] = storage["node_id"]
        template_args["k8s_dist"] = K8S_DIST
        template_args["verbose"] = VERBOSE
        template_args["tolerations"] = tolerations

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
        logging.info(logf("Deployed Server pod",
                          volname=volname,
                          manifest=filename,
                          node=storage.get("node", "")))
    add_tolerations("daemonset", NODE_PLUGIN, tolerations)


def handle_external_storage_addition(core_v1_client, obj):
    """Deploy service(One service per Volume)"""
    volname = obj["metadata"]["name"]
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
        "volname": volname,
        "volume_id": obj["spec"]["volume_id"],
        "type": VOLUME_TYPE_EXTERNAL,
        "pvReclaimPolicy": pv_reclaim_policy,
        # CRD would set 'native' but just being cautious
        "single_pv_per_pool": get_single_pv_per_pool(obj["spec"]),
        "gluster_hosts": ",".join(hosts),
        "gluster_volname": details["gluster_volname"],
        "gluster_options": details.get("gluster_options", ""),
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)
    volinfo_file = "%s.info" % volname
    configmap_data.data[volinfo_file] = json.dumps(data)

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf("Updated configmap", name=KADALU_CONFIG_MAP,
                      volname=volname))
    filename = os.path.join(MANIFESTS_DIR, "external-storageclass.yaml")
    template(filename, **data)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed External StorageClass", volname=volname, manifest=filename))
    add_tolerations("daemonset", NODE_PLUGIN, tolerations)


def handle_added(core_v1_client, obj):
    """
    New Volume is requested. Update the configMap and deploy
    """

    if not validate_volume_request(obj):
        # TODO: Delete Custom resource
        logging.debug(logf(
            "validation of volume request failed",
            yaml=obj
        ))
        return

    # Ignore if already deployed
    volname = obj["metadata"]["name"]
    pods = core_v1_client.list_namespaced_pod(NAMESPACE)
    for pod in pods.items:
        if pod.metadata.name.startswith("server-" + volname + "-"):
            logging.debug(logf(
                "Ignoring already deployed server statefulsets",
                storagename=volname
            ))
            return

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    if configmap_data.data.get("%s.info" % volname, None):
        # Volume already exists
        logging.warning(logf(
            "Updating existing config map",
            storagename=volname
        ))

    # Generate new Volume ID
    if obj["spec"].get("volume_id", None) is None:
        obj["spec"]["volume_id"] = str(uuid.uuid1())
    # Apply existing Volume ID to recreate storage pool from existing device/path
    else:
        logging.info(logf(
            "Applying existing volume id",
            volume_id=obj["spec"]["volume_id"]
        ))

    voltype = obj["spec"]["type"]
    if voltype == VOLUME_TYPE_EXTERNAL:
        handle_external_storage_addition(core_v1_client, obj)
        return

    # Generate Node ID for each storage device.
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = "node-%d" % idx

    # Storage Class
    deploy_storage_class(obj)

    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, volname=volname)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed Service", volname=volname, manifest=filename))


def handle_modified(core_v1_client, obj):
    """
    Handle when Volume option is updated or Volume
    state is changed to maintenance
    """
    # TODO: Handle Volume maintenance mode

    volname = obj["metadata"]["name"]

    voltype = obj["spec"]["type"]
    if voltype == VOLUME_TYPE_EXTERNAL:
        # Modification of 'External' volume type is not supported
        logging.info(logf(
            "Modification of 'External' volume type is not supported",
            storagename=volname
        ))
        return

    if not validate_volume_request(obj):
        logging.debug(logf(
            "validation of volume request failed",
            yaml=obj
        ))
        return

    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    if not configmap_data.data.get("%s.info" % volname, None):
        logging.warning(logf(
            "Volume config not found",
            storagename=volname
        ))
        # Volume doesn't exist yet, so create it
        handle_added(core_v1_client, obj)
        return

    # Volume ID (uuid) is already generated, re-use
    cfgmap = json.loads(configmap_data.data[volname + ".info"])
    # Get volume-id from config map
    obj["spec"]["volume_id"] = cfgmap["volume_id"]

    # Set Node ID for each storage device from configmap
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = "node-%d" % idx

    # Add new entry in the existing config map
    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, volname=volname)
    lib_execute(KUBECTL_CMD, APPLY_CMD, "-f", filename)
    logging.info(logf("Deployed Service", volname=volname, manifest=filename))


def handle_deleted(core_v1_client, obj):
    """
    If number of pvs provisioned from that volume
    is zero - Delete the respective server pods
    If number of pvs is not zero, wait or periodically
    check for num_pvs. Delete Server pods only when pvs becomes zero.
    """

    volname = obj["metadata"]["name"]

    storage_info_data = get_configmap_data(volname)

    logging.info(logf("Delete requested", volname=volname))

    pv_count = get_num_pvs(storage_info_data)

    if pv_count == -1:
        logging.error(
            logf("Storage delete failed. Failed to get PV count",
                 number_of_pvs=pv_count,
                 storage=volname))
        return

    if pv_count != 0:

        logging.warning(
            logf("Storage delete failed. Storage is not empty",
                 number_of_pvs=pv_count,
                 storage=volname))

    elif pv_count == 0:

        hostvol_type = storage_info_data.get("type")

        # We can't delete external volume but cleanup StorageClass and Configmap
        # Delete Configmap and Storage class for both Native & External
        delete_storage_class(volname, hostvol_type)
        delete_config_map(core_v1_client, obj)

        if hostvol_type != "External":

            delete_server_pods(storage_info_data, obj)
            filename = os.path.join(MANIFESTS_DIR, "services.yaml")
            template(filename, namespace=NAMESPACE, volname=volname)
            lib_execute(KUBECTL_CMD, DELETE_CMD, "-f", filename)
            logging.info(
                logf("Deleted Service", volname=volname, manifest=filename))

    return


def get_configmap_data(volname):
    """
    Get storage info data from kadalu configmap
    """

    cmd = ["kubectl", "get", "configmap", "kadalu-info", "-nkadalu", "-ojson"]

    try:
        resp = utils_execute(cmd)
        config_data = json.loads(resp.stdout)

        data = config_data['data']
        storage_name = "%s.info" % volname
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
    volume requested for deletion
    through configmap.
    """

    volname = storage_info_data['volname']
    volname = "kadalu." + volname
    jpath = ('jsonpath=\'{range .items[?(@.spec.storageClassName=="%s")]}'
                '{.spec.storageClassName}{"\\n"}{end}\'' % volname)
    cmd = ["kubectl", "get", "pv", "-o", jpath]

    try:
        resp = utils_execute(cmd)
        pvs = resp.stdout.strip("'").split()
        return len(pvs)

    except CommandError as msg:
        logging.error(
            logf("Failed to get size details of the "
                 "storage \"%s\"" % volname,
                 error=msg))
        # Return error as its -1
        return -1


def delete_server_pods(storage_info_data, obj):
    """
    Delete server pods depending on type of Hosting
    Volume and other options specified
    """

    volname = obj["metadata"]["name"]
    voltype = storage_info_data['type']
    volumeid = storage_info_data['volume_id']

    docker_user = os.environ.get("DOCKER_USER", "kadalu")

    shd_required = False
    if voltype in (VOLUME_TYPE_REPLICA_3, VOLUME_TYPE_REPLICA_2):
        shd_required = True

    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "docker_user": docker_user,
        "images_hub": IMAGES_HUB,
        "volname": volname,
        "voltype": voltype,
        "volume_id": volumeid,
        "shd_required": shd_required
    }

    bricks = storage_info_data['bricks']

    # Traverse all bricks from configmap
    for brick in bricks:

        idx = brick['brick_index']
        template_args["host_brick_path"] = brick['host_brick_path']
        template_args["kube_hostname"] = brick['kube_hostname']
        template_args["serverpod_name"] = get_brick_hostname(
            volname,
            idx,
            suffix=False
        )
        template_args["brick_path"] = "/bricks/%s/data/brick" % volname
        template_args["brick_index"] = idx
        template_args["brick_device"] = brick['brick_device']
        template_args["pvc_name"] = brick['pvc_name']
        template_args["brick_device_dir"] = brick['brick_device_dir']
        template_args["brick_node_id"] = brick['node_id']
        template_args["k8s_dist"] = K8S_DIST

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        lib_execute(KUBECTL_CMD, DELETE_CMD, "-f", filename)
        logging.info(logf(
            "Deleted Server pod",
            volname=volname,
            manifest=filename,
            node=brick['node']
        ))


def delete_config_map(core_v1_client, obj):
    """
    Volinfo of existing Volume is generated and ConfigMap is deleted
    """

    volname = obj["metadata"]["name"]

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    volinfo_file = "%s.info" % volname
    configmap_data.data[volinfo_file] = None

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    logging.info(logf(
        "Deleted configmap",
        name=KADALU_CONFIG_MAP,
        volname=volname
    ))


def delete_storage_class(hostvol_name, _):
    """
    Deletes deployed External and Custom StorageClass
    """

    sc_name = "kadalu." + hostvol_name
    lib_execute(KUBECTL_CMD, DELETE_CMD, "sc", sc_name)
    logging.info(logf(
        "Deleted Storage class",
        volname=hostvol_name
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
    initial_list = crds.list_cluster_custom_object("kadalu-operator.storage",
                                                   "v1alpha1",
                                                   "kadalustorages")

    for item in initial_list.get("items"):
        handle_added(core_v1_client, item)

    metadata = initial_list.get("metadata")
    resource_version = metadata['resourceVersion']

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
    Watches the CRD to provision new PV Hosting Volumes
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
                 hostvol_name=obj["metadata"]["name"],
                 single_pv_per_pool=get_single_pv_per_pool(obj["spec"]))
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

def main():
    """Main"""
    config.load_incluster_config()

    core_v1_client = client.CoreV1Api()
    k8s_client = client.ApiClient()

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
