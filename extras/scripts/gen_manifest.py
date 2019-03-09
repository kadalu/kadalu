import sys

from jinja2 import Template

MANIFESTS_DIR = "manifests/"


def template(filename, template_file=None, template_args={}):
    if template_file is None:
        template_file = filename + ".j2"

    filename = MANIFESTS_DIR + filename
    template_file = MANIFESTS_DIR + template_file

    content = ""
    with open(template_file) as f:
        content = f.read()

    Template(content).stream(
        **template_args).dump(filename)


if __name__ == "__main__":
    template_args = {
        "volname": "glustervol",
        "kube_hostname": sys.argv[1],
        "namespace": "kadalu",
        "brick_path": "/data/brick",
        "host_brick_path": sys.argv[2],
        "kadalu_version": "latest",
    }

    manifest_files = [
        "namespace.yaml",
        "configmap.yaml",
        "server.yaml",
        "csi.yaml",
        "storageclass.yaml",
        "services.yaml",
        "sample-app.yaml"
    ]

    for filename in manifest_files:
        template(filename, template_args=template_args)
        print("kubectl create -f manifests/%s" % filename)

