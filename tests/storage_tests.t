puts TEST "date"

TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-test-app3.yaml \"Replica3\" 2 90"

TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-test-app1.yaml \"Replica1\" 2 90"

TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-test-app4.yaml \"Disperse\" 2 90"

# TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-external-storage.yaml \"External (PV)\" 1 60"

# TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-external-kadalu-storage.yaml \"External (Kadalu)\" 2 90"

TEST "cp tests/storage-add.yaml /tmp/kadalu-storage.yaml"
TEST "sed -i -e \"s/DISK/#{DISK}/g\" /tmp/kadalu-storage.yaml"
TEST "sed -i -e \"s/node: minikube/node: #{HOSTNAME}/g\" /tmp/kadalu-storage.yaml"
TEST "sed -i -e \"s/dir3.2/dir3.2_modified/g\" /tmp/kadalu-storage.yaml"
TEST "kubectl apply -f /tmp/kadalu-storage.yaml"

TEST "sleep 5"
puts "After modification"
# Observing intermittent failures due to timeout after modification with a
# difference of ~2 min
TEST "bash #{SCRIPTS}/wait_till_pods_start.sh 400"

# TEST "bash #{SCRIPTS}/get_pvc_and_check.sh examples/sample-test-app2.yaml \"Replica2\" 2 60"

# Run minimal IO test
load "./tests/io_tests.t"

# Deploy and run CSI Sanity tests
TEST "kubectl apply -f tests/test-csi/sanity-app.yaml"
TEST "kubectl wait --for=condition=ready pod -l app=sanity-app --timeout=15s"

exp_pass = "33"

# Set expand vol size to 10MB
TEST "kubectl exec sanity-app -i -- sh -c 'csi-sanity -ginkgo.v --csi.endpoint $CSI_ENDPOINT -ginkgo.skip pagination -csi.testvolumesize 10485760 -csi.testvolumeexpandsize 10485760' | tee /tmp/sanity-result.txt"

# Make sure no more failures than above stats
act_pass = TEST "grep -Po '(\d+)(?= Passed)' /tmp/sanity-result.txt 2>/dev/null"
TRUE act_pass == exp_pass, "Sanity tests passed", "Actual: #{act_pass}, Expected: #{exp_pass}"
