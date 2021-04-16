# Release management

## From github UI

This is the approach kadalu team is using for release. This can be done by
just creating a 'Release' in UI. It will trigger the script from github
actions, and it will create all relevant scripts in the corresponding
folder in github.

Check the [Release URL here](https://github.com/kadalu/kadalu/releases)

## From the Makefile

1. Update CHANGELOG.md file with the list of changes and link
2. Run `make release` to generate Operator manifest file and build
   Containers for a specific version(and latest). Built Containers
   will be published to dockerhub.

        TWINE_PASSWORD=<secret> KADALU_VERSION=0.4.0 make release

   **Note**: If `DOCKER_USER` is specified then it will publish the built
   Containers to respective Dockerhub account.

        DOCKER_USER=aravindavk KADALU_VERSION=0.7.0 make release

3. Send the PR with manifest file and CHANGELOG.md file changes
4. Create a new Github release - [https://github.com/kadalu/kadalu/releases/new](https://github.com/kadalu/kadalu/releases/new). In the
   release notes, update the Operator manifest file link as,

        https://raw.githubusercontent.com/kadalu/kadalu/devel/manifests/kadalu-operator-<version>.yaml

   For example,

        kubectl apply -f https://raw.githubusercontent.com/kadalu/kadalu/devel/manifests/kadalu-operator-0.7.0.yaml
