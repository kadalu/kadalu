"""
Utility methods for the CLI tool
"""

import subprocess
import sys

KUBECTL_CMD = "kubectl"

# noqa # pylint: disable=useless-object-inheritance
# noqa # pylint: disable=too-few-public-methods
# noqa # pylint: disable=bad-option-value
class CmdResponse(object):
    """ Class for checking the response """
    def __init__(self, returncode, out, err):
        self.returncode = returncode
        self.stdout = out
        self.stderr = err


class CommandError(Exception):
    """ Class for handling exceptions """
    def __init__(self, returncode, err):
        super(CommandError, self).__init__(u"error %d %s" % (returncode, err))
        self.returncode = returncode
        self.stderr = err


def execute(cmd):
    """ execute the CLI command """

    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True
    )
    out, err = proc.communicate()
    if proc.returncode == 0:
        return CmdResponse(proc.returncode, out, err)

    raise CommandError(proc.returncode, err)


def add_global_flags(parser):
    """Global Flags available with every subcommand"""
    parser.add_argument("--kubectl-cmd", default=KUBECTL_CMD,
                        help="Kubectl Command Path")
    parser.add_argument("--verbose", action="store_true",
                        help="Verbose output")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip execution only preview")
    parser.add_argument("--script-mode", action="store_true",
                        help="Script mode, bypass Prompts")


def command_error(cmd, msg):
    """Print error message and Exit"""
    print("Error while running the following command", file=sys.stderr)
    print("$ " + " ".join(cmd), file=sys.stderr)
    print("", file=sys.stderr)
    print(msg, file=sys.stderr)
    sys.exit(1)


def kubectl_cmd_help(cmd):
    """Print error and exit if kubectl not found"""
    print("Failed to execute the command: \"%s\"" % cmd, file=sys.stderr)
    print("Use `--kubectl-cmd` option if kubectl is installed "
          "in custom path", file=sys.stderr)
    sys.exit(1)
