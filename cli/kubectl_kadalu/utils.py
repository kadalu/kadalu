"""
Utility methods for the CLI tool
"""
from __future__ import print_function
import subprocess
import json
import sys

KUBECTL_CMD = "kubectl"

# noqa # pylint: disable=too-many-instance-attributes
# noqa # pylint: disable=useless-object-inheritance
# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=bad-option-value
class CmdResponse(object):
    """ Class for checking the response """
    def __init__(self, returncode, out, err):
        self.returncode = returncode
        self.stdout = out
        self.stderr = err

class CommandError(Exception):
    """ Class for handling exceptions """
    def __init__(self, returncode, err):
        super().__init__(u"error %d %s" % (returncode, err))
        self.returncode = returncode
        self.stderr = err

# noqa # pylint: disable=too-many-instance-attributes
# noqa # pylint: disable=useless-object-inheritance
# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=bad-option-value
class StorageUnit(object):
    """Structure for Brick/Storage unit"""
    def __init__(self):
        self.kube_host = None
        self.podname = None
        self.path = None
        self.device = None
        self.pvc = None

class Storage(object):
    """Structure for Storage"""
    def __init__(self):
        self.storage_name = None
        self.storage_id = None
        self.storage_type = None
        self.total_size_bytes = 0
        self.used_size_bytes = 0
        self.pv_count = 0
        self.avg_pv_size = 0
        self.min_pv_size = 0
        self.max_pv_size = 0
        self.storage_units = []


def list_storages(cmd_out, _args):
    """Parse list of Storages from JSON input"""
    storages_json = json.loads(cmd_out)

    storages = []
    for key, value in storages_json["data"].items():
        if key.endswith(".info"):
            storage_raw = json.loads(value)
            storage = Storage()
            storage.storage_name = storage_raw["volname"]
            storage.storage_id = storage_raw["volume_id"]
            storage.storage_type = storage_raw["type"]

            for brick in storage_raw.get("bricks", []):
                storage_unit = StorageUnit()
                storage_unit.kube_host = brick["kube_hostname"]
                storage_unit.path = brick["host_brick_path"]
                storage_unit.device = brick["brick_device"]
                storage_unit.pvc = brick["pvc_name"]
                storage_unit.podname = brick["node"].replace(
                    "." + storage.storage_name, "")
                storage.storage_units.append(storage_unit)

            storages.append(storage)

    return storages


def execute(cmd):
    """ execute the CLI command """

    with subprocess.Popen(cmd,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          universal_newlines=True) as proc:
        out, err = proc.communicate()
        if proc.returncode == 0:
            return CmdResponse(proc.returncode, out, err)

        raise CommandError(proc.returncode, err)


def add_global_flags(parser):
    """Global Flags available with every subcommand"""
    parser.add_argument("--kubectl-cmd", default=KUBECTL_CMD,
                        help="Kubectl Command Path")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip execution only preview")
    parser.add_argument("--script-mode", action="store_true",
                        help="Script mode, bypass Prompts")
    parser.add_argument("--kubectl-context", default=None,
                        help="Kubectl Context")


def command_error(cmd, msg):
    """Print error message and Exit"""
    print("Error while running the following command", file=sys.stderr)
    print("$ " + " ".join(cmd), file=sys.stderr)
    print("", file=sys.stderr)
    print(msg, file=sys.stderr)
    sys.exit(1)


def kubectl_cmd_help(cmd):
    """Print error and exit if kubectl not found"""
    print("Failed to execute the command: \"%s\"" % cmd, file=sys.stderr)
    print("Use `--kubectl-cmd` option if kubectl is installed "
          "in custom path", file=sys.stderr)
    sys.exit(1)


def kubectl_cmd(args):
    """k3s embeds kubectl into the k3s binary itself and
    provides kubectl as subcommand. For example `k3s kubectl`.
    Split the given command to support these types.
    """
    cmd_args = args.kubectl_cmd.split()
    if args.kubectl_context is not None:
        cmd_args += ["--context", args.kubectl_context]
    return cmd_args
