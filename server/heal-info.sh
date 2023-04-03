#!/bin/bash

declare -a arr=("$@")

if [ $# -eq 1 ]; then
    dir=$1
    if [ -f /var/lib/kadalu/volfiles/$dir.vol ]; then
        echo "Giving heal summary of volume: $dir"
        # Storing the output of the info-summary for later evaluation
        result=$(/opt/libexec/glusterfs/glfsheal $dir info-summary volfile-path /var/lib/kadalu/volfiles/$dir.vol )
        echo "$result"
        echo
        # If info-summary has only "0" or "-" our exit code is "1" and we skip checking for heal details/split-brain
        echo "$result" | grep "Total Number of entries" | cut -d ":" -f 2 |  grep -q -vE "0|-"
        if [ "$?" -eq 0 ]; then
            echo "List of files needing a heal on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $dir volfile-path /var/lib/kadalu/volfiles/$dir.vol
            echo
            echo "List of files in splitbrain on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $dir split-brain-info volfile-path /var/lib/kadalu/volfiles/$dir.vol
        fi
        echo;
        exit 0
    else
        echo "storage pool not available"
        exit 1;
    fi
fi

if [ $# -gt 1 ]; then
    echo "Expects atmost one option"
    exit 1;
fi

dirs=$(/bin/ls -d /var/lib/gluster/*.info 2>/dev/null| wc -l);
if [ $dirs -lt 1 ] ; then
    echo "No storage pool added to kadalu yet!"
    exit 1;
fi

# Host Volume is in the form /mnt/$host-volname
for storage_pool in $(cd /var/lib/gluster/; ls *.info); do
    #/opt/libexec/glusterfs/glfsheal <VOLNAME> [bigger-file <FILE> | latest-mtime <FILE> | source-brick <HOSTNAME:BRICKNAME> [<FILE>] | split-brain-info | info-summary] [glusterd-sock <FILE> | volfile-path <FILE>]
    vol=${storage_pool%.info}
    volfile=$vol.vol
    echo "Giving heal summary of volume ${vol}:"
    # Storing the output of the info-summary for later evaluation
    result=$(/opt/libexec/glusterfs/glfsheal $vol info-summary volfile-path /var/lib/kadalu/volfiles/$volfile )
    echo "$result"
    echo
    # If info-summary has only "0" or "-" our exit code is "1" and we skip checking for heal details/split-brain
    echo "$result" | grep "Total Number of entries" | cut -d ":" -f 2 |  grep -q -vE "0|-"
    if [ "$?" -eq 0 ]; then
            echo "List of files needing a heal on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $vol volfile-path /var/lib/kadalu/volfiles/$volfile
            echo
            echo "List of files in splitbrain on ${vol}:"
            /opt/libexec/glusterfs/glfsheal $vol split-brain-info volfile-path /var/lib/kadalu/volfiles/$volfile
    fi
    echo;echo
done
