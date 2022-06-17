{{/* vim: set filetype=mustache: */}}

{{/*
Kadalu standard labels
*/}}
{{- define "common.labels.standard" -}}
app.kubernetes.io/part-of: kadalu
app.kubernetes.io/name: {{ printf "kadalu-%s" .Chart.Name }}
{{- end -}}