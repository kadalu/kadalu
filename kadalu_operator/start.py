import os
from kadalulib import Monitor, Proc, logging_setup


def main():
    curr_dir = os.path.dirname(__file__)

    mon = Monitor()

    mon.add_process(Proc("Storage Manager", "kadalu", ["mgr", "--hostname=kadalu-operator"]))
    mon.add_process(Proc("operator", "python3", [curr_dir + "/main.py"]))
    mon.add_process(Proc("metrics", "python3", [curr_dir + "/exporter.py"]))

    mon.start_all()
    mon.monitor()


if __name__ == "__main__":
    logging_setup()
    main()
