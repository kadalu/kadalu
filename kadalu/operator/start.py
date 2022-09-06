"""
Start Kadalu Operator
"""
import os
import json
import base64
import sys
import logging

from kadalu.common.utils import (
    Monitor, Proc, logging_setup, logf, execute,
    CommandException
)


def restore_kadalu_storage_config_from_configmap():
    """
    Restore Kadalu Storage Configuration from Configmap based backup.
    """
    filepath = "/var/lib/kadalu/config-snapshots/latest.tar.gz"

    cmd = ["kubectl", "get", "configmap", "kadalu-mgr", "--output=json"]
    try:
        resp = execute(*cmd)
    except CommandException as err:
        if "not found" in err.err:
            # No backups found in Configmap so fresh setup.
            return

        logging.error(logf(
            "Failed to read Kadalu Storage Configurations "
            "backup from Configmap",
            command=cmd,
            error=err
        ))
        sys.exit(1)

    os.makedirs(os.path.dirname(filepath), mode = 0o700, exist_ok = True)

    data = json.loads(resp[0])
    with open(filepath, "wb") as cm_file:
        cm_file.write(base64.b64decode(data["binaryData"]["latest.tar.gz"]))

    # Extract Archive (Change workdir to /var/lib/kadalu/config-snapshots)
    cmd = ["tar", "xvzf", "latest.tar.gz", "latest"]
    try:
        execute(*cmd, cwd="/var/lib/kadalu/config-snapshots")
    except CommandException as err:
        logging.error(logf(
            "Failed to extract Kadalu Storage Configurations backup",
            command=cmd,
            error=err
        ))
        sys.exit(1)

    cmd = ["kadalu", "config-snapshot", "restore", "latest"]
    try:
        execute(*cmd)
    except CommandException as err:
        logging.error(logf(
            "Failed to restore Kadalu Storage Configurations.",
            command=cmd,
            error=err
        ))
        sys.exit(1)

    logging.info(logf(
        "Operator restarted and Kadalu Storage configurations "
        "restored from ConfigMap",
        configmap_name="kadalu-mgr"
    ))

# pylint: disable=missing-function-docstring
def main():
    logging_setup()

    curr_dir = os.path.dirname(__file__)

    # Restore if previously created Kadalu Storage
    # config backup is available
    restore_kadalu_storage_config_from_configmap()

    mon = Monitor()

    mon.add_process(Proc("Storage Manager", "kadalu", ["mgr", "--hostname=kadalu-operator"]))
    mon.add_process(Proc("operator", "python3", [curr_dir + "/main.py"]))
    mon.add_process(Proc("metrics", "python3", [curr_dir + "/exporter.py"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    main()
