kubectl -nkadalu delete StatefulSet csi-provisioner
kubectl -nkadalu delete ClusterRoleBinding csi-provisioner-role
kubectl -nkadalu delete ServiceAccount csi-provisioner
kubectl -nkadalu delete ClusterRole external-provisioner-runner
kubectl -nkadalu delete DaemonSet csi-nodeplugin
kubectl -nkadalu delete ClusterRoleBinding csi-nodeplugin
kubectl -nkadalu delete ClusterRole csi-nodeplugin
kubectl -nkadalu delete ServiceAccount csi-nodeplugin
kubectl -nkadalu delete StatefulSet csi-attacher
kubectl -nkadalu delete ClusterRoleBinding csi-attacher-role
kubectl -nkadalu delete ClusterRole external-attacher-runner
kubectl -nkadalu delete ServiceAccount csi-attacher
kubectl -nkadalu delete Service glustervol
kubectl -nkadalu delete StatefulSet glustervol-kube1
kubectl -nkadalu delete Service glustervol1
kubectl -nkadalu delete StatefulSet glustervol1-kube1
kubectl delete storageclass kadalu.gluster

# Operator
kubectl delete -nkadalu CustomResourceDefinition kadaluvolumes.kadalu-operator.gluster
kubectl delete -nkadalu ClusterRole kadalu-operator
kubectl delete -nkadalu ServiceAccount kadalu-operator
kubectl delete -nkadalu ClusterRoleBinding kadalu-operator
kubectl delete -nkadalu Deployment kadalu-operator

kubectl delete namespace kadalu
