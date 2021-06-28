from string import Template

CUSTOM_SC_TEMPLATE = """kind: StorageClass
apiVersion: storage.k8s.io/v1
metadata:
  name: kadalu.${hostvol_name}
provisioner: kadalu
allowVolumeExpansion: true
parameters:
  hostvol_type: "${type}"
  storage_name: "${hostvol_name}"
"""

def to_sc_yaml(obj):
    """Add details to custom storage class from obj and convert to YAML"""
    sc_yaml = Template(CUSTOM_SC_TEMPLATE).substitute(hostvol_name=obj["metadata"]["name"],
                                                 type=obj["spec"]["type"])
    return sc_yaml