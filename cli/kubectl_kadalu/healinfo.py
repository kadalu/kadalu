"""
'healcheck' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import utils

# TODO: provide 'hint' based on grepping error logs. That way, users get to
#       check for few common errors easily

def set_args(_name, _subparsers):
    """ add arguments to argparser """
    # TODO: allow check of specific storage pool
    return


def validate(_args):
    """No validation available"""
    return


def run(args):
    """ perform log subcommand """

    try:
        cmd = utils.kubectl_cmd(args) + ["exec",
                                         "-nkadalu",
                                         "csi-provisioner-0",
                                         "-c",
                                         "kadalu-csi-provisioner",
                                         "--", "/kadalu/heal-info.sh"]
        resp = utils.execute(cmd)
        print(resp.stdout)
        print()

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
