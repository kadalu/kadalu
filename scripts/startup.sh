#!/usr/bin/env bash
set -x

pid=0
cmd=$1
script=$2


# SIGTERM-handler
term_handler() {
    if [ $pid -ne 0 ]; then
        kill -SIGTERM "$pid"
        wait "$pid"
    fi
    exit 143; # 128 + 15 -- SIGTERM
}


trap 'kill ${!}; term_handler' SIGTERM

$cmd $script &
pid="$!"

# wait forever
while true
do
    tail -f /dev/null & wait ${!}
done
