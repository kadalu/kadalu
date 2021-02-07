import subprocess
import os
import sys

from kadalulib import Monitor, Proc


def main():
    curr_dir = os.path.dirname(__file__)

    mon = Monitor()
    mon.add_process(Proc("operator", "python3", [curr_dir + "/main.py"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    main()
