import os
import json
import base64
import sys
import logging

from kadalulib import Monitor, Proc, logging_setup, logf
from utils import CommandError
from utils import execute as utils_execute


def restore_kadalu_storage_config_from_configmap():
    filepath = "/var/lib/kadalu/config-snapshots/latest.tar.gz"

    cmd = ["kubectl", "get", "configmap", "kadalu-mgr", "--output=json"]
    try:
        resp = utils_execute(cmd)
    except CommandError as err:
        if "not found" in err:
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

    data = json.loads(resp)
    with open(filepath, "wb") as cm_file:
        cm_file.write(base64.b64decode(data["binaryData"]["latest.tar.gz"]))

    # Extract Archive (Change workdir to /var/lib/kadalu/config-snapshots)
    cmd = ["tar", "xvzf", "latest.tar.gz", "latest"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to extract Kadalu Storage Configurations backup",
            command=cmd,
            error=err
        ))
        sys.exit(1)

    cmd = ["kadalu", "config-snapshot", "restore", "latest"]
    try:
        utils_execute(cmd)
    except CommandError as err:
        logging.error(logf(
            "Failed to restore Kadalu Storage Configurations.",
            command=cmd,
            error=err
        ))
        sys.exit(1)


def main():
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
    logging_setup()
    main()
