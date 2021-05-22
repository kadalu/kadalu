#!/bin/bash

CONFIG_MAP_INFO_DIR="/var/lib/gluster"

ps aux | grep python

CSI_PROCESS_ID=$(ps aux|grep python | grep main | awk '{ print $2}' | xargs);

echo $CSI_PROCESS_ID;

while true; do
    echo "Starting watch on configmap"
    line=$(inotifywait -e modify ${CONFIG_MAP_INFO_DIR});
    # Send a blanket HUP, so all vols can be checked and relevant glusterfs process can be sent a SIGHUP after volgen
    echo $line
    kill -HUP $CSI_PROESS_ID;
done
