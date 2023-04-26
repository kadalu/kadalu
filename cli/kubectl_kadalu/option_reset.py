"""
'option-reset' sub command
"""

# noqa # pylint: disable=duplicate-code
# noqa # pylint: disable=too-many-branches

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
    if not args.script_mode:
        answer = ""
        valid_answers = ["yes", "no", "n", "y"]
        while answer not in valid_answers:
            answer = input("Is this correct?(Yes/No): ")
            answer = answer.strip().lower()

        if answer in ["n", "no"]:
            return False

    return True


def run(args):
    """ Adds the subcommand arguments back to main CLI tool """

    data = {}
    updated_options = {}
    existing_options = {}
    options = []

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

    if data["spec"].get("options", []):
        e_options = data["spec"]["options"]
        for option in e_options:
            existing_options.update({
                option.get("key"): option.get("value")
            })

    if existing_options is None:
        print("No options present in Storage Pool to reset.")

    updated_options = existing_options.copy()

    # Remove all options
    if args.all:
        print("All Existing Storage Pool Options below will be cleared")
        for key, value in existing_options.items():
            print("Key: %s :: Value: %s" %(key, value))

        updated_options = updated_options.clear()
        print("updated options after clear()", updated_options)

    # Remove user specified options
    else:
        for option in args.options:
            if option in updated_options:
                del updated_options[option]
        print("Storage Options before updation")
        for key, value in existing_options.items():
            print("Key: %s :: Value: %s" %(key, value))
        print()
        print("Storage Options after updation")
        if not updated_options:
            print("No Storage Options left after updation!")
        else:
            for key, value in updated_options.items():
                print("Key: %s :: Value: %s" %(key, value))

    # Save back into CRD in array of objects format.
    # Which will be processed while deploying configmaps in operator.
    if updated_options:
        for key, value in updated_options.items():
            options.append({"key": key, "value": value})

    data["spec"]["options"] = options

    if args.dry_run:
        return

    if not user_confirmation(args):
        return

    # Create a temporary file named "<pool_name>.json"
    temp_file_path = tempfile.gettempdir() + "/%s.json" % (args.name)
    with open(temp_file_path, mode="w", encoding="utf-8") as temp_file:
        # Write the data to the file in JSON format
        json.dump(data, temp_file)
        print(temp_file_path)

    cmd = utils.kubectl_cmd(args) + [
        "apply", "-f", temp_file_path]

    try:
        resp = utils.execute(cmd)
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
