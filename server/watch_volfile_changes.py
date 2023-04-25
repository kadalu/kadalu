import os
import time
import json
import logging
import signal
import serverutils
from kadalulib import (CommandException, execute, logf,
                       logging_setup)
from glusterfsd import (create_brick_volfile, create_client_volfile)
from shd import create_shd_volfile

VOLINFO_DIR = "/var/lib/gluster"
VOLFILES_DIR = "/var/lib/kadalu/volfiles"

brick_device = os.environ.get("BRICK_DEVICE", None)
brick_path = os.environ["BRICK_PATH"]

volume_id = os.environ["VOLUME_ID"]
brick_path_name = brick_path.strip("/").replace("/", "-")
volname = os.environ["VOLUME"]
nodename = os.environ["HOSTNAME"]

volfile_id = "%s.%s.%s" % (volname, nodename, brick_path_name)

storage_unit_volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volfile_id)
client_volfile_path = os.path.join(VOLFILES_DIR, "%s.vol" % volname)
shd_volfile_path = os.path.join(VOLFILES_DIR, "glustershd.vol")

data = {}
info_file_path = os.path.join(VOLINFO_DIR, "%s.info" % volname)

def send_sighup():
    """ Send SIGHUP to Brick & SHD Process notifing change in volfiles """

    try:
        out, _, _ = execute("pgrep", "-f", "-a", "glusterfsd|shd")
        for line in out.split("\n"):
            try:
                pid = line.split(" ", 1)[0]
                os.kill(int(pid), signal.SIGHUP)
            except ProcessLookupError as err:
                logging.error(logf(
                    "Failed to send SIGHUP",
                    line=line,
                    error=err
                ))
    except CommandException as err:
        logging.error(logf(
            "Failed to get pid",
            error=err
        ))


# TODO: Find more efficient ways to watch change on configmap.
# As mtime based watch will not work on Configmap,
# since it is immutable & require pod refresh for mtime to be changed.
def watch_volfile_changes():
    """
    Watch mounted configmap file for changes infinitely every 10 seconds.
    If file is changed, regenerate volfiles & send SIGHUP
    """

    last_content = None

    # Intialize last_content to avoid regenerating volfiles on first pass.
    with open(info_file_path, "r") as info_file:
        last_content = info_file.read()

    while True:
        with open(info_file_path, "r") as info_file:
            content = info_file.read()

            if last_content is not None and content != last_content:
                last_content = content
                logging.info(logf(
                    "Detected change in configmap content. Regenerating volfiles."
                ))

                data = json.loads(content)
                create_brick_volfile(storage_unit_volfile_path, volname, volume_id, brick_path, data)
                create_shd_volfile(shd_volfile_path, volname)
                create_client_volfile(client_volfile_path, data)

                # Send HUP to GlusterFSD & SHD processes
                send_sighup()

        time.sleep(10)


if __name__ == "__main__":

    logging_setup()
    logging.info(logf("Watch established on Configmap."))
    watch_volfile_changes()
