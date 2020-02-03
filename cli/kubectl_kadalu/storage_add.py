"""
'storage-add ' sub command
"""

import os
import tempfile
import sys
import yaml

from kubectl_kadalu import utils


# noqa # pylint: disable=too-many-branches
def storage_add_args(subparsers):
    """ add arguments, and their options """
    parser_add_storage = subparsers.add_parser('storage-add')
    parser_add_storage.add_argument(
        "name",
        help="Storage Name"
    )
    parser_add_storage.add_argument(
        "--type",
        help="Storage Type",
        choices=["Replica1", "Replica3", "External", "Replica2"],
        default=None
    )
    parser_add_storage.add_argument(
        "--device",
        help=("Storage device in <node>:<device> format, "
              "Example: --device kube1.example.com:/dev/vdc"),
        default=[],
        action="append"
    )
    parser_add_storage.add_argument(
        "--path",
        help=("Storage path in <node>:<path> format, "
              "Example: --path kube1.example.com:/exports/data"),
        default=[],
        action="append"
    )
    parser_add_storage.add_argument(
        "--pvc",
        help="Storage from pvc, Example: --pvc local-pvc-1",
        default=[],
        action="append"
    )
    parser_add_storage.add_argument(
        "--external",
        help="Storage from external gluster, Example: --external gluster-node:/gluster-volname",
        default=""
    )
    parser_add_storage.add_argument(
        "--tiebreaker",
        help="If type is 'Replica2', one can have a tiebreaker node along "
        "with it. like '--tiebreaker tie-breaker-node-name:/data/tiebreaker'",
        default=None
    )


def storage_add_validation(args):
    """ validate arguments """
    for vol in args.external:
        if args.type and args.type != "External":
            print("'--external' option is used only with '--type External'",
                  file=sys.stderr)
            sys.exit(1)

        if ":" not in vol:
            print("Invalid external storage details. Please specify "
                  "details in the format <node>:/<volname>", file=sys.stderr)
            sys.exit(1)
        # Set type to External as '--external' option is provided
        args.type = "External"

    if args.tiebreaker:
        if args.type != "Replica2":
            print("'--tiebreaker' option should be used only with "
                  "type 'Replica2'", file=sys.stderr)
            sys.exit(1)
        if ":" not in args.tiebreaker:
            print("Invalid tiebreaker details. Please specify details "
                  "in the format <node>:/<path>", file=sys.stderr)
            sys.exit(1)
    else:
        args.tiebreaker = "tie-breaker.kadalu.io:/mnt"

    if not args.type:
        args.type = "Replica1"

    num_storages = len(args.device) or len(args.path) or len(args.pvc) or len(args.external)
    if num_storages == 0:
        print("Please specify atleast one storage", file=sys.stderr)
        sys.exit(1)

    storage_mismatch = False
    if (args.type == "Replica1" and num_storages != 1) or (
            args.type == "Replica3" and num_storages != 3
    ):
        storage_mismatch = True

    if (args.type == "External" and num_storages != 1) or (
            args.type == "Replica2" and num_storages != 2
    ):
        storage_mismatch = True

    if storage_mismatch:
        print("Number of storages not matching for type=%s" % args.type,
              file=sys.stderr)
        sys.exit(1)

    for dev in args.device:
        if ":" not in dev:
            print("Invalid storage device details. Please specify device "
                  "details in the format <node>:<device>", file=sys.stderr)
            sys.exit(1)

    for path in args.path:
        if ":" not in path:
            print("Invalid storage path details. Please specify path "
                  "details in the format <node>:<path>", file=sys.stderr)
            sys.exit(1)


def storage_add_data(args):
    """ Build the config file """
    content = {
        "apiVersion": "kadalu-operator.storage/v1alpha1",
        "kind": "KadaluStorage",
        "metadata": {
            "name": args.name
        },
        "spec": {
            "type": args.type,
            "storage": []
        }
    }

    # External details are specified, no 'storage' section required
    if args.external:
        for voldata in args.external:
            node, vol = voldata.split(":")
            content["spec"]["storage"].append(
                {
                    "gluster_host": node,
                    "gluster_volname": vol.strip("/")
                }
            )
        return content

    # Everything below can be provided for a 'Replica3' setup.
    # Or two types of data can be provided for 'Replica2'.
    # So, return only at the end.

    # Device details are specified
    if args.device:
        for devdata in args.device:
            node, dev = devdata.split(":")
            content["spec"]["storage"].append(
                {
                    "node": node,
                    "device": dev
                }
            )

    # If Path is spacified
    if args.path:
        for pathdata in args.path:
            node, path = pathdata.split(":")
            content["spec"]["storage"].append(
                {
                    "node": node,
                    "path": path
                }
            )

    # If PVC is specified
    if args.pvc:
        for pvc in args.pvc:
            content["spec"]["storage"].append(
                {
                    "pvc": pvc
                }
            )

    if args.tiebreaker:
        for tb_data in args.tiebreaker:
            node, path = tb_data.split(":")
            content["spec"]["tiebreaker"] = {
                "node": node,
                "path": path
            }

    return content


def subcmd_storage_add(args):
    """ Adds the subcommand arguments back to main CLI tool """
    data = storage_add_data(args)

    config, tempfile_path = tempfile.mkstemp(prefix="kadalu")
    try:
        with os.fdopen(config, 'w') as tmp:
            yaml.dump(data, tmp)

        cmd = [utils.KUBECTL_CMD, "create", "-f", tempfile_path]
        resp = utils.execute(cmd)
        print("Storage add request sent successfully")
        print(resp.stdout)
        print()
        print("Storage Yaml file for your reference:")
        print(yaml.dump(data))
        print()
    except utils.CommandError as err:
        print("Error while running the following command", file=sys.stderr)
        print("$ " + " ".join(cmd), file=sys.stderr)
        print("", file=sys.stderr)
        print(err.stderr, file=sys.stderr)
        sys.exit(1)
    finally:
        os.remove(tempfile_path)
