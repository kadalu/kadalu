"""
This is an CLI command to handle kadalu executions
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

from argparse import ArgumentParser

import install
import storage_add
import storage_list
import storage_remove

from version import VERSION


def get_args():
    """Argument Parser"""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")

    install.set_args("install", subparsers)
    storage_add.set_args("storage-add", subparsers)
    storage_list.set_args("storage-list", subparsers)
    storage_remove.set_args("storage-remove", subparsers)
    version_set_args("version", subparsers)

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
        if args.mode == "install":
            install.validate(args)
            install.run(args)
        elif args.mode == "storage-add":
            storage_add.validate(args)
            storage_add.run(args)
        elif args.mode == "storage-list":
            storage_list.validate(args)
            storage_list.run(args)
        elif args.mode == 'storage-remove':
            storage_remove.validate(args)
            storage_remove.run(args)
        elif args.mode == "version":
            show_version()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
