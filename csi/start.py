import os
import logging

from kadalulib import logging_setup, SupervisordConf


def main():
    conf = SupervisordConf()
    conf.add_program("csi-server", "python3 /kadalu/main.py")
    conf.add_program("metrics-server", "python3 /kadalu/exporter.py")
    conf.add_program("volumewatch", "bash /kadalu/watch-vol-changes.sh")
    conf.add_program("logrotate", "bash /kadalu/watch-logrotate.sh")

    if os.environ.get("CSI_ROLE", "-") == "provisioner":
        conf.add_program("quota", "bash /kadalu/quota-crawler.sh")

    conf.save()
    logging.info(conf.content)
    os.execv("/usr/bin/supervisord", ["/usr/bin/supervisord", "-c", conf.conf_file])


if __name__ == "__main__":
    logging_setup()
    main()
