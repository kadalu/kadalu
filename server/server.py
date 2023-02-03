#!/usr/bin/python3

"""
Prepares, Validates and then starts the Server process(glusterfsd, shd)
"""

import os
import logging

import glusterfsd
import shd
from kadalulib import logging_setup, SupervisordConf


def start_server_process():
    """
    Start glusterfsd or glustershd process
    """
    conf = SupervisordConf()
    conf.add_program("metrics", "python3 /kadalu/exporter.py")
    glusterfsd_args = glusterfsd.start_args()
    conf.add_program("glusterfsd", f"/opt/sbin/glusterfsd {' '.join(glusterfsd_args)}")

    # Start Self heal daemon only if Replica/Disperse Volume
    shd_required = os.environ.get("SHD_REQUIRED", "0")
    if shd_required == "1":
        shd_args = shd.start_args()
        conf.add_program("shd", f"/opt/sbin/glusterfs {' '.join(shd_args)}")

    conf.save()
    logging.info(conf.content)
    os.execv("/usr/bin/supervisord", ["/usr/bin/supervisord", "-c", conf.conf_file])


if __name__ == "__main__":
    logging_setup()
    start_server_process()
