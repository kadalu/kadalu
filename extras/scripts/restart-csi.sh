#!/bin/bash
kubectl get pods -nkadalu | grep "csi-" | awk '{print $1}' | xargs kubectl delete pod -nkadalu
