TEST "sudo sysctl fs.protected_regular=0"

TEST "bash -x #{SCRIPTS}/install_minikube.sh"
#if driver  is 'none' install kubectl with KUBE_VERSION
if VM_DRIVER == "none"
  TEST "mkdir -p \"#{HOME}/.kube\" \"#{HOME}/.minikube\""
  TEST "bash -x #{SCRIPTS}/install_kubectl.sh"
end

puts "starting minikube with kubeadm bootstrapper"
TEST "minikube start --memory=\"#{MEMORY}\" -b kubeadm --kubernetes-version=\"#{KUBE_VERSION}\" --vm-driver=\"#{VM_DRIVER}\" --feature-gates=\"#{K8S_FEATURE_GATES}\""

# environment
if VM_DRIVER != "none"
  TEST "bash -x #{SCRIPTS}/wait_for_ssh.sh"
  # shellcheck disable=SC2086
  TEST "minikube ssh \"sudo mkdir -p /mnt/#{DISK};sudo rm -rf /mnt/#{DISK}/*; sudo truncate -s 4g /mnt/#{DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1,4.1,4.2,4.3}; sudo mkdir -p /mnt/#{DISK}/{dir3.2,dir3.2_modified,pvc}\""
else
  TEST "sudo mkdir -p /mnt/#{DISK}"
  TEST "sudo rm -rf /mnt/#{DISK}/*"
  TEST "sudo truncate -s 4g /mnt/#{DISK}/file{1.1,1.2,1.3,2.1,2.2,3.1,4.1,4.2,4.3}"
  TEST "sudo mkdir -p /mnt/#{DISK}/dir3.2"
  TEST "sudo mkdir -p /mnt/#{DISK}/dir3.2_modified"
  TEST "sudo mkdir -p /mnt/#{DISK}/pvc"
end

# Dump Cluster Info
puts TEST "kubectl cluster-info"
