"""
'healcheck' subcommand for kubectl-kadalu CLI tool
"""
#To prevent Py2 to interpreting print(val) as a tuple.
from __future__ import print_function

import sys
import utils

# TODO: provide 'hint' based on grepping error logs. That way, users get to
#       check for few common errors easily

def set_args(name, subparsers):
    """ add arguments to argparser """
    parser = subparsers.add_parser(name)
    arg = parser.add_argument

    arg("--name", metavar="NAME",
        help="Specify Storage name to heak or get healinfo")

    arg("--trigger-full-heal",
        action="store_true",
        help="Trigger full client side self heal")

    utils.add_global_flags(parser)


def validate(_args):
    """No validation available"""
    return


def check_server_pod_is_up(server_pod, args):
    """
    Return True if server pod is up,
    Exit when CommandError is reached,
    Return False if server_pod is down
    """

    cmd = utils.kubectl_cmd(args) + ["get", "pods", f"-n{args.namespace}", server_pod,
                                     "-o", "jsonpath={.status.phase}"]

    try:
        resp = utils.execute(cmd)
        if resp.stdout == "Running":
            return True
    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)

    return False


def exec_server_and_fetch_healinfo(server_pod, args):
    """
    server_pod: First reachable server pod
    Exec into server_pod and call heal-info.sh script
    """

    try:
        heal_info_cmd = ["exec",
                         f"-n{args.namespace}",
                         server_pod,
                         "--", "/kadalu/heal-info.sh"]

        # TODO: Throw error in stdout when storage-pool not exists.
        if args.name is not None:
            heal_info_cmd.append(args.name)

        cmd = utils.kubectl_cmd(args) + heal_info_cmd
        resp = utils.execute(cmd)
        print(resp.stdout)
        print()

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)


def exec_csi_and_heal(args):
    """
    Exec into csi pod and call client_heal.sh which
    crawls into /mnt/pool_name and refreshes heal xattrs
    """

    try:
        client_heal_cmd = ["exec",
                           f"-n{args.namespace}",
                           "kadalu-csi-provisioner-0",
                           "-c",
                           "kadalu-provisioner",
                           "--", "/kadalu/client_heal.sh"]

        if args.name is not None:
            client_heal_cmd.append(args.name)

        cmd = utils.kubectl_cmd(args) + client_heal_cmd
        resp = utils.execute(cmd)
        print(resp.stdout)
        print()
    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)


def run(args):
    """ Call heal-info.sh or client_heal.sh based on args """

    if args.trigger_full_heal:
        exec_csi_and_heal(args)
        sys.exit(0)

    cmd = utils.kubectl_cmd(args) + [
        "get", "configmap", "kadalu-info", f"-n{args.namespace}", "-ojson"]

    try:
        resp = utils.execute(cmd)
        storages = utils.list_storages(resp.stdout, args)

        for storage in storages:
            if args.name is not None and args.name != storage.storage_name:
                continue

            for storage_unit in storage.storage_units:
                if check_server_pod_is_up(storage_unit.podname, args):
                    exec_server_and_fetch_healinfo(storage_unit.podname, args)
                    break

    except utils.CommandError as err:
        utils.command_error(cmd, err.stderr)
    except FileNotFoundError:
        utils.kubectl_cmd_help(args.kubectl_cmd)
