#!/bin/bash

echo "This is a sample application"
ret=1

echo "# df -h"
df -h /mnt/pv || echo "FAILURE"

echo "# mount"
mount | grep /mnt/pv

echo "Write/Read test on PV mount"
date > /mnt/pv/timestamp || echo "FAILURE"

cat /mnt/pv/timestamp  || echo "FAILURE"

rm /mnt/pv/timestamp; ret=$?

if [ "x$ret" = "x0" ]; then
    echo "SUCCESS"

    echo "Validated PV successfully" >> /usr/share/nginx/html/index.html
else
    echo "FAILURE"

    echo "Failed to validate PV" >> /usr/share/nginx/html/index.html    
fi

# Want the application to always run
/bin/bash
