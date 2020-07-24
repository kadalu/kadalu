"""
'storage-list' subcommand for kubectl-kadalu CLI tool
"""
from __future__ import print_function
import json
import sys

import utils


# noqa # pylint: disable=too-few-public-methods
class StorageUnit:
    """Structure for Brick/Storage unit"""
    def __init__(self):
        self.kube_host = None
        self.podname = None
        self.path = None
        self.device = None
        self.pvc = None


# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=too-many-instance-attributes
class Storage:
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


def set_args(name, subparsers):
    """ add arguments to argparser """
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg("--name", metavar="NAME",
        help="Specify Storage name to get info")
    arg("--detail", action="store_true",
        help=("Show detailed information "
              "including Storage units"))
    arg("--status", action="store_true",
        help=("Show status information like number "
              "of PVs, Utilization etc"))
    utils.add_global_flags(parser)


def validate(_args):
    """No validation available"""
    return


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

            for brick in storage_raw["bricks"]:
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


def human_readable_size(size):
    """Show size information human readable"""
    symbols = ["Ei", "Ti", "Gi", "Mi", "Ki"]
    symbol_values = {
        "Ei": 1125899906842624,
        "Ti": 1099511627776,
        "Gi": 1073741824,
        "Mi": 1048576,
        "Ki": 1024
    }
    if size < 1024:
        return "%d" % int(size)

    for ele in symbols:
        if size >= symbol_values[ele]:
            return "%d %s" % (int(size / symbol_values[ele]), ele)

    return "%d" % int(size)


def detailed_output(storages, args):
    """Print the detailed output"""
    for storage in storages:
        if args.name is not None and args.name != storage.storage_name:
            continue

        print("---")
        print("Name: %s" % storage.storage_name)
        print("ID  : %s" % storage.storage_id)
        print("Type: %s" % storage.storage_type)
        if args.status:
            used_percent = 0
            if storage.total_size_bytes > 0:
                used_percent = int(
                    storage.used_size_bytes*100/storage.total_size_bytes
                )
            print("Number of PVs     : %d" % storage.pv_count)
            print("Utilization: %s/%s (%d%%)" % (
                human_readable_size(storage.used_size_bytes),
                human_readable_size(storage.total_size_bytes),
                used_percent
            ))
            print("Min PV Size: %s" % human_readable_size(storage.min_pv_size))
            print("Avg PV Size: %s" % human_readable_size(storage.avg_pv_size))
            print("Max PV Size: %s" % human_readable_size(storage.max_pv_size))

        for idx, storage_unit in enumerate(storage.storage_units):
            print("Storage Unit %d:" % (idx + 1))
            print("  Kube hostname: %s" % storage_unit.kube_host)
            if storage_unit.device != "":
                print("  Device: %s" % storage_unit.device)
            if storage_unit.path != "":
                print("  Path: %s" % storage_unit.path)
            if storage_unit.pvc != "":
                print("  PVC: %s" % storage_unit.pvc)

            print()


def summary_output(storages, args):
    """Print the Summary"""
    if len(storages) > 0:
        print()
        if args.status:
            print("%-15s  %-10s  %-20s  %10s  %15s  %15s  %15s" % (
                "Name", "Type", "Utilization", "Pvs Count",
                "Min PV Size", "Avg PV Size", "Max PV Size"
            ))
        else:
            print("%-15s  %-10s" % ("Name", "Type"))

    for storage in storages:
        if args.name is not None and args.name == storage.storage_name:
            continue

        row = "%-15s  " % storage.storage_name
        row += "%-10s  " % storage.storage_type
        if args.status:
            used_percent = 0
            if storage.total_size_bytes > 0:
                used_percent = int(
                    storage.used_size_bytes*100/storage.total_size_bytes
                )
            utilization = ("%s/%s (%d%%)" % (
                human_readable_size(storage.used_size_bytes),
                human_readable_size(storage.total_size_bytes),
                used_percent
            ))
            row += "%-20s  " % utilization
            row += "%10d  " % storage.pv_count
            row += "%15s  " % human_readable_size(storage.min_pv_size)
            row += "%15s  " % human_readable_size(storage.avg_pv_size)
            row += "%15s  " % human_readable_size(storage.max_pv_size)

        print(row)


def fetch_status(storages, args):
    """Updates the Status details to input Object"""
    for storage in storages:
        if args.name is not None and args.name != storage.storage_name:
            continue

        dbpath = "/bricks/" + storage.storage_name + "/data/brick/stat.db"
        query = ("select size from summary;"
                 "select count(pvname), sum(size), min(size), "
                 "avg(size), max(size) from pv_stats")

        cmd = [
            args.kubectl_cmd, "exec", "-it",
            storage.storage_units[0].podname,
            "-c", "glusterfsd", "-nkadalu", "sqlite3",
            dbpath,
            query
        ]

        try:
            resp = utils.execute(cmd)
            parts = resp.stdout.strip().split("\n")
            storage.total_size_bytes = float(parts[0].strip())
            # num_pvs|used_size|min_pv_size|avg_pv_size|max_pv_size
            pv_stats_parts = parts[1].strip().split("|")
            storage.pv_count = int(pv_stats_parts[0])
            storage.used_size_bytes = float(pv_stats_parts[1])
            storage.min_pv_size = float(pv_stats_parts[2])
            storage.avg_pv_size = float(pv_stats_parts[3])
            storage.max_pv_size = float(pv_stats_parts[4])
        except utils.CommandError as err:
            print("Failed to get size details of the "
                  "storage \"%s\"" % storage.storage_name,
                  file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)

    return True


def run(args):
    """Shows List of Storages"""
    cmd = [args.kubectl_cmd, "get", "configmap",
           "kadalu-info", "-nkadalu", "-ojson"]

    try:
        resp = utils.execute(cmd)
        storages = list_storages(resp.stdout, args)
        if args.status:
            if not fetch_status(storages, args):
                sys.exit(1)

        if args.detail:
            detailed_output(storages, args)
        else:
            summary_output(storages, args)
    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
