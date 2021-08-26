EXIT_ON_NOT_OK true

load "./tests/env.t"
load "./tests/setup.t"

# List of available docker images
puts TEST "docker images"

if !COMMIT_MSG.include?('helm skip')
  puts TEST "bash -x #{SCRIPTS}/helm_tests.sh"
end

puts "Starting the kadalu Operator"
# pick the operator file from repo
TEST "sed -i -e 's/imagePullPolicy: Always/imagePullPolicy: IfNotPresent/g' manifests/kadalu-operator.yaml"
TEST "kubectl apply -f manifests/kadalu-operator.yaml"
TEST "kubectl apply -f manifests/csi-nodeplugin.yaml"

TEST "sleep 1"
# Start storage
output = TEST "kubectl get nodes -o=name"
# output will be in format 'node/hostname'. We need 'hostname'
HOSTNAME = TEST "basename #{output.strip}"

puts "Hostname is #{HOSTNAME}"
TEST "cp tests/storage-add.yaml /tmp/kadalu-storage.yaml"
TEST "sed -i -e \"s/DISK/#{DISK}/g\" /tmp/kadalu-storage.yaml"
TEST "sed -i -e \"s/node: minikube/node: #{HOSTNAME}/g\" /tmp/kadalu-storage.yaml"

# Prepare PVC also as a storage
TEST "sed -i -e \"s/DISK/#{DISK}/g\" tests/get-minikube-pvc.yaml"
TEST "kubectl apply -f tests/get-minikube-pvc.yaml"

# Generally it needs some time for operator to get started, give it time, so some logs are reduced in tests
TEST "sleep 15"
TEST "kubectl apply -f /tmp/kadalu-storage.yaml"

puts TEST "bash -x #{SCRIPTS}/wait_till_pods_start.sh"

load "./tests/storage_tests.t"

RUN "bash -x #{SCRIPTS}/print_all_logs.sh"
load "./tests/cleanup.t"
