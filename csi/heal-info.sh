#!/bin/bash

MOUNT_DIR=/mnt

if [ $# -eq 1 ]; then
    dir=$1
    if [ -f /kadalu/volfiles/$dir.client.vol ]; then
	/opt/libexec/glusterfs/glfsheal $dir info-summary volfile-path /kadalu/volfiles/$dir.client.vol
	exit 0;
    fi
    echo "storage pool not available"
    exit 1
fi

if [ $# -gt 1 ]; then
    echo "Expects zero or one options"
    exit 1;
fi


dirs=$(/bin/ls -d $MOUNT_DIR/* 2>/dev/null| wc -l);
if [ $dirs -lt 1 ] ; then
    echo "No storage pool added to kadalu yet!"
    exit 1;
fi

# Host Volume is in the form /mnt/$host-volname
for volfile in $(cd /kadalu/volfiles; ls *); do
    #/opt/libexec/glusterfs/glfsheal <VOLNAME> [bigger-file <FILE> | latest-mtime <FILE> | source-brick <HOSTNAME:BRICKNAME> [<FILE>] | split-brain-info | info-summary] [glusterd-sock <FILE> | volfile-path <FILE>]
    vol=${volfile%.client.vol}
    echo "Giving heal summary of volume ${vol}:"
    # Storing the output of the info-summary for later evaluation
    result=$(/opt/libexec/glusterfs/glfsheal $vol info-summary volfile-path /kadalu/volfiles/$volfile )
    echo "$result"
    echo
    # If info-summary has only "0" or "-" our exit code is "1" and we skip checking for heal details/split-brain
    echo "$result" | grep "Total Number of entries" | cut -d ":" -f 2 |  grep -q -vE "0|-"
    if [ "$?" -eq 0 ]; then
            echo "List of files needing a heal on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $vol volfile-path /kadalu/volfiles/$volfile
            echo
            echo "List of files in splitbrain on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $vol split-brain-info volfile-path /kadalu/volfiles/$volfile
    fi
    echo;echo
done
