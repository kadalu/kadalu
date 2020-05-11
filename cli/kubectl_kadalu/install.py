"""
'install' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import sys

from kubectl_kadalu import utils

def install_args(subparsers):
    """ add arguments to argparser """
    parser_install = subparsers.add_parser('install')
    parser_install.add_argument(
        "--version",
        help="Kadalu Version to Install [default: latest]",
        choices=["0.6.0", "latest"],
        default="latest"
    )
    parser_install.add_argument(
        "--type",
        help="Type of installation - k8s/openshift [default: kubernetes]",
        choices=["openshift", "kubernetes"],
        default="kubernetes"
    )
    parser_install.add_argument(
        "--local-yaml",
        help="local operator yaml file path"
    )


def subcmd_install(args):
    """ perform install subcommand """
    operator_file = args.local_yaml
    if not operator_file:
        file_url = "https://raw.githubusercontent.com/kadalu/kadalu/master/manifests"
        version = ""
        insttype = ""

        if args.version and args.version != "latest":
            version = "-%s" % args.version

            if args.type and args.type == "openshift":
                insttype = "-openshift"

        operator_file = "%s/kadalu-operator%s%s.yaml" % (file_url, insttype, version)

    try:
        cmd = [utils.KUBECTL_CMD, "apply", "-f", operator_file]
        print("Executing '%s'" % cmd)
        resp = utils.execute(cmd)
        print("Kadalu operator create request sent successfully")
        print(resp.stdout)
        print()
    #noqa #pylint : disable=R0801
    except utils.CommandError as err:
        print("Error while running the following command", file=sys.stderr)
        print("$ " + " ".join(cmd), file=sys.stderr)
        print("", file=sys.stderr)
        print(err.stderr, file=sys.stderr)
        sys.exit(1)
