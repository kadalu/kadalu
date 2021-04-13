"""
This is an CLI command to handle kadalu executions
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

from argparse import ArgumentParser

import healinfo
import install
import logs
import storage_add
import storage_list
import storage_remove
from version import VERSION

cmds = {
    "install": install,
    "storage-add": storage_add,
    "storage-list": storage_list,
    "storage-remove": storage_remove,
    "logs": logs,
    "healinfo": healinfo,
}


def get_args():
    """Argument Parser"""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")

    logs.set_args("logs", subparsers)
    healinfo.set_args("healinfo", subparsers)
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
        func = cmds.get(args.mode)
        if func:
            func.validate(args)
            func.run(args)
        elif args.mode == "version":
            show_version()
    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
