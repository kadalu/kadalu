#!/bin/bash


# Make sure we start only after there is a file in '/logs/'
LOGDIR="/logs"

while true;
do
    filecnt=$(ls ${LOGDIR}/*.log | wc -l)
    if [ ${filecnt} -gt 0 ]; then
	break
    fi
    sleep 3
done

OUTPUT_FILE="nohup.out"

touch ${OUTPUT_FILE}
declare -A log_files

while true;
do
    # Log every file.
    tail -f ${LOGDIR}/*.log

    # TODO: this doesn't handle the newly created files
    # after the first execution. Need to work on that
    #
done    
