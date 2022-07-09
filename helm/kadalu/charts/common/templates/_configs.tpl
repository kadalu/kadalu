{{/* vim: set filetype=mustache: */}}

{{/*
Kadalu KUBELET_DIR
*/}}
{{- define "common.configs.kubeletDir" -}}
{{- if (eq .Values.global.kubernetesDistro "microk8s") -}}
{{ default "/var/snap/microk8s/common/var/lib/kubelet" .Values.global.kubeletDir }}
{{- else -}}
{{ default "/var/lib/kubelet" .Values.global.kubeletDir }}
{{- end -}}
{{- end -}}