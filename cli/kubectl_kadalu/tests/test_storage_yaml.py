from kubectl_kadalu.storage_yaml import to_storage_yaml

API_VERSION = "kadalu-operator.storage/v1alpha1"
KIND = "KadaluStorage"
REPLICA_1 = "Replica1"
REPLICA_2 = "Replica2"
REPLICA_3 = "Replica3"
EXTERNAL = "External"
STORAGE_POOL_NAME = "storage-pool"
NODE_1 = "node1.example.com"
NODE_2 = "node2.example.com"
NODE_3 = "node3.example.com"
DEVICE_1 = "/dev/sdc"
DEVICE_2 = "/dev/sdc"
DEVICE_3 = "/dev/sdc"
PATH_1 = "/exports/kadalu/storage1"
PATH_2 = "/exports/kadalu/storage2"
PATH_3 = "/exports/kadalu/storage3"
PVC_1 = "pvc1"
PVC_2 = "pvc2"
PVC_3 = "pvc3"
EXTERNAL_HOST = "gluster1.kadalu.io"
EXTERNAL_VOLNAME = "kadalu"
EXTERNAL_OPTIONS = "log-level=DEBUG"

REPLICA1_DEVICE_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_1}"
  storage:
    - node: "{NODE_1}"
      device: "{DEVICE_1}"
"""

REPLICA2_DEVICE_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_2}"
  storage:
    - node: "{NODE_1}"
      device: "{DEVICE_1}"
    - node: "{NODE_2}"
      device: "{DEVICE_2}"
"""

REPLICA3_DEVICE_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_3}"
  storage:
    - node: "{NODE_1}"
      device: "{DEVICE_1}"
    - node: "{NODE_2}"
      device: "{DEVICE_2}"
    - node: "{NODE_3}"
      device: "{DEVICE_3}"
"""

def test_replica1_storage_device():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_1,
            "storage": [
                {
                    "node": NODE_1,
                    "device": DEVICE_1
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA1_DEVICE_OUTPUT)


def test_replica2_storage_device():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_2,
            "storage": [
                {
                    "node": NODE_1,
                    "device": DEVICE_1
                },
                {
                    "node": NODE_2,
                    "device": DEVICE_2
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA2_DEVICE_OUTPUT)


def test_replica3_storage_device():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_3,
            "storage": [
                {
                    "node": NODE_1,
                    "device": DEVICE_1
                },
                {
                    "node": NODE_2,
                    "device": DEVICE_2
                },
                {
                    "node": NODE_3,
                    "device": DEVICE_3
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA3_DEVICE_OUTPUT)


REPLICA1_PATH_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_1}"
  storage:
    - node: "{NODE_1}"
      path: "{PATH_1}"
"""

REPLICA2_PATH_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_2}"
  storage:
    - node: "{NODE_1}"
      path: "{PATH_1}"
    - node: "{NODE_2}"
      path: "{PATH_2}"
"""

REPLICA3_PATH_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_3}"
  storage:
    - node: "{NODE_1}"
      path: "{PATH_1}"
    - node: "{NODE_2}"
      path: "{PATH_2}"
    - node: "{NODE_3}"
      path: "{PATH_3}"
"""

def test_replica1_storage_path():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_1,
            "storage": [
                {
                    "node": NODE_1,
                    "path": PATH_1
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA1_PATH_OUTPUT)


def test_replica2_storage_path():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_2,
            "storage": [
                {
                    "node": NODE_1,
                    "path": PATH_1
                },
                {
                    "node": NODE_2,
                    "path": PATH_2
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA2_PATH_OUTPUT)


def test_replica3_storage_path():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_3,
            "storage": [
                {
                    "node": NODE_1,
                    "path": PATH_1
                },
                {
                    "node": NODE_2,
                    "path": PATH_2
                },
                {
                    "node": NODE_3,
                    "path": PATH_3
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA3_PATH_OUTPUT)


REPLICA1_PVC_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_1}"
  storage:
    - pvc: "{PVC_1}"
"""

REPLICA2_PVC_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_2}"
  storage:
    - pvc: "{PVC_1}"
    - pvc: "{PVC_2}"
  tiebreaker:
    node: "tie-breaker.kadalu.io"
    path: "/mnt"
    port: 24007
"""

REPLICA3_PVC_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{REPLICA_3}"
  storage:
    - pvc: "{PVC_1}"
    - pvc: "{PVC_2}"
    - pvc: "{PVC_3}"
"""

def test_replica1_storage_pvc():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_1,
            "storage": [
                {
                    "pvc": PVC_1
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA1_PVC_OUTPUT)


def test_replica2_storage_pvc():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_2,
            "storage": [
                {
                    "pvc": PVC_1
                },
                {
                    "pvc": PVC_2
                }
            ],
            "tiebreaker": {
                "node": "tie-breaker.kadalu.io",
                "port": 24007,
                "path": "/mnt"
            }
        }
    }
    assert (to_storage_yaml(content) == REPLICA2_PVC_OUTPUT)


def test_replica3_storage_pvc():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": REPLICA_3,
            "storage": [
                {
                    "pvc": PVC_1
                },
                {
                    "pvc": PVC_2
                },
                {
                    "pvc": PVC_3
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == REPLICA3_PVC_OUTPUT)


EXTERNAL_OUTPUT = f"""apiVersion: "{API_VERSION}"
kind: "{KIND}"
metadata:
  name: "{STORAGE_POOL_NAME}"
spec:
  type: "{EXTERNAL}"
  storage: []
  details:
    - gluster_host: "{EXTERNAL_HOST}"
      gluster_volname: "{EXTERNAL_VOLNAME}"
      gluster_options: "{EXTERNAL_OPTIONS}"
"""

def test_external_storage():
    content = {
        "metadata": {
            "name": STORAGE_POOL_NAME
        },
        "spec": {
            "type": EXTERNAL,
            "details": [
                {
                    "gluster_host": EXTERNAL_HOST,
                    "gluster_volname": EXTERNAL_VOLNAME,
                    "gluster_options": EXTERNAL_OPTIONS
                }
            ]
        }
    }
    assert (to_storage_yaml(content) == EXTERNAL_OUTPUT)
