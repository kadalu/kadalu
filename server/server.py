#!/usr/bin/python3

"""
Prepares, Validates and then starts the Server process(glusterfsd, shd)
"""

import os

from kadalulib import logging_setup, Monitor, Proc
import glusterfsd
import shd


def start_server_process():
    """
    Start glusterfsd or glustershd process
    """
    curr_dir = os.path.dirname(__file__)

    mon = Monitor()
    glusterfsd_proc = glusterfsd.start_args()

    mon.add_process(glusterfsd_proc)

    # Start Self heal daemon only if Replica/Disperse Volume
    shd_required = os.environ.get("SHD_REQUIRED", "0")
    if shd_required == "1":
        shd_proc = shd.start_args()
        mon.add_process(shd_proc)

    mon.add_process(Proc("quotad", "python3", [curr_dir + "/quotad.py"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    logging_setup()
    start_server_process()
