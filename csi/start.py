import os
import sys

from kadalulib import Monitor, Proc, logging_setup


def main():
    curr_dir = os.path.dirname(__file__)

    mon = Monitor()
    mon.add_process(Proc("csi", "python3", [curr_dir + "/main.py"]))
    mon.add_process(Proc("metrics", "python3", [curr_dir + "/exporter.py"]))
    mon.add_process(Proc("volumewatch", "bash", [curr_dir + "/watch-vol-changes.sh"]))

    if os.environ.get("CSI_ROLE", "-") == "provisioner":
        mon.add_process(Proc("quota", "bash", [curr_dir + "/quota-crawler.sh"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    logging_setup()
    main()
