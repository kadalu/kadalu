import sys
import os

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
        "namespace": "kadalu",
        "kadalu_version": "latest",
    }

    template("00-namespace.yaml", template_args=template_args)
    template("operator.yaml", template_args=template_args)

