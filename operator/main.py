"""
KaDalu Operator: Once started, deploys required CSI drivers,
bootstraps the ConfigMap and waits for the CRD update to create
Server pods
"""
import os
import uuid
import json
import logging
import re
import socket

from jinja2 import Template
from kubernetes import client, config, watch

from kadalulib import execute as lib_execute, logging_setup, logf, send_analytics_tracker
from utils import execute as utils_execute, CommandError

NAMESPACE = os.environ.get("KADALU_NAMESPACE", "kadalu")
VERSION = os.environ.get("KADALU_VERSION", "latest")
K8S_DIST = os.environ.get("K8S_DIST", "kubernetes")
KUBELET_DIR = os.environ.get("KUBELET_DIR")
MANIFESTS_DIR = "/kadalu/templates"
KUBECTL_CMD = "/usr/bin/kubectl"
KADALU_CONFIG_MAP = "kadalu-info"
CSI_POD_PREFIX = "csi-"
STORAGE_CLASS_NAME_PREFIX = "kadalu."
# TODO: Add ThinArbiter and Disperse
VALID_HOSTING_VOLUME_TYPES = ["Replica1", "Replica2", "Replica3", "External"]
VOLUME_TYPE_REPLICA_1 = "Replica1"
VOLUME_TYPE_REPLICA_2 = "Replica2"
VOLUME_TYPE_REPLICA_3 = "Replica3"
VOLUME_TYPE_EXTERNAL = "External"

CREATE_CMD = "apply"
DELETE_CMD = "delete"

def template(filename, **kwargs):
    """Substitute the template with provided fields"""
    content = ""
    with open(filename + ".j2") as template_file:
        content = template_file.read()

    if kwargs.get("render", False):
        return Template(content).render(**kwargs)

    return Template(content).stream(**kwargs).dump(filename)


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
            logging.error(logf("Storage path/device not specified", number=idx+1))
            ret = False

        if brick.get("node", None) is None:
            logging.error(logf("Storage node not specified", number=idx+1))
            ret = False

    return ret


def is_host_reachable(host, port):
    """Check if glusterd is reachable in the given node"""
    timeout = 5
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        sock.connect((host, int(port)))
        sock.shutdown(socket.SHUT_RDWR)
        return True
    except socket.error as msg:
        logging.error(logf("Failed to open socket connection", error=msg))
        return False
    finally:
        sock.close()

def validate_ext_details(obj):
    """Validate external Volume details"""
    clusterdata = obj["spec"].get("details", None)
    if not clusterdata:
        logging.error(logf("External Cluster details not given."))
        return False

    valid = 0
    if len(clusterdata) > 1:
        logging.error(logf("Multiple External Cluster details given."))
        return False

    ghost = None
    gport = 24007
    for cluster in clusterdata:
        if cluster.get('gluster_host', None):
            valid += 1
            ghost = cluster.get('gluster_host', None)
        if cluster.get('gluster_volname', None):
            valid += 1
        if cluster.get('gluster_port', None):
            gport = cluster.get('gluster_port', 24007)

    if valid != 2:
        logging.error(logf("No 'host' and 'volname' details provided."))
        return False

    if not is_host_reachable(ghost, gport):
        logging.error(logf("gluster server not reachable: on %s:%d" %
                           (ghost, gport)))
        #  Noticed that there may be glitches in n/w during this time.
        #  Not good to fail the validation, instead, just log here, so
        #  we are aware this is a possible reason.
        #return False

    logging.debug(logf("External Storage %s successfully validated" % \
                       obj["metadata"].get("name", "<unknown>")))
    return True


# pylint: disable=too-many-return-statements
def validate_volume_request(obj):
    """Validate the Volume request for Replica options, number of bricks etc"""
    if not obj.get("spec", None):
        logging.error("Storage 'spec' not specified")
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

    bricks = obj["spec"].get("storage", [])
    if not bricks_validation(bricks):
        return False

    if (voltype == VOLUME_TYPE_REPLICA_1 and len(bricks) != 1) or \
       (voltype == VOLUME_TYPE_REPLICA_3 and len(bricks) != 3):
        logging.error("Invalid number of storage directories/devices"
                      " specified")
        return False

    if voltype == VOLUME_TYPE_REPLICA_2:
        if len(bricks) != 2:
            logging.error("Invalid number of storage directories/devices"
                          " specified")
            return False

        tiebreaker = obj["spec"].get("tiebreaker", None)
        if tiebreaker and (not tiebreaker.get("node", None) or
                           not tiebreaker.get("path", None)):
            logging.error(logf("'tiebreaker' provided for replica2 "
                               "config is not valid"))
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


def update_config_map(core_v1_client, obj):
    """
    Volinfo of new hosting Volume is generated and updated to ConfigMap
    """
    volname = obj["metadata"]["name"]
    voltype = obj["spec"]["type"]
    volume_id = obj["spec"]["volume_id"]

    data = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "volname": volname,
        "volume_id": volume_id,
        "type": voltype,
        "bricks": [],
        "options": obj["spec"].get("options", {})
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

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
            "brick_index": idx
        })

    if voltype == VOLUME_TYPE_REPLICA_2:
        tiebreaker = obj["spec"].get("tiebreaker", None)
        if not tiebreaker:
            logging.warning(logf("No 'tiebreaker' provided for replica2 "
                                 "config. Using default tie-breaker.kadalu.io:/mnt",
                                 volname=volname))
            # Add default tiebreaker if no tie-breaker option provided
            tiebreaker = {
                "node": "tie-breaker.kadalu.io",
                "path": "/mnt",
            }
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
    docker_user = os.environ.get("DOCKER_USER", "kadalu")

    shd_required = False
    if voltype in (VOLUME_TYPE_REPLICA_3, VOLUME_TYPE_REPLICA_2):
        shd_required = True

    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "docker_user": docker_user,
        "volname": volname,
        "voltype": voltype,
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

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
        logging.info(logf("Deployed Server pod",
                          volname=volname,
                          manifest=filename,
                          node=storage.get("node", "")))


def handle_external_storage_addition(core_v1_client, obj):
    """Deploy service(One service per Volume)"""
    volname = obj["metadata"]["name"]
    details = obj["spec"]["details"][0]

    data = {
        "volname": volname,
        "volume_id": obj["spec"]["volume_id"],
        "type": VOLUME_TYPE_EXTERNAL,
        "kadalu-format": True,
        "gluster_host": details["gluster_host"],
        "gluster_volname": details["gluster_volname"],
        "gluster_options": details.get("gluster_options", "ignore-me"),
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
    lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
    logging.info(logf("Deployed External StorageClass", volname=volname, manifest=filename))


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
        logging.debug(logf(
            "Ignoring already updated volume config",
            storagename=volname
        ))
        return

    # Generate new Volume ID
    obj["spec"]["volume_id"] = str(uuid.uuid1())

    voltype = obj["spec"]["type"]
    if voltype == VOLUME_TYPE_EXTERNAL:
        handle_external_storage_addition(core_v1_client, obj)
        return

    # Generate Node ID for each storage device.
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = str(uuid.uuid1())

    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, volname=volname)
    lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
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

    # It doesn't make sense to support Replica1 also in this operation.
    if voltype == VOLUME_TYPE_REPLICA_1:
        # Modification of 'External' volume type is not supported
        logging.info(logf(
            "Modification of '%s' volume type is not supported" % VOLUME_TYPE_REPLICA_1,
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
        # Volume doesn't exists
        logging.error(logf(
            "Volume config not found",
            storagename=volname
        ))
        return

    # Volume ID (uuid) is already generated, re-use
    cfgmap = json.loads(configmap_data.data[volname + ".info"])
    # Get volume-id from config map
    obj["spec"]["volume_id"] = cfgmap["volume_id"]

    # Set Node ID for each storage device from configmap
    for idx, _ in enumerate(obj["spec"]["storage"]):
        obj["spec"]["storage"][idx]["node_id"] = cfgmap["bricks"][idx]["node_id"]

    # Add new entry in the existing config map
    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, volname=volname)
    lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
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

    logging.warning(logf(
        "Delete requested",
        volname=volname
    ))

    pv_count = get_num_pvs(storage_info_data)

    if pv_count != 0:

        logging.error(logf(
            "Storage delete failed. Storage is not empty",
            number_of_pvs=pv_count,
            storage=volname
        ))

    elif pv_count == 0:

        delete_server_pods(storage_info_data, obj)
        delete_config_map(core_v1_client, obj)

        filename = os.path.join(MANIFESTS_DIR, "services.yaml")
        template(filename, namespace=NAMESPACE, volname=volname)
        lib_execute(KUBECTL_CMD, DELETE_CMD, "-f", filename)
        logging.info(logf(
            "Deleted Service",
            volname=volname,
            manifest=filename
        ))


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


def get_num_pvs(storage_info_data):
    """
    Get number of PVs provisioned from
    volume requested for deletion
    through configmap.
    """

    volname = storage_info_data['volname']
    bricks = storage_info_data['bricks']

    dbpath = "/bricks/" + volname + "/data/brick/stat.db"
    query = ("select count(pvname) from pv_stats;")

    cmd = ["kubectl", "exec", "-i",
           bricks[0]['node'].replace("." + volname, ""),
           "-c", "glusterfsd", "-nkadalu", "--", "sqlite3",
           dbpath,
           query]

    try:
        resp = utils_execute(cmd)
        parts = resp.stdout.strip().split("\n")
        pv_count = int(parts[0].strip())

        return pv_count

    except CommandError as msg:
        logging.error(logf(
            "Failed to get size details of the "
            "storage \"%s\"" % volname,
            error=msg
        ))
        # Set default as 0
        return 0


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


def crd_watch(core_v1_client, k8s_client):
    """
    Watches the CRD to provision new PV Hosting Volumes
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
       api_instance.minor >= "14":
        filename = os.path.join(MANIFESTS_DIR, "csi-driver-object.yaml")
        template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
        lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
    else:
        filename = os.path.join(MANIFESTS_DIR, "csi-driver-crd.yaml")
        template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
        lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)

    filename = os.path.join(MANIFESTS_DIR, "csi.yaml")
    docker_user = os.environ.get("DOCKER_USER", "kadalu")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION,
             docker_user=docker_user, k8s_dist=K8S_DIST,
             kubelet_dir=KUBELET_DIR)

    lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
    logging.info(logf("Deployed CSI Pods", manifest=filename))


def deploy_config_map(core_v1_client):
    """Deploys the template configmap if not exists"""

    configmaps = core_v1_client.list_namespaced_config_map(
        NAMESPACE)
    uid = uuid.uuid4()
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
            # Keep the config details required to be preserved.

    # Deploy Config map
    filename = os.path.join(MANIFESTS_DIR, "configmap.yaml")
    template(filename,
             namespace=NAMESPACE,
             kadalu_version=VERSION,
             uid=uid)

    lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
    logging.info(logf("Deployed ConfigMap", manifest=filename))
    return uid


def deploy_storage_class():
    """Deploys the default storage class for KaDalu if not exists"""

    api_instance = client.StorageV1Api()
    scs = api_instance.list_storage_class()
    sc_names = []
    for tmpl in os.listdir(MANIFESTS_DIR):
        if tmpl.startswith("storageclass-"):
            sc_names.append(
                tmpl.replace("storageclass-", "").replace(".yaml.j2", "")
            )

    installed_scs = [item.metadata.name for item in scs.items]
    for sc_name in sc_names:
        filename = os.path.join(MANIFESTS_DIR, "storageclass-%s.yaml" % sc_name)
        if sc_name in installed_scs:
            logging.info(logf("Ignoring already deployed StorageClass",
                              manifest=filename))
            continue

        # Deploy Storage Class
        template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
        lib_execute(KUBECTL_CMD, CREATE_CMD, "-f", filename)
        logging.info(logf("Deployed StorageClass", manifest=filename))


def main():
    """Main"""
    config.load_incluster_config()

    # As per the issue https://github.com/kubernetes-client/python/issues/254
    clnt = client.Configuration() #go and get a copy of the default config
    clnt.verify_ssl = False #set verify_ssl to false in that config
    client.Configuration.set_default(clnt) #make that config the default for all new clients

    core_v1_client = client.CoreV1Api()
    k8s_client = client.ApiClient()

    # ConfigMap
    uid = deploy_config_map(core_v1_client)

    # CSI Pods
    deploy_csi_pods(core_v1_client)

    # Storage Class
    deploy_storage_class()

    # Send Analytics Tracker
    # The information from this analytics is available for
    # developers to understand and build project in a better
    # way
    send_analytics_tracker("operator", uid)

    # Watch CRD
    crd_watch(core_v1_client, k8s_client)


if __name__ == "__main__":
    logging_setup()
    main()
