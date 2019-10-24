import sys
import os

from jinja2 import Template

TEMPLATES_DIR = "templates/"


def template(filename, template_file=None, template_args={}):
    if template_file is None:
        template_file = filename + ".j2"

    filename = TEMPLATES_DIR + filename
    template_file = TEMPLATES_DIR + template_file

    content = ""
    with open(template_file) as f:
        content = f.read()

    Template(content).stream(
        **template_args).dump(filename)


if __name__ == "__main__":
    docker_user = os.environ.get("DOCKER_USER", "kadalu")
    kadalu_version = os.environ.get("KADALU_VERSION", "latest")
    openshift = bool(int(os.environ.get("OPENSHIFT", 0)))
    template_args = {
        "namespace": "kadalu",
        "kadalu_version": kadalu_version,
        "docker_user": docker_user,
        "openshift": openshift
    }

    template("namespace.yaml", template_args=template_args)
    template("operator.yaml", template_args=template_args)

