import os
import yaml
import subprocess
import tempfile
import sys


KUBECTL_CMD = "kubectl"


def storage_add_args(subparsers):
    parser_add_storage = subparsers.add_parser('storage-add')
    parser_add_storage.add_argument(
        "name",
        help="Storage Name"
    )
    parser_add_storage.add_argument(
        "--type",
        help="Storage Type",
        choices=["Replica1", "Replica3"],
        default="Replica1"
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


def storage_add_validation(args):
    num_storages = len(args.device) or len(args.path) or len(args.pvc)
    if num_storages == 0:
        print("Please specify atleast one storage", file=sys.stderr)
        sys.exit(1)

    if (args.type == "Replica1" and num_storages != 1) or (
            args.type == "Replica3" and num_storages != 3
    ):
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
        return content

    # Path is spacified instead of Raw device
    if args.path:
        for pathdata in args.path:
            node, path = pathdata.split(":")
            content["spec"]["storage"].append(
                {
                    "node": node,
                    "path": path
                }
            )
        return content

    # If PVC is specified instead of Raw device and Path
    if args.pvc:
        for pvc in args.pvc:
            content["spec"]["storage"].append(
                {
                    "pvc": pvc
                }
            )
        return content


def subcmd_storage_add(args):
    data = storage_add_data(args)

    fd, tempfile_path = tempfile.mkstemp(prefix="kadalu")
    try:
        with os.fdopen(fd, 'w') as tmp:
            yaml.dump(data, tmp)

        cmd = [KUBECTL_CMD, "create", "-f", tempfile_path]
        resp = subprocess.run(cmd, capture_output=True, check=True,
                              universal_newlines=True)
        print("Storage add request sent successfully")
        print(resp.stdout)
        print()
        print("Storage Yaml file for your reference:")
        print(yaml.dump(data))
        print()
    except subprocess.CalledProcessError as err:
        print("Error while running the following command", file=sys.stderr)
        print("$ " + " ".join(cmd), file=sys.stderr)
        print("", file=sys.stderr)
        print(err.stderr, file=sys.stderr)
        sys.exit(1)
    finally:
        os.remove(tempfile_path)
