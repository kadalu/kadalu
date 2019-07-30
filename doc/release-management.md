# Release management

1. Update CHANGELOG.md file with the list of changes and link
2. Generate Operator yaml file with version

        KADALU_VERSION=0.1.0 make gen-manifest
        cp manifests/kadalu-operator.yaml manifests/kadalu-operator-0.1.0.yaml
        make gen-manifest

3. Build Containers with the required version

        KADALU_VERSION=0.1.0 make build-containers
        docker push kadalu/kadalu-operator:0.1.0
        docker push kadalu/kadalu-csi:0.1.0
        docker push kadalu/kadalu-server:0.1.0
        make build-containers
        docker push kadalu/kadalu-operator:latest
        docker push kadalu/kadalu-csi:latest
        docker push kadalu/kadalu-server:latest

4. Send the PR with manifest file changes
5. Tag and Release with release notes. Operator link will be(Short URL will be planned soon)

        https://raw.githubusercontent.com/aravindavk/kadalu/master/manifests/kadalu-operator-<version>.yaml

