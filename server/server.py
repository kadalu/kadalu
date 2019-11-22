#!/usr/bin/python3

"""
Prepares, Validates and then starts the Server process(glusterfsd, shd)
"""

import os

from kadalulib import logging_setup


def start_server_process():
    """
    Start glusterfsd or glustershd process
    """
    server_role = os.environ.get("KADALU_SERVER_ROLE", "glusterfsd")
    if server_role == "glusterfsd":
        import glusterfsd

        glusterfsd.start()
    elif server_role == "shd":
        import shd

        shd.start()
    elif server_role == "quotad":
        import quotad

        quotad.start()


if __name__ == "__main__":
    logging_setup()
    start_server_process()
