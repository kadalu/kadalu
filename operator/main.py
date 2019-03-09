# kubectl-gluster deploy <config> Will deploy the Gluster based on
# inputs from config file

# kubectl-gluster operator Will start watcher and install based on CRD
# changes

from argparse import ArgumentParser, SUPPRESS


def subcmd_deploy(args):
    pass


def subcmd_operator(args):
    pass


def get_args():
    parser = ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="subcmd", metavar='{deploy}')

    # Deploy
    parser_deploy = subparsers.add_parser('deploy')
    parser_deploy.add_argument("config", help="Config File name")

    # Operator
    parser_operator = subparsers.add_parser('operator')

    return parser.parse_args()


def main():
    args = get_args()
    if args.subcmd is not None:
        globals()["subcmd_" + args.subcmd](args)


if __name__ == "__main__":
    main()
