"""
'logs' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import utils

# TODO: provide 'hint' based on grepping error logs. That way, users get to
#       check for few common errors easily

def set_args(name, subparsers):
    """ add arguments to argparser """
    # TODO: in future allow users to pass optional pod names
    # TODO: make 'all-containers' optional based on container name (along with pod name).
    # TODO: provide options to pass options to kubectl logs (like tail, container name etc)
    parser = subparsers.add_parser(name)
    utils.add_global_flags(parser)


def validate(_args):
    """No validation available"""
    return


def run(args):
    """ perform log subcommand """

    try:
        cmd = utils.kubectl_cmd(args) + ["get", "pods", "-nkadalu", "-oname"]
        resp = utils.execute(cmd)
        pods = resp.stdout.split('\n')

        for pod in pods:
            if pod == "":
                continue
            log_cmd = utils.kubectl_cmd(args) + ["logs", "-nkadalu", pod, "--all-containers=true"]
            log_resp = utils.execute(log_cmd)
            print("----- (Kadalu Namespace) %s -----" % pod)
            print(log_resp.stdout)
            print()

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
