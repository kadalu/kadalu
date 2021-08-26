EXIT_ON_NOT_OK true

load "./tests/env.t"
load "./tests/setup.t"

output = TEST "kubectl get nodes -o=name"
# output will be in format 'node/hostname'. We need 'hostname'
HOSTNAME = TEST "basename #{output.strip}"
puts "Hostname is ${HOSTNAME}"

# install kubectl kadalu
TEST "KADALU_VERSION=\"0.0.1canary\" make cli-build"

TEST "sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml"

puts "Installing Operator through CLI"
TEST "cli/build/kubectl-kadalu install --local-yaml manifests/kadalu-operator.yaml --local-csi-yaml manifests/csi-nodeplugin.yaml"

TEST "sed -i -e \"s/DISK/#{DISK}/g\" tests/get-minikube-pvc.yaml"
TEST "kubectl apply -f tests/get-minikube-pvc.yaml"

TEST "sleep 1"
TEST "cli/build/kubectl-kadalu storage-add storage-pool-3 --script-mode --type Replica3 --device #{HOSTNAME}:/mnt/#{DISK}/file3.1 --path #{HOSTNAME}:/mnt/#{DISK}/dir3.2 --pvc local-pvc"

# TODO: Enable this test after we resume testing Replica2 gluster cluster
# Test Replica2 option
# TEST "cli/build/kubectl-kadalu storage-add storage-pool-2 --script-mode --type Replica2 --device #{HOSTNAME}:/mnt/#{DISK}/file2.1 --device #{HOSTNAME}:/mnt/#{DISK}/file2.2"

# # Test Replica2 with tie-breaker option
# TEST "sudo truncate -s 2g /mnt/#{DISK}/file2.{10,20}"

# TEST "cli/build/kubectl-kadalu storage-add storage-pool-2-1 --script-mode --type Replica2 --device #{HOSTNAME}:/mnt/#{DISK}/file2.10 --device #{HOSTNAME}:/mnt/#{DISK}/file2.20 --tiebreaker tie-breaker.kadalu.io:/mnt"

# Check if the type default is Replica1
TEST "cli/build/kubectl-kadalu storage-add storage-pool-1 --script-mode --device #{HOSTNAME}:/mnt/#{DISK}/file1.1 --device #{HOSTNAME}:/mnt/#{DISK}/file1.2 --device #{HOSTNAME}:/mnt/#{DISK}/file1.3"

# Check for Disperse Volume
TEST "sleep 1"
TEST "cli/build/kubectl-kadalu storage-add storage-pool-4 --script-mode --type Disperse --data 2 --redundancy 1 --device #{HOSTNAME}:/mnt/#{DISK}/file4.1 --device #{HOSTNAME}:/mnt/#{DISK}/file4.2 --device #{HOSTNAME}:/mnt/#{DISK}/file4.3"

# Check for external storage
# TODO: For now, keep the name as 'ext-config' as PVC should use this to send request.
# TODO: Enable this test after we resume testing external gluster cluster
# TEST "cli/build/kubectl-kadalu storage-add ext-config --script-mode --external gluster1.kadalu.io:/kadalu"

TEST "bash -x #{SCRIPTS}/wait_till_pods_start.sh"

load "./tests/storage_tests.t"

RUN "bash -x #{SCRIPTS}/print_all_logs.sh"
load "./tests/cleanup.t"
