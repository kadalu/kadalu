#!/bin/bash

CONFIG_MAP_INFO_DIR="/var/lib/gluster"

CSI_PROCESS_ID=$(ps aux|grep python | awk '{ print $2}' | xargs);

while true; do
    line=$(inotifywait -e modify ${CONFIG_MAP_INFO_DIR});
    # Send a blanket HUP, so all vols can be checked and relevant glusterfs process can be sent a SIGHUP after volgen
    kill -HUP $CSI_PROESS_ID;
done
