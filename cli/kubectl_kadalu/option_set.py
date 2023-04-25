"""
'option-set' sub command
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
        help=('Add or Set Storage pool options in "<xlator> <value>" format.\n'
              'Example: option-set <POOL NAME> performance.write-behind on\n'
              'Example: option-set <POOL NAME> performance.quick-read on performance.open-behind on'),
        nargs="+",
        action="store")
    utils.add_global_flags(parser)


# pylint: disable=too-many-statements
def validate(args):
    """ validate arguments """

    print(len(args.options))

    if len(args.options) < 2 or len(args.options) % 2 != 0:
        print(
            "Invalid storage pool option-set details. Please specify options "
            'details in the format "<xlator> <value>" or "<xlator1> <value1> <xlator2> <value2> ..."',
            file=sys.stderr)
        sys.exit(1)


def run(args):
    """ Adds the subcommand arguments back to main CLI tool """

    data = {}
    updated_options = {}
    existing_options = {}
    given_options = {}
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

    print("from data", data["spec"].get("options", []))

    if data["spec"].get("options", []):
        options = data["spec"]["options"]
        for option in options:
            existing_options.update({
                option.get("key"): option.get("value")
            })

    print("existing_options", existing_options)

    updated_options = existing_options.copy()

    for index in range(0, len(args.options), 2):
        given_options.update({
            args.options[index]: args.options[index + 1]
        })

    print("given_options", given_options)

    updated_options.update(given_options)

    print("updated_options", updated_options)

    # Save back into CRD in array of objects format.
    # Which will be processed while deploying configmaps in operator.
    for key,value in updated_options.items():
        options.append({"key": key, "value": value})

    print(options)

    data["spec"]["options"] = options
    print("to data", data)

    print("Storage Options before updation")
    if not existing_options:
        print("Storage Options not yet configured!")
    else:
        for key,value in existing_options.items():
            print("Key: %s :: Value: %s" %(key, value))
    print()
    print("Storage Options after updation")
    for key, value in updated_options.items():
        print("Key: %s :: Value: %s" %(key, value))

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

    # Create a temporary file named "<pool_name>.json"
    temp_file_path = tempfile.gettempdir() + "/%s.json" % (args.name)
    with open(temp_file_path, mode="w") as temp_file:
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
    # finally:
    #     if os.path.exists(temp_file_path):
    #         os.remove(temp_file_path)
