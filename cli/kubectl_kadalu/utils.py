"""
Utility methods for the CLI tool
"""

import subprocess

KUBECTL_CMD = "kubectl"


class CmdResponse: # noqa # pylint: disable=too-few-public-methods
    """ Class for checking the response """
    def __init__(self, rc, out, err):
        self.returncode = rc
        self.stdout = out
        self.stderr = err


class CommandError(Exception):
    """ Class for handling exceptions """
    def __init__(self, rc, err):
        super().__init__("error %d %s" % (rc, err))
        self.returncode = rc
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
