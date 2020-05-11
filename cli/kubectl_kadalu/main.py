"""
This is an CLI command to handle kadalu executions
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

from argparse import ArgumentParser

# noqa # pylint: disable=unused-import
from kubectl_kadalu.storage_add import storage_add_args, subcmd_storage_add, \
     storage_add_validation
from kubectl_kadalu.install import install_args, subcmd_install


def get_args():
    """Argument Parser"""
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")

    storage_add_args(subparsers)

    install_args(subparsers)

    return parser.parse_args()


def main():
    """Handle Commands"""
    try:
        args = get_args()

        func = None
        if args.mode is not None:
            validation_func = globals().get(args.mode.replace("-", "_") + "_validation", None)
            func = globals().get("subcmd_" + args.mode.replace("-", "_"), None)

        if func is not None:
            if validation_func is not None:
                validation_func(args)
            func(args)

    except KeyboardInterrupt:
        return


if __name__ == "__main__":
    main()
