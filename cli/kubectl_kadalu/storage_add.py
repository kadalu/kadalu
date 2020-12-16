"""
'storage-add ' sub command
"""

# noqa # pylint: disable=duplicate-code
# noqa # pylint: disable=too-many-branches

#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import os
import tempfile
import sys
import json

import utils
from storage_yaml import to_storage_yaml


def set_args(name, subparsers):
    """ add arguments, and their options """
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg(
        "name",
        help="Storage Name"
    )
    arg(
        "--type",
        help="Storage Type",
        choices=["Replica1", "Replica3", "External", "Replica2"],
        default=None
    )
    arg(
        "--device",
        help=("Storage device in <node>:<device> format, "
              "Example: --device kube1.example.com:/dev/vdc"),
        default=[],
        action="append"
    )
    arg(
        "--path",
        help=("Storage path in <node>:<path> format, "
              "Example: --path kube1.example.com:/exports/data"),
        default=[],
        action="append"
    )
    arg(
        "--pvc",
        help="Storage from pvc, Example: --pvc local-pvc-1",
        default=[],
        action="append"
    )
    arg(
        "--external",
        help="Storage from external gluster, Example: --external gluster-node:/gluster-volname",
        default=None
    )
    arg(
        "--tiebreaker",
        help="If type is 'Replica2', one can have a tiebreaker node along "
        "with it. like '--tiebreaker tie-breaker-node-name:/data/tiebreaker'",
        default=None
    )
    utils.add_global_flags(parser)


def validate(args):
    """ validate arguments """
    if args.external is not None:
        if args.type and args.type != "External":
            print("'--external' option is used only with '--type External'",
                  file=sys.stderr)
            sys.exit(1)

        if ":" not in args.external:
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

    num_storages = (len(args.device) + len(args.path) + len(args.pvc)) or \
                   (1 if args.external is not None else 0)

    if num_storages == 0:
        print("Please specify at least one storage", file=sys.stderr)
        sys.exit(1)

    # pylint: disable=too-many-boolean-expressions
    if ((args.type == "Replica1" and num_storages != 1) or
            (args.type == "Replica2" and num_storages != 2) or
            (args.type == "Replica3" and num_storages != 3)):
        print("Number of storages not matching for type=%s" % args.type,
              file=sys.stderr)
        sys.exit(1)

    kube_nodes = get_kube_nodes(args)

    for dev in args.device:
        if ":" not in dev:
            print("Invalid storage device details. Please specify device "
                  "details in the format <node>:<device>", file=sys.stderr)
            sys.exit(1)
        if (not args.dry_run) and (dev.split(":")[0] not in kube_nodes):
            print("Node name does not appear to be valid: " + dev)
            sys.exit(1)

    for path in args.path:
        if ":" not in path:
            print("Invalid storage path details. Please specify path "
                  "details in the format <node>:<path>", file=sys.stderr)
            sys.exit(1)

        if (not args.dry_run) and (path.split(":")[0] not in kube_nodes):
            print("Node name does not appear to be valid: " + path)
            sys.exit(1)


def get_kube_nodes(args):
    """ gets all nodes  """
    if args.dry_run:
        return []

    cmd = utils.kubectl_cmd(args) + ["get", "nodes", "-ojson"]
    try:
        resp = utils.execute(cmd)
        data = json.loads(resp.stdout)
        nodes = []
        for nodedata in data["items"]:
            nodes.append(nodedata["metadata"]["name"])

        print("The following nodes are available:\n  %s" % ", ".join(nodes))
        print()
        return nodes
    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)


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
        node, vol = args.external.split(":")
        content["spec"]["details"] = [
            {
                "gluster_host": node,
                "gluster_volname": vol.strip("/")
            }
        ]
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

    # If Path is specified
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

    # TODO: Support for different port can be added later
    if args.type == "Replica2":
        node, path = args.tiebreaker.split(":")
        content["spec"]["tiebreaker"] = {
            "node": node,
            "path": path,
            "port": 24007
        }

    return content


def run(args):
    """ Adds the subcommand arguments back to main CLI tool """
    data = storage_add_data(args)

    yaml_content = to_storage_yaml(data)
    print("Storage Yaml file for your reference:\n")
    print(yaml_content)

    if args.dry_run:
        return

    if not args.script_mode:
        answer = ""
        valid_answers = ["yes", "no", "n", "y"]
        while answer not in valid_answers:
            answer = input("Is this correct?(Yes/No): ")
            answer = answer.strip().lower()

        if answer in ["n", "no"]:
            return

    config, tempfile_path = tempfile.mkstemp(prefix="kadalu")
    try:
        with os.fdopen(config, 'w') as tmp:
            tmp.write(yaml_content)

        cmd = utils.kubectl_cmd(args) + ["apply", "-f", tempfile_path]
        resp = utils.execute(cmd)
        print("Storage add request sent successfully")
        print(resp.stdout)
        print()
    except utils.CommandError as err:
        os.remove(tempfile_path)
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        os.remove(tempfile_path)
        utils.kubectl_cmd_help(args.kubectl_cmd)
    finally:
        if os.path.exists(tempfile_path):
            os.remove(tempfile_path)
