#!/bin/bash -e

# Ask for permission to do a minikube delete first.

echo -n "This does 'minikube delete' before running minikube start. Are you OK? (Y/n): "
read yesno

if [ "x${yesno}" == "xn" -o "x${yesno}" == "xN" ]; then
    exit 0;
fi

# delete minikube first
minikube delete

# Found this script with  https://github.com/kubernetes-csi/docs/issues/37
minikube start --vm-driver=kvm2 --memory=4096  --feature-gates=KubeletPluginsWatcher=true,BlockVolume=true,CSIBlockVolume=true,VolumeSnapshotDataSource=true

# # replace /var sys links with abs links
# VAR_CMD="sudo find /var -type l -execdir bash -c 'ln -sfn \"\$(readlink -f \"\$0\")\" \"\${PWD}/\$(basename \$0)\"' {} \\;"
# minikube ssh "$VAR_CMD"

# # replace etc sys links with abs links
# ETC_CMD="sudo find /etc -type l -execdir bash -c 'ln -sfn \"\$(readlink -f \"\$0\")\" \"\${PWD}/\$(basename \$0)\"' {} \\;"
# minikube ssh "$ETC_CMD"

# # prepare a storage with xattrs
PREPARE_STORAGE="sudo mkdir /mnt/data && sudo truncate -s 5g /mnt/vda1/disk-file && \
                 sudo mkfs.xfs /mnt/vda1/disk-file && sudo mount /mnt/vda1/disk-file /mnt/data"
minikube ssh "$PREPARE_STORAGE"


# Also noticed there were instances where /etc/resolv.conf was not properly linked.

# PREPARE_NW="sudo touch /etc/systemd/resolv.conf && \
#            sudo sed -i -e '#s##nameserver 8.8.8.8#g' /etc/systemd/resolv.conf && \
#            sudo ln -sfn /etc/systemd/resolv.conf /etc/resolv.conf"
# minikube ssh "$PREPARE_NW"
