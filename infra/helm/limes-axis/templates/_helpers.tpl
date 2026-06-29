{{- define "limes-axis.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "limes-axis.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "limes-axis.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "limes-axis.labels" -}}
helm.sh/chart: {{ include "limes-axis.chart" . }}
app.kubernetes.io/name: {{ include "limes-axis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "limes-axis.selectorLabels" -}}
app.kubernetes.io/name: {{ include "limes-axis.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "limes-axis.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "limes-axis.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "limes-axis.apiImage" -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.api.image.repository .Values.api.image.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.api.image.repository .Values.api.image.tag -}}
{{- end -}}
{{- end -}}

{{- define "limes-axis.webImage" -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.web.image.repository .Values.web.image.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.web.image.repository .Values.web.image.tag -}}
{{- end -}}
{{- end -}}
