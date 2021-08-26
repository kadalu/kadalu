# As per https://github.com/actions/virtual-environments/blob/main/images/linux/Ubuntu2004-README.md
# `helm` is already part of github runner
for distro in kubernetes rke microk8s openshift
do
    if [ "$distro" != "kubernetes" ]; then
        export operator="kadalu-operator-$distro"
        export nodeplugin="csi-nodeplugin-$distro"
    else
        export operator="kadalu-operator"
        export nodeplugin="csi-nodeplugin"
    fi
    export verbose="yes" dist=$distro
    echo Validating helm template for "'$distro'" against "'$operator'" [Empty for no diff]
    echo

    # Helm templates will not have 'kind: Namespace' so need to skip first 6 lines from operator manifest
    if [ "$distro" == "openshift" ]; then
        # Helm follows a specific order while installing/uninstalling (https://github.com/helm/helm/blob/release-3.0/pkg/releaseutil/kind_sorter.go#L27)
        # resources and it doesn't contain OpenShift 'SecurityContextConstraints' kind, so need to sort lines before 'diff'
        diff <(helm template --namespace kadalu helm/kadalu --set operator.enabled=true --set-string operator.kubernetesDistro=$distro,operator.verbose=$verbose | grep -v '#' | sort) \
             <(grep -v '#' manifests/"$operator.yaml" | tail -n +6 | sed '/^kind: CustomResourceDefinition/,/^spec:/{/namespace/d}' | sort ) --ignore-blank-lines
    else
        diff <(helm template --namespace kadalu helm/kadalu --set operator.enabled=true --set-string operator.kubernetesDistro=$distro,operator.verbose=$verbose | grep -v '#') \
             <(grep -v '#' manifests/"$operator.yaml" | tail -n +6 | sed '/^kind: CustomResourceDefinition/,/^spec:/{/namespace/d}' ) --ignore-blank-lines
    fi

    echo Validating helm template for "'$distro'" against "'$nodeplugin'" [Empty for no diff]
    echo
    diff <(helm template --namespace kadalu helm/kadalu --set csi-nodeplugin.enabled=true --set-string csi-nodeplugin.kubernetesDistro=$distro,csi-nodeplugin.verbose=$verbose | grep -v '#') \
         <(grep -v '#' manifests/"$nodeplugin.yaml") --ignore-blank-lines
done
unset operator nodeplugin verbose dist
