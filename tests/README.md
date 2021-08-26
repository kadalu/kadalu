# Kadalu Storage Tests using Binnacle

## Setup

Test setup should have `ruby` installed. Install Binnacle.

```bash
curl -L https://github.com/kadalu/binnacle/releases/latest/download/binnacle -o binnacle
chmod +x ./binnacle
sudo mv ./binnacle /usr/local/bin/binnacle
binnacle --version
```

Refer [this document](https://kadalu.io/docs/binnacle/devel/quick-start) for more details about Binnacle.

## Run Tests

YAML based Operator install and test Kadalu.

```console
$ binnacle -v tests/operator_tests.t
```

CLI (`kubectl-kadalu`) based Operator install and test Kadalu.

```console
$ binnacle -v tests/cli_tests.t
```
