#!/bin/bash

MOUNT_DIR=/mnt

if [ $# -eq 1 ]; then
    dir=$1
    /opt/libexec/glusterfs/glfsheal $dir info-summary volfile-path /kadalu/volfiles/$dir.client.vol
    return 0;
elif [ $# -gt 1]; then
    echo "Expects zero of one options"
    return 1;
fi


dirs=$(/bin/ls -d $MOUNT_DIR/* 2>/dev/null| wc -l);
if [ $dirs -lt 1 ] ; then
    echo "No storage pool added to kadalu yet!"
fi

# Host Volume is in the form /mnt/$host-volname
for dir in $(ls $MOUNT_DIR/* -d); do
    #    /opt/libexec/glusterfs/glfsheal <VOLNAME> [bigger-file <FILE> | latest-mtime <FILE> | source-brick <HOSTNAME:BRICKNAME> [<FILE>] | split-brain-info | info-summary] [glusterd-sock <FILE> | volfile-path <FILE>]
    echo "Giving heal information of volume $dir"
    /opt/libexec/glusterfs/glfsheal $dir info-summary volfile-path /kadalu/volfiles/$dir.client.vol
done
