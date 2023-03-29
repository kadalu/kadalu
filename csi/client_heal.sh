#!/bin/bash

MOUNT_DIR=/mnt

declare -a arr=("$@")

if [ $# -eq 1 ]; then
    vol=$1
    if [ -f /var/lib/gluster/$vol.info ]; then
    echo "Applying full client-side self-heal on volume ${vol} by crawling recursively:"
    find /mnt/$vol/* -type f -follow -print
    exit 0
    fi
    echo "storage pool not available"
    exit 1
fi

if [ $# -gt 1 ]; then
    echo "Expects atmost one option"
    exit 1;
fi

dirs=$(/bin/ls -d $MOUNT_DIR/* 2>/dev/null| wc -l);
if [ $dirs -lt 1 ] ; then
    echo "No storage pool added to kadalu yet!"
    exit 1;
fi

for storage_pool in $(cd /var/lib/gluster/; ls *.info); do
    vol=${storage_pool%.info}
    echo "Applying full client-side self-heal on volume ${vol} by crawling recursively:"
    find /mnt/$vol/* -type f -follow -print
    exit 0
done
