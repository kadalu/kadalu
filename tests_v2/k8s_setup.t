#-*- mode: ruby -*-

load "./tests_v2/env.t"

EMIT_STDOUT true do
  # Install Minikube
  TEST "bash #{SCRIPTS}/install_minikube.sh #{ARCH} #{MINIKUBE_VERSION}"

  # Install Kubectl
  TEST "bash #{SCRIPTS}/install_kubectl.sh #{ARCH} #{KUBE_VERSION}"

  # Start Minikube
  TEST "sysctl fs.protected_regular=0"
  TEST "swapoff -a"
  TEST "mkdir -p #{ENV["HOME"]}/.kube #{ENV["HOME"]}/.minikube"
  TEST %Q[minikube start --memory="#{MEMORY}" -b kubeadm --kubernetes-version="#{KUBE_VERSION}" --vm-driver="#{VM_DRIVER}" --feature-gates="#{K8S_FEATURE_GATES}"]
end
