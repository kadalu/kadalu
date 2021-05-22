#!/bin/bash

# This is a script/process which is expected to run in the csi pod to watch for any
# modifications in ConfigMap dir, and trigger regeneration of client volfiles with
# new configmap values. The script/process is expected to run for the lifetime of
# the pod.

# ConfigMap dir as per csi.yaml pod's template.
CONFIG_MAP_DIR="/var/lib/gluster"

# Currently 'SIGHUP' handling is done only in 'csi/main.py'.
CSI_PROCESS_ID=$(ps aux|grep python | grep main | awk '{ print $2}' | xargs);

echo "Starting watch on configmap"
while true; do
    # Starting inotifywait without `-m` option (ie, `--monitor`), which makes the process
    # exit after first instance of modify on directory.
    line=$(inotifywait -e modify ${CONFIG_MAP_DIR});
    # Send a blanket HUP, so all vols can be checked and relevant glusterfs process can be sent a SIGHUP after volgen
    echo $line
    kill -HUP $CSI_PROESS_ID;
done

echo "Exiting..."
