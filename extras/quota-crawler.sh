#!/bin/bash

MOUNT_DIR=/mnt

echo "Starting the quota crawler script"
while true; do

    if [ ! -d $MOUNT_DIR/*/subdir ] ; then
	echo "No PVC yet, continuing to watch..."
	sleep 30;
	continue;
    fi

    # Subdir is in the form /mnt/$host-volname/subdir/NN/MM/PVCNAME
    for dir in $(find $MOUNT_DIR/*/subvol/*/* -maxdepth 1 -mindepth 1 -type d); do
	used_size=$(df -B1 ${dir}  | tail -n1 | awk '{print $3}');
	echo "$dir : $used_size"
	setfattr -n glusterfs.quota.total-usage -v ${used_size} $dir;
    done

    sleep 10;
done

echo "Exiting the quota crawler script"
