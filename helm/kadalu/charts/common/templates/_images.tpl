{{/* vim: set filetype=mustache: */}}

{{/*
Kadalu proper image repository
*/}}
{{- define "common.images.image" -}}
{{- print .Values.global.image.repository }}
{{- end -}}