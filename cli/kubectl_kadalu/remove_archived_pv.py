"""
'remove-archived-pv' subcommand for kubectl-kadalu CLI tool
"""
from __future__ import print_function
import sys
import json
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
    arg("--pvc", metavar="PVC", default=None,
        help="name of archived pvc belonging to specified storage-pool")
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
        sys.exit()


def get_configmap_data(args):
    """
    Get storage info data from kadalu configmap
    """

    cmd = utils.kubectl_cmd(args) + [
        "get", "configmap", "kadalu-info", f"-n{args.namespace}", "-ojson"
    ]

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


def request_pv_delete(args):
    """ Send PVC delete request to CSI"""

    cmd = utils.kubectl_cmd(args) + [
         "exec", "-it", "kadalu-csi-provisioner-0", 
         "-c", "kadalu-provisioner", 
         f"-n{args.namespace}",
         "--", "bash",
         "-c", "cd /kadalu; python3 remove_archived_pv.py %s" %(args.name)
    ]

    if args.pvc:
        cmd[-1] = cmd[-1] + " --pvc=%s" %(args.pvc)

    try:
        resp = utils.execute(cmd)
        print("Sent request for deletion of archived PVCs")
        return resp

    except utils.CommandError as err:
        print("Failed to request deletion of archived pvc of the "
                "storage \"%s\"" % args.name,
                file=sys.stderr)
        print(err, file=sys.stderr)
        print()
        return None
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
        return None


def run(args):
    """Run Delete Archived PVCs"""

    resp = request_pv_delete(args)
    if resp is not None:
        if resp.stderr:
            print(resp.stderr)
        print(resp.stdout)
