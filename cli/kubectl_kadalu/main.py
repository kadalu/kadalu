from argparse import ArgumentParser

from kubectl_kadalu.storage_add import storage_add_args, subcmd_storage_add, \
    storage_add_validation


def get_args():
    parser = ArgumentParser()
    subparsers = parser.add_subparsers(dest="mode")

    storage_add_args(subparsers)

    return parser.parse_args()


def main():
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
