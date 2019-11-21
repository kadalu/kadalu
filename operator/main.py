"""
KaDalu Operator: Once started, deploys required CSI drivers,
bootstraps the ConfigMap and waits for the CRD update to create
Server pods
"""
import os
import uuid
import json
import logging
import requests

from kubernetes import client, config, watch
from jinja2 import Template

from kadalulib import execute, logging_setup, logf, send_analytics_tracker


NAMESPACE = os.environ.get("KADALU_NAMESPACE", "kadalu")
VERSION = os.environ.get("KADALU_VERSION", "latest")
MANIFESTS_DIR = "/kadalu/templates"
KUBECTL_CMD = "/usr/bin/kubectl"
KADALU_CONFIG_MAP = "kadalu-info"
CSI_POD_PREFIX = "csi-"
STORAGE_CLASS_NAME_PREFIX = "kadalu."
# TODO: Add ThinArbiter and Disperse
VALID_HOSTING_VOLUME_TYPES = ["Replica1", "Replica3"]
VOLUME_TYPE_REPLICA_1 = "Replica1"
VOLUME_TYPE_REPLICA_3 = "Replica3"


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
        if brick.get("path", None) is None and \
           brick.get("device", None) is None:
            logging.error(logf("Storage path/device not specified", number=idx+1))
            ret = False

        if brick.get("node", None) is None:
            logging.error(logf("Storage node not specified", number=idx+1))
            ret = False

        if not ret:
            break

    return ret


def validate_volume_request(obj):
    """Validate the Volume request for Replica options, number of bricks etc"""
    voltype = obj["spec"].get("type", None)
    if voltype is None:
        logging.error("Storage type not specified")
        return False

    if voltype not in VALID_HOSTING_VOLUME_TYPES:
        logging.error(logf("Invalid Storage type",
                           valid_types=",".join(VALID_HOSTING_VOLUME_TYPES),
                           provided_type=voltype))
        return False

    bricks = obj["spec"].get("storage", [])
    if not bricks_validation(bricks):
        return False

    if (voltype == VOLUME_TYPE_REPLICA_1 and len(bricks) != 1) or \
       (voltype == VOLUME_TYPE_REPLICA_3 and len(bricks) != 3):
        logging.error("Invalid number of storage directories/devices"
                      " specified")
        return False

    return True


def get_brick_device_dir(brick):
    # If custom file is passed as brick device then the
    # parent directory needs to be mounted as is
    # in server container
    brick_device_dir = ""
    logging.info(repr(brick))
    brickdev = brick.get("device", "")
    logging.info(brickdev)
    if brickdev != "" and not brickdev.startswith("/dev/"):
        brick_device_dir = os.path.dirname(brickdev)

    return brick_device_dir


def get_brick_hostname(volname, node, idx, suffix=True):
    # Brick hostname is <statefulset-name>-<ordinal>.<service-name>
    # statefulset name is the one which is visible when the
    # `get pods` command is run, so the format used for that name
    # is "server-<volname>-<idx>-<hostname>". Escape dots from the
    # hostname from the input otherwise will become invalid name.
    # Service is created with name as Volume name. For example,
    # brick_hostname will be "server-spool1-0-minikube-0.spool1" and
    # server pod name will be "server-spool1-0-minikube"
    hostname = "server-%s-%d-%s" % (volname, idx, node.replace(".", "-"))
    if suffix:
        return "%s-0.%s" % (hostname, volname)

    return hostname


def update_config_map(core_v1_client, obj):
    """
    Volinfo of new hosting Volume is generated and updated to ConfigMap
    """
    volname = obj["metadata"]["name"]
    data = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "volname": volname,
        "volume_id": obj["spec"]["volume_id"],
        "type": obj["spec"]["type"],
        "bricks": [],
        "options": obj["spec"].get("options", {})
    }

    # Add new entry in the existing config map
    configmap_data = core_v1_client.read_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE)

    # For each brick, add brick path and node id
    for idx, storage in enumerate(obj["spec"]["storage"]):
        data["bricks"].append({
            "brick_path": "/bricks/%s/data/brick" % volname,
            "node": get_brick_hostname(volname, storage["node"], idx),
            "node_id": str(uuid.uuid1()),
            "host_brick_path": storage.get("path", ""),
            "brick_device": storage.get("device", ""),
            "brick_device_dir": get_brick_device_dir(storage),
            "brick_index": idx
        })

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
    docker_user = os.environ.get("DOCKER_USER", "kadalu")
    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "docker_user": docker_user,
        "volname": volname,
        "volume_id": obj["spec"]["volume_id"]
    }

    # One StatefulSet per Brick
    for idx, storage in enumerate(obj["spec"]["storage"]):
        template_args["host_brick_path"] = storage.get("path", "")
        template_args["kube_hostname"] = storage["node"]
        # TODO: Understand the need, and usage of suffix
        template_args["serverpod_name"] = get_brick_hostname(
            volname,
            storage["node"],
            idx,
            suffix=False
        )
        template_args["brick_path"] = "/bricks/%s/data/brick" % volname
        template_args["brick_index"] = idx
        template_args["brick_device"] = storage.get("device", "")
        template_args["brick_device_dir"] = get_brick_device_dir(storage)

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        execute(KUBECTL_CMD, "create", "-f", filename)
        logging.info(logf("Deployed Server pod",
                          volname=volname,
                          manifest=filename,
                          node=storage["node"]))


def handle_added(core_v1_client, obj):
    """
    New Volume is requested. Update the configMap and deploy
    """

    if not validate_volume_request(obj):
        # TODO: Delete Custom resource
        return

    # Ignore if already deployed
    volname = obj["metadata"]["name"]
    pods = core_v1_client.list_namespaced_pod(
        NAMESPACE)
    for pod in pods.items:
        if pod.metadata.name.startswith("server-" + volname + "-"):
            logging.debug(logf(
                "Ignoring already deployed server statefulsets",
                storagename=volname
            ))
            return

    # Generate new Volume ID
    obj["spec"]["volume_id"] = str(uuid.uuid1())

    update_config_map(core_v1_client, obj)
    deploy_server_pods(obj)

    # Deploy service(One service per Volume)
    volname = obj["metadata"]["name"]
    filename = os.path.join(MANIFESTS_DIR, "services.yaml")
    template(filename, namespace=NAMESPACE, volname=volname)
    execute(KUBECTL_CMD, "create", "-f", filename)
    logging.info(logf("Deployed Service", volname=volname, manifest=filename))


def handle_modified():
    """
    Handle when Volume option is updated or Volume
    state is changed to maintenance
    """
    # TODO: Handle Volume option change
    # TODO: Handle Volume maintenance mode
    pass


def handle_deleted():
    """
    If number of pvs provisioned from that volume
    is zero - Delete the respective server pods
    If number of pvs is not zero, wait or periodically
    check for num_pvs. Delete Server pods only when pvs becomes zero.
    """
    # TODO
    pass


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
            handle_modified()
        elif operation == "DELETED":
            handle_deleted()


def deploy_csi_pods(core_v1_client):
    """
    Look for CSI pods, if any one CSI pod found then
    that means it is deployed
    """
    pods = core_v1_client.list_namespaced_pod(
        NAMESPACE)
    for pod in pods.items:
        if pod.metadata.name.startswith(CSI_POD_PREFIX):
            logging.debug("Ignoring already deployed CSI pods")
            return

    # Deploy CSI Pods
    filename = os.path.join(MANIFESTS_DIR, "csi.yaml")
    docker_user = os.environ.get("DOCKER_USER", "kadalu")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION,
             docker_user=docker_user)
    execute(KUBECTL_CMD, "create", "-f", filename)
    logging.info(logf("Deployed CSI Pods", manifest=filename))


def deploy_config_map(core_v1_client):
    """Deploys the template configmap if not exists"""

    configmaps = core_v1_client.list_namespaced_config_map(
        NAMESPACE)
    for item in configmaps.items:
        if item.metadata.name == KADALU_CONFIG_MAP:
            logging.debug(logf(
                "Found existing configmap",
                name=item.metadata.name
            ))
            return

    # Deploy Config map
    filename = os.path.join(MANIFESTS_DIR, "configmap.yaml")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
    execute(KUBECTL_CMD, "create", "-f", filename)
    logging.info(logf("Deployed ConfigMap", manifest=filename))


def deploy_storage_class():
    """Deploys the default storage class for KaDalu if not exists"""

    api_instance = client.StorageV1Api()
    scs = api_instance.list_storage_class()
    for item in scs.items:
        if item.metadata.name.startswith(STORAGE_CLASS_NAME_PREFIX):
            return

    # Deploy Storage Class
    filename = os.path.join(MANIFESTS_DIR, "storageclass.yaml")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
    execute(KUBECTL_CMD, "create", "-f", filename)
    logging.info(logf("Deployed StorageClass", manifest=filename))

def main():
    """Main"""
    config.load_incluster_config()

    core_v1_client = client.CoreV1Api()
    k8s_client = client.ApiClient()

    # ConfigMap
    deploy_config_map(core_v1_client)

    # CSI Pods
    deploy_csi_pods(core_v1_client)

    # Storage Class
    deploy_storage_class()

    # Send Analytics Tracker
    # The information from this analytics is available for
    # developers to understand and build project in a better
    # way
    send_analytics_tracker("operator")

    # Watch CRD
    crd_watch(core_v1_client, k8s_client)


if __name__ == "__main__":
    logging_setup()
    main()
