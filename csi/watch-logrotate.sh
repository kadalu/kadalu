#!/bin/bash
while true
do
  if [[ $(ls /var/log/gluster/*.gz | wc -l) -ge 4 ]]; then
    rm -rf /var/log/gluster/*.gz
  fi
  logrotate /kadalu/logrotate.conf
  /usr/bin/killall -HUP glusterfs > /dev/null 2>&1 || true
  # Run logrotate for every 8 hours
  sleep 28800
done
