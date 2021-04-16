"""
This is an CLI command to handle kadalu executions
"""
# To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import sys
from argparse import ArgumentParser

from version import VERSION

# Subcommands list that are currently supported, if any new subcommand has to
# be implemeted add argument to this list and implement `validate` and `run`
# functions in a separate file
SUPPORTED_ARGS = [
    "install",
    "storage-add",
    "storage-list",
    "storage-remove",
    "logs",
    "healinfo",
]


def get_args():
    """Argument Parser"""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")
    version_set_args("version", subparsers)
    for arg in SUPPORTED_ARGS:
        mod = __import__(arg.replace("-", "_"))
        mod.set_args(arg, subparsers)

    # If no argument is provided display help text and exit
    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    return parser.parse_args()


def show_version():
    """Show version information"""
    print("kubectl-kadalu %s" % VERSION)


def version_set_args(name, parser):
    """Version subcommand"""
    parser.add_parser(name)


def main():
    """Handle Commands"""
    try:
        args = get_args()
        if args.mode == "version":
            show_version()
            sys.exit(0)
        try:
            mod = __import__(args.mode.replace("-", "_"))
            mod.validate(args)
            mod.run(args)
        except ModuleNotFoundError:
            print('Invalid sub-command "%s"' % args.mode, file=sys.stderr)
            sys.exit(1)
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
