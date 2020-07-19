"""
Generate Yaml for Kadalu Storage
"""
from string import Template

YAML_TEMPLATE = """apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "${name}"
spec:
  type: "${type}"
  storage:"""

STORAGE_DEV_TMPL = """    - node: "${node}"
      device: "${device}"
"""

STORAGE_PATH_TMPL = """    - node: "${node}"
      path: "${path}"
"""

STORAGE_PVC_TMPL = """    - pvc: "${pvc}"
"""

EXTERNAL_TMPL = """    - gluster_host: "${gluster_host}"
      gluster_volname: "${gluster_volname}"
      gluster_options: "${gluster_options}"
"""

TIEBREAKER_TMPL = """  tiebreaker:
    node: "${node}"
    path: "${path}"
    port: ${port}
"""


def to_storage_yaml(data):
    """Convert Python dict to yaml format"""
    yaml = Template(YAML_TEMPLATE).substitute(name=data["metadata"]["name"],
                                              type=data["spec"]["type"])
    if len(data["spec"].get("storage", [])) == 0:
        yaml += " []\n"
    else:
        yaml += "\n"

    if data["spec"].get("storage", None) is not None:
        for storage in data["spec"]["storage"]:
            if storage.get("device", None) is not None:
                yaml += Template(STORAGE_DEV_TMPL).substitute(**storage)
            elif storage.get("path", None) is not None:
                yaml += Template(STORAGE_PATH_TMPL).substitute(**storage)
            elif storage.get("pvc", None) is not None:
                yaml += Template(STORAGE_PVC_TMPL).substitute(**storage)

    if data["spec"].get("details", None) is not None:
        yaml += "  details:\n"
        for entry in data["spec"]["details"]:
            if entry.get("gluster_options", None) is None:
                entry["gluster_options"] = "log-level=INFO"
            yaml += Template(EXTERNAL_TMPL).substitute(**entry)

    if data["spec"].get("tiebreaker", None) is not None:
        yaml += Template(TIEBREAKER_TMPL).substitute(**data["spec"]["tiebreaker"])

    return yaml
