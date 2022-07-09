{{/* vim: set filetype=mustache: */}}

{{/*
Kadalu KADALU_VERSION
*/}}
{{- define "common.version" -}}
{{- if eq .Chart.Version "0.0.0-0" -}}
{{ print "devel" }}
{{- else -}}
{{ .Chart.Version }}
{{- end -}}
{{- end -}}