"""
Utility methods for the CLI tool
"""

import subprocess
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
