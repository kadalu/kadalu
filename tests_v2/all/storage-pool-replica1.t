#-*- mode: ruby -*-

# Create Storage Pool
TEST "kubectl create -f tests_v2/manifests/storage-pool-replica1.yaml"

# Test if Storage container started
EMIT_STDOUT true do
  TEST "bash #{SCRIPTS}/check_server_pods_ready_state.sh"
end

TEST "kubectl apply -f examples/sample-test-app1.yaml"

# Verify the default Storage Class
# For each Subvol, Block mounted, Block Vol
#   Create a PV
#   Run App Pod
#   Expand PV
#   Run App Pod
#   Remove/Delete App Pod
#   PV list verify
#   Delete the PV
# View Storage Pool list, status and detail
# Delete Storage Pool
