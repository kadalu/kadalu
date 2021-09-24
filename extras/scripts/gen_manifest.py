"""
This file is used to generate the files from template
"""

import sys
import os

from jinja2 import Template

TEMPLATES_DIR = "templates/"


def template(filename, template_file=None, template_args=None):
    """Function helping to generate final files from templates"""
    if template_file is None:
        template_file = filename + ".j2"

    template_file = TEMPLATES_DIR + template_file

    content = "# This file is autogenerated, do not edit; " \
              "changes may be undone by the next 'make gen-manifest'\n"
    with open(template_file) as tmp_file:
        content += tmp_file.read()

    Template(content).stream(
        **template_args).dump(filename)


if __name__ == "__main__":
    DOCKER_USER = os.environ.get("DOCKER_USER", "kadalu")
    KADALU_VERSION = os.environ.get("KADALU_VERSION", "latest")
    K8S_DIST = os.environ.get("K8S_DIST", "kubernetes")
    VERBOSE = os.environ.get("VERBOSE", "no")
    KUBELET_DIR = "/var/lib/kubelet"
    HTTP_PROXY = "HTTP_PROXY"
    if K8S_DIST == "microk8s":
        KUBELET_DIR = "/var/snap/microk8s/common/var/lib/kubelet"
    elif K8S_DIST == "rke":
        KUBELET_DIR = "/var/lib/kubelet"

    TEMPLATE_ARGS = {
        "namespace": "kadalu",
        "kadalu_version": KADALU_VERSION,
        "docker_user": DOCKER_USER,
        "k8s_dist": K8S_DIST,
        "kubelet_dir": KUBELET_DIR,
        "verbose": VERBOSE,
        "proxy": HTTP_PROXY,
    }

    template(sys.argv[1], template_file="operator.yaml.j2", template_args=TEMPLATE_ARGS)

    csipath = os.path.join(os.path.dirname(sys.argv[1]), "csi-nodeplugin-" + K8S_DIST + ".yaml")
    if K8S_DIST == "kubernetes":
        csipath = os.path.join(os.path.dirname(sys.argv[1]), "csi-nodeplugin.yaml")

    # Generate csi-nodeplugin too
    template(csipath, template_file="csi-nodeplugin.yaml.j2", template_args=TEMPLATE_ARGS)
