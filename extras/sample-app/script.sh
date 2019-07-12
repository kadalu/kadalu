#!/bin/bash

echo "This is a sample application"
ret=1

echo "# df -h"
df -h /mnt/pv || echo "FAILURE"

echo "# mount"
mount | grep /mnt/pv

echo "Write/Read test on PV mount"
date > /mnt/pv/timestamp || echo "Write FAILURE"

cat /mnt/pv/timestamp  || echo "Read FAILURE"

rm /mnt/pv/timestamp; ret=$?

if [ "x$ret" = "x0" ]; then
    echo "SUCCESS"
    exit 0
else
    echo "FAILURE"
    exit 1
fi
