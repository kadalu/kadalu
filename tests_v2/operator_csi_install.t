# -*- mode: ruby -*-
load "./tests_v2/env.t"

def cleanup
  TEST "kubectl delete -f manifests/kadalu-operator.yaml"
  TEST "kubectl delete -f manifests/csi-nodeplugin.yaml"
end

# Setup K8s
#load 'tests/setup.t'

# Install Operator using Yaml files
TEST "kubectl apply -f manifests/kadalu-operator.yaml"
TEST "kubectl apply -f manifests/csi-nodeplugin.yaml"
  
# Verify the Operator services running
EMIT_STDOUT true do
  TEST "bash #{SCRIPTS}/check_operator_pod_ready_state.sh"
  TEST "bash #{SCRIPTS}/check_csi_pods_ready_state.sh"
end

# TODO: Install Operator using Krew
# TODO: Install the Operator using Helm
# TODO: Install the Operator using kubectl-kadalu
