#!/bin/bash

volname=$1

kill -SIGTERM $(cat /var/run/gluster/glusterfsd-bricks-${volname}-data-brick.pid)
umount /bricks/${volname}/data
