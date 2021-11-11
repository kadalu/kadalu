"""
'healcheck' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import utils

# TODO: provide 'hint' based on grepping error logs. That way, users get to
#       check for few common errors easily

def set_args(name, subparsers):
    """ add arguments to argparser """
    # TODO: allow check of specific storage pool
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg("--trigger-full-heal",
        action="store_true",
        help="Trigger full client side self heal on all volumes"
    )

    utils.add_global_flags(parser)


def validate(_args):
    """No validation available"""
    return


def run(args):
    """ perform log subcommand """

    try:
        heal_info_cmd = ["exec",
                        "-nkadalu",
                        "kadalu-csi-provisioner-0",
                        "-c",
                        "kadalu-provisioner",
                        "--", "/kadalu/heal-info.sh"]
        if args.trigger_full_heal:
            heal_info_cmd.append("trigger_full_heal")
        cmd = utils.kubectl_cmd(args) + heal_info_cmd
        resp = utils.execute(cmd)
        print(resp.stdout)
        print()

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
