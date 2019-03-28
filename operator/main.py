"""
KaDalu Operator: Once started, deploys required CSI drivers,
bootstraps the ConfigMap and waits for the CRD update to create
Server pods
"""
import sys
import os
import subprocess
import uuid
import json

from kubernetes import client, config, watch
from jinja2 import Template


NAMESPACE = os.environ.get("KADALU_NAMESPACE", "kadalu")
VERSION = os.environ.get("KADALU_VERSION", "latest")
MANIFESTS_DIR = "/kadalu/manifests"
KUBECTL_CMD = "/usr/bin/kubectl"
KADALU_CONFIG_MAP = "kadalu-info"
CSI_POD_PREFIX = "csi-"
STORAGE_CLASS_NAME = "kadalu.gluster"
# TODO: Add ThinArbiter and Disperse
VALID_HOSTING_VOLUME_TYPES = ["Replica1", "Replica3"]
VOLUME_TYPE_REPLICA_1 = "Replica1"
VOLUME_TYPE_REPLICA_3 = "Replica3"


class CommandException(Exception):
    """Custom exception when failed to execute commands"""
    pass


def _log(logtype, msg, **kwargs):
    for msg_field_key, msg_field_value in kwargs.items():
        msg += " %s=%s" % (msg_field_key, msg_field_value)
    sys.stderr.write("%s %s\n" % (logtype, msg))


def info(msg, **kwargs):
    """Log info message"""
    _log(" INFO", msg, **kwargs)


def error(msg, **kwargs):
    """Log error"""
    _log("ERROR", msg, **kwargs)


def template(filename, **kwargs):
    """Substitute the template with provided fields"""
    content = ""
    with open(filename + ".j2") as template_file:
        content = template_file.read()

    if kwargs.get("render", False):
        return Template(content).render(**kwargs)

    return Template(content).stream(**kwargs).dump(filename)


def execute(cmd, *args):
    """
    Execute command. Return output and error
    on success. Raise CommandException on failure
    """
    proc = subprocess.Popen([cmd] + list(args), stderr=subprocess.PIPE,
                            stdout=subprocess.PIPE)
    out, err = proc.communicate()
    if proc.returncode != 0:
        raise CommandException((proc.returncode, out.strip(), err.strip()))

    return (out, err)


def bricks_validation(bricks):
    """Validate Brick path and node options"""
    ret = True
    for idx, brick in enumerate(bricks):
        if brick.get("path", None) is None:
            error("Storage path not specified", number=idx+1)
            ret = False

        if brick.get("node", None) is None:
            error("Storage node not specified", number=idx+1)
            ret = False

        if not ret:
            break

    return ret


def validate_volume_request(obj):
    """Validate the Volume request for Replica options, number of bricks etc"""
    voltype = obj["spec"].get("type", None)
    if voltype is None:
        error("PV Hosting Volume type not specified")
        return False

    if voltype not in VALID_HOSTING_VOLUME_TYPES:
        error("Invalid PV Hosting Volume type",
              valid_types=",".join(VALID_HOSTING_VOLUME_TYPES),
              provided_type=voltype)
        return False

    bricks = obj["spec"].get("storage", [])
    if not bricks_validation(bricks):
        return False

    if (voltype == VOLUME_TYPE_REPLICA_1 and len(bricks) != 1) or \
       (voltype == VOLUME_TYPE_REPLICA_3 and len(bricks) != 3):
        error("Invalid number of storage directories specified")
        return False

    return True


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
    for idx, brick in enumerate(obj["spec"]["storage"]):
        data["bricks"].append({
            "brick_path": "/data/brick",
            "node": brick["node"],
            "node_id": str(uuid.uuid1()),
            "host_brick_path": brick["path"],
            "brick_index": idx
        })

    volinfo_file = "%s.info" % volname
    configmap_data.data[volinfo_file] = json.dumps(data)

    core_v1_client.patch_namespaced_config_map(
        KADALU_CONFIG_MAP, NAMESPACE, configmap_data)
    info("Updated configmap", name=KADALU_CONFIG_MAP, volname=volname)


def deploy_server_pods(obj):
    """
    Deploy server pods depending on type of Hosting
    Volume and other options specified
    """
    # Deploy server pod
    volname = obj["metadata"]["name"]
    template_args = {
        "namespace": NAMESPACE,
        "kadalu_version": VERSION,
        "volname": volname,
        "volume_id": obj["spec"]["volume_id"]
    }

    # One StatefulSet per Brick
    for idx, brick in enumerate(obj["spec"]["storage"]):
        template_args["host_brick_path"] = brick["path"]
        template_args["kube_hostname"] = brick["node"]
        template_args["brick_path"] = "/data/brick"
        template_args["brick_index"] = idx

        filename = os.path.join(MANIFESTS_DIR, "server.yaml")
        template(filename, **template_args)
        execute(KUBECTL_CMD, "create", "-f", filename)
        info("Deployed Server pod",
             volname=volname,
             manifest=filename,
             node=brick["node"])


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
        NAMESPACE,
        include_uninitialized=True)
    for pod in pods.items:
        if pod.metadata.name.startswith("server-" + volname + "-"):
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
    info("Deployed Service", volname=volname, manifest=filename)


def handle_modified():
    """
    Handle when Volume option is updated or Volume
    state is changed to maintenence
    """
    # TODO: Handle Volume option change
    # TODO: Handle Volume maintenence mode
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
                                  "kadalu-operator.gluster",
                                  "v1alpha1",
                                  "kadaluvolumes",
                                  resource_version=resource_version):
        obj = event["object"]
        operation = event['type']
        spec = obj.get("spec")
        if not spec:
            continue
        metadata = obj.get("metadata")
        resource_version = metadata['resourceVersion']
        info("Event", operation=operation, object=repr(obj))
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
        NAMESPACE,
        include_uninitialized=True)
    for pod in pods.items:
        if pod.metadata.name.startswith(CSI_POD_PREFIX):
            return

    # Deploy CSI Pods
    filename = os.path.join(MANIFESTS_DIR, "csi.yaml")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
    execute(KUBECTL_CMD, "create", "-f", filename)
    info("Deployed CSI Pods", manifest=filename)


def deploy_config_map(core_v1_client):
    """Deploys the template configmap if not exists"""

    configmaps = core_v1_client.list_namespaced_config_map(
        NAMESPACE,
        include_uninitialized=True)
    for item in configmaps.items:
        if item.metadata.name == KADALU_CONFIG_MAP:
            return

    # Deploy Config map
    filename = os.path.join(MANIFESTS_DIR, "configmap.yaml")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
    execute(KUBECTL_CMD, "create", "-f", filename)
    info("Deployed ConfigMap", manifest=filename)


def deploy_storage_class():
    """Deploys the default storage class for KaDalu if not exists"""

    api_instance = client.StorageV1Api()
    scs = api_instance.list_storage_class(include_uninitialized=True)
    for item in scs.items:
        if item.metadata.name == STORAGE_CLASS_NAME:
            return

    # Deploy Storage Class
    filename = os.path.join(MANIFESTS_DIR, "storageclass.yaml")
    template(filename, namespace=NAMESPACE, kadalu_version=VERSION)
    execute(KUBECTL_CMD, "create", "-f", filename)
    info("Deployed StorageClass", manifest=filename)


def main():
    """Main"""
    try:
        config.load_kube_config()
    except FileNotFoundError:
        config.load_incluster_config()

    core_v1_client = client.CoreV1Api()
    k8s_client = client.ApiClient()

    # ConfigMap
    deploy_config_map(core_v1_client)

    # CSI Pods
    deploy_csi_pods(core_v1_client)

    # Storage Class
    deploy_storage_class()

    # Watch CRD
    crd_watch(core_v1_client, k8s_client)


if __name__ == "__main__":
    main()
