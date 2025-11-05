"""
'storage-remove' sub command
"""

# noqa # pylint: disable=duplicate-code
# noqa # pylint: disable=too-many-branches

#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function
from string import Template

import os
import tempfile
import sys
import json

import utils

YAML_TEMPLATE = """apiVersion: "kadalu-operator.storage/v1alpha1"
kind: "KadaluStorage"
metadata:
  name: "${name}"
"""


def set_args(name, subparsers):
    """ add arguments, and their options """

    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg(
        "name",
        help="Storage Name"
    )
    utils.add_global_flags(parser)


def validate(args):
    """
    Validate the storage requested to be deleted
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

    cmd = utils.kubectl_cmd(args) + [
        "get", "configmap", "kadalu-info", f"-n{args.namespace}", "-ojson"]

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


def storage_add_data(args):
    """ Build the config file """

    content = {
        "apiVersion": "kadalu-operator.storage/v1alpha1",
        "kind": "KadaluStorage",
        "metadata": {
            "name": args.name
        }
    }

    return content


def run(args):
    """ Adds the subcommand arguments back to main CLI tool """

    yaml_content = Template(YAML_TEMPLATE).substitute(name=args.name)

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

        cmd = utils.kubectl_cmd(args) + ["delete", "-f", tempfile_path]
        resp = utils.execute(cmd)
        print("Storage delete request sent successfully.\n")
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
