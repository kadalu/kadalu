kubectl -nkadalu delete StatefulSet csi-kadalu-provisioner
kubectl -nkadalu delete ClusterRoleBinding csi-provisioner-role
kubectl -nkadalu delete ServiceAccount csi-provisioner
kubectl -nkadalu delete ClusterRole external-provisioner-runner
kubectl -nkadalu delete DaemonSet csi-kadalu-nodeplugin
kubectl -nkadalu delete ClusterRoleBinding csi-nodeplugin
kubectl -nkadalu delete ClusterRole csi-nodeplugin
kubectl -nkadalu delete ServiceAccount csi-nodeplugin
kubectl -nkadalu delete StatefulSet csi-kadalu-attacher
kubectl -nkadalu delete ClusterRoleBinding csi-attacher-role
kubectl -nkadalu delete ClusterRole external-attacher-runner
kubectl -nkadalu delete ServiceAccount csi-attacher
kubectl -nkadalu delete Service glustervol
kubectl -nkadalu delete StatefulSet glustervol-kube1
kubectl delete namespace kadalu
kubectl delete storageclass kadalu.gluster
