"""
'option-reset' sub command
"""

#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import json
import os
import sys
import tempfile
import argparse
import utils


def set_args(name, subparsers):
    """ add arguments, and their options """
    # TODO: Sub group arguments to relax validation manually
    # https://docs.python.org/3/library/argparse.html#argument-groups
    parser = subparsers.add_parser(name, formatter_class=argparse.RawTextHelpFormatter)
    arg = parser.add_argument

    arg("name", help="Storage Name")
    arg("options",
        help=('Reset or Remove Storage pool options in "<xlator>" format.\n'
              'Example: option-reset <POOL NAME> performance.write-behind\n'
              'Example: option-reset <POOL NAME> performance.quick-read '
              'performance.open-behind on'),
        nargs="*",
        action="store")
    arg("--all",
        help=('Reset or Remove all Storage pool options.\n'),
        action="store_true", default=False)

    utils.add_global_flags(parser)


# pylint: disable=too-many-statements
def validate(args):
    """ validate arguments """

    # Error out when options is not specified and --all flag is not set
    if not args.options and not args.all:
        print(
            "Invalid storage pool option-reset details. Please specify options "
            'details in the format "<xlator>" or "<xlator1> <xlator2> <xlator3> ..."',
            file=sys.stderr)
        sys.exit(1)

    # Error out when both options and --all used in conjunction.
    if args.all and args.options:
        print(
            "Invalid storage pool option-reset details. Please either specify options "
            'to be removed or use --all to remove all existing options',
            file=sys.stderr)
        sys.exit(1)


def user_confirmation(args):
    """ Prompt user for confirmation of changes """
    if not args.script_mode and args.all:
        answer = ""
        valid_answers = ["yes", "no", "n", "y"]
        while answer not in valid_answers:
            answer = input("Do you want to proceed removing all configured options?\n")
            answer = answer.strip().lower()

        if answer in ["n", "no"]:
            return False

    return True


def run(args):
    """ Adds the subcommand arguments back to main CLI tool """

    data = {}

    cmd = utils.kubectl_cmd(args) + [
        "get", "kadalustorages.kadalu-operator.storage",
        args.name, "-ojson"]

    try:
        resp = utils.execute(cmd)
        data = json.loads(resp.stdout)
    except utils.CommandError as err:
        print("Failed to get CRD of "
              "storage \"%s\"" % args.name,
              file=sys.stderr)
        print(err, file=sys.stderr)
        print()
        sys.exit(1)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
        sys.exit(1)

    e_options = data["spec"]["options"]
    data["spec"]["options"] = []
    for option in e_options:
        if option["key"] not in args.options and not args.all:
            data["spec"]["options"].append(option)

    if args.dry_run:
        return

    if not user_confirmation(args):
        return

    # Create a temporary file named "<pool_name>.json"
    temp_file_path = tempfile.gettempdir() + "/%s.json" % (args.name)
    with open(temp_file_path, mode="w", encoding="utf-8") as temp_file:
        # Write the data to the file in JSON format
        json.dump(data, temp_file)

    cmd = utils.kubectl_cmd(args) + [
        "apply", "-f", temp_file_path]

    try:
        resp = utils.execute(cmd)
        print(f"Storage Pool {args.name} storage-options configured.")
    except utils.CommandError as err:
        print("Failed to apply CRD for "
              "storage \"%s\"" % args.name,
              file=sys.stderr)
        print(err, file=sys.stderr)
        print()
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
    finally:
        if os.path.exists(temp_file_path):
            os.remove(temp_file_path)
