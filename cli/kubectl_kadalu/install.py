"""
'install' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import json
import utils
from version import VERSION


def set_args(name, subparsers):
    """ add arguments to argparser """
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg(
        "--version",
        help="Kadalu Version to Install [default: " + VERSION + "]",
        choices=[VERSION, "devel"],
        default=VERSION
    )
    arg(
        "--type",
        help="Type of installation - k8s/openshift [default: kubernetes]",
        choices=["openshift", "kubernetes", "microk8s", "rke"],
        default="kubernetes"
    )
    arg(
        "--local-yaml",
        help="local operator yaml file path"
    )
    arg(
        "--local-csi-yaml",
        help="local csi-nodeplugin yaml file path"
    )
    utils.add_global_flags(parser)


def validate(_args):
    """No validation available"""
    return

# noqa # pylint: disable=too-many-branches
def run(args):
    """ perform install subcommand """

    # Check if kadalu operator is present already.
    try:
        cmd = utils.kubectl_cmd(args) + ["get", "deployments", "-nkadalu", "-ojson"]
        resp = utils.execute(cmd)
        data = json.loads(resp.stdout)
        items = data["items"]

        if items:
            operator = items[0]["metadata"].get("name")
            namespace = items[0]["metadata"].get("namespace")

            if operator is not None and namespace is not None:
                print("Kadalu operator already installed")
                return

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)

    file_url = ""
    insttype = ""
    if args.version and args.version == "devel":
        file_url = "https://raw.githubusercontent.com/kadalu/kadalu/devel/manifests"
    elif args.version:
        file_url = f"https://github.com/kadalu/kadalu/releases/download/{args.version}"

    if args.type and args.type != "kubernetes":
        insttype = f"-{args.type}"

    operator_file = args.local_yaml
    if not operator_file:
        operator_file = f"{file_url}/kadalu-operator{insttype}.yaml"

    csi_file = args.local_csi_yaml
    if not csi_file:
        csi_file = f"{file_url}/csi-nodeplugin{insttype}.yaml"

    try:
        cmd = utils.kubectl_cmd(args) + ["apply", "-f", operator_file]
        print(f'Executing \'{" ".join(cmd)}\'')
        if args.dry_run:
            return

        resp = utils.execute(cmd)
        print("Kadalu operator create request sent successfully")
        print(resp.stdout)
        print()

        cmd = utils.kubectl_cmd(args) + ["apply", "-f", csi_file]
        print('Executing \'{" ".join(cmd)}\'')
        if args.dry_run:
            return

        resp = utils.execute(cmd)
        print("Kadalu CSI-nodeplugin create request sent successfully")
        print(resp.stdout)
        print()
    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
