#!/usr/bin/python3

"""
Prepares, Validates and then starts the Server process(glusterfsd, shd)
"""

import os

from kadalulib import logging_setup
import glusterfsd
import shd
import quotad


def start_server_process():
    """
    Start glusterfsd or glustershd process
    """
    server_role = os.environ.get("KADALU_SERVER_ROLE", "glusterfsd")
    if server_role == "glusterfsd":
        glusterfsd.start()
    elif server_role == "shd":
        shd.start()
    elif server_role == "quotad":
        quotad.start()


if __name__ == "__main__":
    logging_setup()
    start_server_process()
