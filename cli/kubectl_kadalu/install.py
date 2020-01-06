import os
import yaml
import subprocess
import tempfile
import sys


KUBECTL_CMD = "kubectl"


def install_args(subparsers):
    parser_install = subparsers.add_parser('install')
    parser_install.add_argument(
        "--version",
        help="Kadalu Version to Install [default: latest]",
        choices=["0.4.0", "latest"],
        default="latest"
    )
    parser_install.add_argument(
        "--type",
        help="Type of installation - k8s/openshift [default: kubernetes]",
        choices=["openshift", "kubernetes"],
        default="kubernetes"
    )
    return


def subcmd_install(args):
    file_url = "https://raw.githubusercontent.com/kadalu/kadalu/master/manifests"
    version = ""
    insttype = ""

    if args.version and args.version != "latest":
        version = "-%s" % args.version

    if args.type and args.type == "openshift":
        insttype = "-openshift"

    operator_file = "%s/kadalu-operator%s%s.yaml" % (file_url, insttype, version)

    try:
        cmd = [KUBECTL_CMD, "apply", "-f", operator_file]
        resp = subprocess.run(cmd, capture_output=True, check=True,
                              universal_newlines=True)
        print("Kadalu operator create request sent successfully")
        print(resp.stdout)
        print()
    except subprocess.CalledProcessError as err:
        print("Error while running the following command", file=sys.stderr)
        print("$ " + " ".join(cmd), file=sys.stderr)
        print("", file=sys.stderr)
        print(err.stderr, file=sys.stderr)
        sys.exit(1)

    return
