"""
'storage-list' subcommand for kubectl-kadalu CLI tool
"""
from __future__ import print_function
import sys
import json
import shutil
import utils
import os

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
    print("hello1 ", cmd)

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


    cmd = utils.kubectl_cmd(args) + [
         "exec", "kadalu-csi-provisioner-0", "-c", "kadalu-provisioner", "-nkadalu", "--", "bash",
         "-c", "ls -R /mnt/%s | grep '^pvc.*\.json'" %(args.name)
    ]

    print("hello", cmd)

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


def get_full_pv_path(args, archived_pvs):

    archived_pv_full_path = {}
    for archived_pv in archived_pvs:


        cmd = utils.kubectl_cmd(args) + [
            "exec", "kadalu-csi-provisioner-0", "-c", "kadalu-provisioner", "-nkadalu", "--", "bash",
            "-c", "ls -R /mnt/%s | grep '^\/mnt.*%s'" % (args.name, archived_pv.rstrip(".json"))
        ]
        print(archived_pv)
        print(cmd)

        try:
            resp = utils.execute(cmd)
            print(resp.stdout)
            archived_pv_full_path[archived_pv] = str(resp.stdout.strip().split("\n")[0]).rstrip(":")
            print("123", archived_pv_full_path)
            return archived_pv_full_path

        except utils.CommandError as err:
            print("Failed to get archived_pv full path of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
            return None

        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)
            return None


def update_pvstats(args, archived_pvs):

    dbpath = "/mnt/" + args.name + "/stat.db"

    for archived_pv in archived_pvs:

        query = ("DELETE from pv_stats WHERE pvname = '%s'" % archived_pv.rstrip(".json"))

        cmd = utils.kubectl_cmd(args) + [
            "exec", "-it",
            "kadalu-csi-provisioner-0",
            "-c", "kadalu-provisioner",
            "-nkadalu", "--", "sqlite3",
            dbpath,
            query
        ]
        print(cmd)

        try:
            resp = utils.execute(cmd)
            print(resp.stdout)

        except utils.CommandError as err:
            print("Failed to update pv_stats of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)


def delete_archived_pv(args, archived_pv_full_path):


    # archived_pv_full_path = {}
    # archived_pv_full_path["pvc"] = "/mnt/storage-pool-1/subvol/8c/b7/pvc-be602914-06bb-4775-900e-856b6f986468"
    # print(archived_pv_full_path.keys())
    for full_pvc_path in archived_pv_full_path.values():

        path_prefix = full_pvc_path.replace("/mnt/%s/" % args.name, "")

        # Remove archived info file dir
        cmd = utils.kubectl_cmd(args) + [
            "exec", "-it",
            "kadalu-csi-provisioner-0",
            "-c", "kadalu-provisioner",
            "-nkadalu", "--", "python",
            "-c",
            "import shutil; shutil.rmtree('/mnt/%s/info/%s')" %(args.name, os.path.dirname(path_prefix+".json"))
        ]
        print(cmd)

        try:
            resp = utils.execute(cmd)
            print(resp.stdout)
        except OSError as err:
            print("Failed to delete archived info file of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except utils.CommandError as err:
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)

        # Remove the archived PVC
        cmd = utils.kubectl_cmd(args) + [
            "exec", "-it",
            "kadalu-csi-provisioner-0",
            "-c", "kadalu-provisioner",
            "-nkadalu", "--", "python",
            "-c",
            "import shutil; shutil.rmtree('%s')" %(os.path.dirname(full_pvc_path))
        ]
        print(cmd)

        try:
            resp = utils.execute(cmd)
            print(resp.stdout)
        except OSError as err:
            print("Failed to delete archived PVC of the "
                    "storage \"%s\"" % args.name,
                    file=sys.stderr)
            print(err, file=sys.stderr)
            print()
        except utils.CommandError as err:
            print(err, file=sys.stderr)
            print()
        except FileNotFoundError:
            utils.kubectl_cmd_help(args.kubectl_cmd)


def run(args):
    """Run Delete Archived PVCs"""

    try:
        print("hello3", args)
        archived_pvs = get_archived_pvname(args)

        if archived_pvs is None:
            print("No archived PVCs found to delete")
            return

        archived_pv_full_path = get_full_pv_path(args, archived_pvs)

        print(archived_pv_full_path)
        update_pvstats(args, archived_pvs)
        delete_archived_pv(args, archived_pv_full_path)

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
