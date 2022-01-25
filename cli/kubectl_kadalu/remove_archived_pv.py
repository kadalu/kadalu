"""
'storage-list' subcommand for kubectl-kadalu CLI tool
"""
from __future__ import print_function
import sys
import json
import shutil
import utils

# noqa # pylint: disable=too-many-instance-attributes
# noqa # pylint: disable=useless-object-inheritance
# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=bad-option-value
def set_args(name, subparsers):
    """ add arguments to argparser """
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg("name", metavar="NAME",
        help="Specify Storage name to delete archived pvc(s)")
    utils.add_global_flags(parser)


def validate(args):
    """
    Validate the storage of archived pvcs requested to be delete
    is present in kadalu configmap or not.
    Exit if not present.
    """

    storage_info_data = get_configmap_data(args)

    if storage_info_data is None:
        print("Aborting.....")
        print("Invalid name. No such storage '%s' in Kadalu configmap." % args.name)
        sys.exit(1)


def get_configmap_data(args):
    """
    Get storage info data from kadalu configmap
    """

    cmd = utils.kubectl_cmd(args) + ["get", "configmap", "kadalu-info", "-nkadalu", "-ojson"]

    try:
        resp = utils.execute(cmd)
        config_data = json.loads(resp.stdout)

        volname = args.name
        data = config_data['data']
        storage_name = "%s.info" % volname
        storage_info_data = data[storage_name]

        # Return data in 'dict' format
        return json.loads(storage_info_data)

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
        return None

    except KeyError:
        # Validate method expects None when 'storage' not found.
        return None


def get_archived_pvname(args):

    cmd = "ls - R /mnt/%s | grep '^pvc_.*\.json'" % args.name

    try:
        resp = utils.execute(cmd)
        print(resp.stdout)
        archived_pvs = resp.stdout.strip().split("\n")
        return archived_pvs

    except utils.CommandError as err:
        print("Failed to get details of archived pvs of the "
                "storage \"%s\"" % args.name,
                file=sys.stderr)
        print(err, file=sys.stderr)
        print()
        return None
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
        return None


def get_full_pv_path(storage_name, archived_pvs):

    archived_pv_full_path = {}
    for archived_pv in archived_pvs:

        cmd = "ls - R /mnt/%s | grep '^\./subvol.*pvc'" % (storaga_pool_name, archived_pv)

        try:
            resp = utils.execute(cmd)
            print(resp.stdout)
            archived_pv_full_path[archived_pv] = resp.stdout.strip().split("\n")

        except utils.CommandError as err:
            print("Failed to get archived_pv full path of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)


def update_pvstats(args, archived_pvs):

    dbpath = "/mnt/" + args.name + "/stat.db"

    for archived_pv in archived_pvs:

        archived_pv.rstrip(".json")

        query = ("DELETE from pv_stats WHERE pvname = '%s'" % archived_pv)

        cmd = utils.kubectl_cmd(args) + [
            "exec", "-it",
            "kadalu-csi-provisioner-0",
            "-c kadalu-provisioner",
            "-nkadalu", "--", "sqlite3",
            dbpath,
            query
        ]

        try:
            resp = utils.execute(cmd)

        except utils.CommandError as err:
            print("Failed to update pv_stats of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)


def delete_archived_pv(args, archived_pv_full_path):

    for key, value in archived_pv_full_path:

        parent_dir = os.path.dir(value.lstrip("./"))
        # Remove info file dir
        try:
            shutil.rmtree("/mnt/%s/info/%s" %(args.name, parent_dir))
        except OSError as err:
            print("Failed to delete archived info file of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()

        # Remove PVC
        try:
            shutil.rmtree("/mnt/%s/%s" %(args.name, parent_dir))
        except OSError as err:
            print("Failed to delete archived PVC of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()


def run(args):
    """Shows List of Storages"""

    try:
        archived_pvs = get_archived_pvname(args)

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
