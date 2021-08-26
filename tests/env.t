HOME = ENV["HOME"]
VM_DRIVER = ENV.fetch("VM_DRIVER", "none")
SCRIPTS = "./tests/scripts"

MINIKUBE_VERSION = ENV.fetch("MINIKUBE_VERSION", "v1.15.1")
KUBE_VERSION = ENV.fetch("KUBE_VERSION", "v1.20.0")
COMMIT_MSG = ENV.fetch("COMMIT_MSG", "")
MEMORY = ENV.fetch("MEMORY", "3000")

#configure image repo
KADALU_IMAGE_REPO = ENV.fetch("KADALU_IMAGE_REPO", "docker.io/kadalu")
K8S_IMAGE_REPO = ENV.fetch("K8S_IMAGE_REPO", "quay.io/k8scsi")

#feature-gates for kube
K8S_FEATURE_GATES = ENV.fetch("K8S_FEATURE_GATES", "BlockVolume=true,CSIBlockVolume=true,VolumeSnapshotDataSource=true,CSIDriverRegistry=true")

DISK = "sda1"
if VM_DRIVER == "kvm2"
  # use vda1 instead of sda1 when running with the libvirt driver
  DISK = "vda1"
end
