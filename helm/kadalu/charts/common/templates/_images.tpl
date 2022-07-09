{{/* vim: set filetype=mustache: */}}

{{/*
Kadalu proper image repository
*/}}
{{- define "common.images.image" -}}
{{- printf "%s/%s" .Values.global.image.registry .Values.global.image.repository }}
{{- end -}}