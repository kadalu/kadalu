#!/bin/bash

# Set default values
STORAGE_POOL_NAME=storage-pool-1
HOSTNAME=NULL
DEVICE_FILE_PATH=NULL
#PVC_FILE_NAME=sample-pvc
PVC_FILE_PATH=../../examples/sample-pvc.yaml
PVC_FILE_NAME="$(basename $PVC_FILE_PATH)"
PVC_NAME=pv1
STORAGE_VALUE=NULL
#POD_FILE_NAME=sample-app
POD_FILE_PATH=../../examples/sample-app.yaml
POD_FILE_NAME="$(basename $POD_FILE_PATH)"
POD_NAME=pod1

function main(){
    if [[ $# == 0 ]]
    then
        help
    else
        parse_args $@
    fi
}

function help(){
    echo "usage: ${0} [--option=argument] or ${0} [-o argument]"
    echo "  -h | --help   help            display help"
    echo "  -s | --storage-pool-name      specify storage-pool-name"
    echo "  -n | --hostname               specify the device/host-name"
    echo "  -d | --device-file-path       specify the device file path [Mandatory]"
    echo "  -p | --pvc-filename           specify the name for pvc.yaml"
    echo "  -P | --pvc-name               specify the PVC name"
    echo "  -v | --storage-value          specify the storage value in Ngi or NNNMi [Mandatory]"
    echo "  -o | --pod-filename           specify the name for app.yaml"
    echo "  -O | --pod-name               specify the pod name"
    echo "  Mandatory arguments for all options."
    echo "  Arguments for long options should be preceeded with '=' not space. Ex: --device=minikube"
    echo "  --storage-value and --device-file-path are mandatory options rest are optional."
    exit 1
}

function parse_args(){

    die() {
        # Complain to STDERR and show help
        echo "$*" >&2;
        help;
    }

    needs_arg() {
        # Handle no argument case for long option
        if [[ -z "$OPTARG" ]] ;
        then
            die "No argument given for --${OPT} option";
            help
        fi;
    }

    arg_hostname=""

    while getopts :hs:n:d:p:P:v:o:O:-: OPT;
    do
        if [[ "$OPT" = "-" ]];        # long option: reformulate OPT and OPTARG
        then
            OPT="${OPTARG%%=*}"       # extract long option name
            OPTARG="${OPTARG#$OPT}"   # extract long option argument (may be empty)
            OPTARG="${OPTARG#=}"      # if long option argument, remove assigning `=`
        fi
        case "$OPT" in
            h | help             )       help;;
            s | storage-pool-name)       needs_arg; STORAGE_POOL_NAME=$OPTARG;;
            n | hostname         )       needs_arg; arg_hostname=$OPTARG; ;;
            d | device-file-path )       needs_arg; DEVICE_FILE_PATH=$OPTARG;;
            p | pvc-filename     )       needs_arg; PVC_FILE_NAME=$OPTARG;;
            P | pvc-name         )       needs_arg; PVC_NAME=$OPTARG;;
            v | storage-value    )       needs_arg; STORAGE_VALUE=$OPTARG;;
            o | pod-filename     )       needs_arg; POD_FILE_NAME=$OPTARG;;
            O | pod-name         )       needs_arg; POD_NAME=$OPTARG;;
            :                    )       echo No argument given for ${OPTARG} option; help;;
            ??*                  )       die  Bad long option --$OPT; help;;  # No such long option
            ?                    )       die  Bad short option -$OPTARG; help;;  # No such short option
        esac
    done

    validate_hostname $arg_hostname

    if [[ "$DEVICE_FILE_PATH" == "NULL" || "$STORAGE_VALUE" == "NULL" ]] ;
    then
        echo "--storage-value and --device-file-path are mandatory options."
        echo "See usage with --help option."
        exit 1
    fi

    kadalu_quick_start
}

# Based on the idea from https://github.com/kadalu/kadalu/manifests/minikube.sh
function wait_till_pods_start(){
    # give it some time
    cnt=0
    local_timeout=200
    while true;
    do
        cnt=$((cnt + 1))
        sleep 2
        ret_kadalu_pods=$(sudo kubectl get pods -nkadalu -o wide | grep 'Running' | wc -l)
        ret_pvc=$(sudo kubectl get pvc $PVC_NAME | grep 'Bound' | wc -l)
        ret_pod=$(sudo kubectl get pod $POD_NAME | grep 'Completed' | wc -l)

        if [[ "${ret_kadalu_pods}" == "4" && "${ret_pvc}" == "1" && "${ret_pod}" == "1" ]]; then
            echo "All Kadalu pods in status: 'Running'"
            echo "PVC $PVC_NAME in status: 'Bound'"
            echo "POD $POD_NAME in status: 'Completed'"
            echo "Successful after $cnt seconds"
            break
        fi
        if [[ $cnt -eq ${local_timeout} ]]; then
            kubectl get pods -o wide
            echo "giving up after ${local_timeout} seconds"
            fail=1
            break
        fi
        if [[ $((cnt % 15)) -eq 0 ]]; then
            echo "$cnt: Waiting for pods to come up..."
        fi
    done
}

function validate_hostname(){

    i=0
    local_hostname=""
    arg_hostname=$1
    # Read by lines from stdout. If is i>1, ask to specify the required hostname/device.
    cmd=$(sudo kubectl get nodes -o=name)
    while read -r line;
    do
        let "i++"
        local_hostname=$(basename $line)
        if [[ "$local_hostname" == "$arg_hostname" ]]; then
            HOSTNAME=$local_hostname
            return 0
        fi
    done <<< "$cmd"

    # Anything other than empty is invalid after the while pass & comparison.
    if [[ "$arg_hostname" != "" ]] ;
    then
        echo "specified hostname is not present in cluster."
        exit 1
    fi

    if [[ $i -gt 1 ]] ;
    then
        echo "Number of hostnames are $i"
        echo "More than one hostname present. Choose one of the above with --hostname option."
        exit 1
    fi

    # When no hostname is specified.
    HOSTNAME=$local_hostname
}

function kadalu_quick_start(){

    # Start kadalu operator
    sudo kubectl apply -f https://raw.githubusercontent.com/kadalu/kadalu/devel/manifests/kadalu-operator.yaml

    # Base storage
    echo "Hostname is ${HOSTNAME}"
    sudo cp ../../examples/sample-storage.yaml /tmp/kadalu-storage1.yaml
    sudo sed -i "s/storage-pool-1/${STORAGE_POOL_NAME}/g" /tmp/kadalu-storage1.yaml
    sudo sed -i s/kube1/${HOSTNAME}/g /tmp/kadalu-storage1.yaml
    sed -ie "s|/dev/vdc|${DEVICE_FILE_PATH}|g" /tmp/kadalu-storage1.yaml

    sudo kubectl apply -f /tmp/kadalu-storage1.yaml

    # PV Claim
    sudo cp ${PVC_FILE_PATH} /tmp/${PVC_FILE_NAME}
    sudo sed -i s/pv1/$PVC_NAME/g  /tmp/${PVC_FILE_NAME}
    sudo sed -i s/1Gi/$STORAGE_VALUE/g  /tmp/${PVC_FILE_NAME}

    sudo kubectl apply -f /tmp/${PVC_FILE_NAME}

    # POD
    sudo cp ${POD_FILE_PATH} /tmp/${POD_FILE_NAME}
    sudo sed -i s/pod1/$POD_NAME/g  /tmp/${POD_FILE_NAME}
    sudo sed -i s/pv1/$PVC_NAME/g  /tmp/${POD_FILE_NAME}

    sudo kubectl apply -f /tmp/${POD_FILE_NAME}

    wait_till_pods_start
}

main $@
