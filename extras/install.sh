#!/bin/bash

curl -fsSL https://github.com/kadalu/kadalu/releases/latest/download/kubectl-kadalu -o /tmp/kubectl-kadalu

install /tmp/kubectl-kadalu /usr/bin/kubectl-kadalu
install /tmp/kubectl-kadalu /usr/bin/oc-kadalu
