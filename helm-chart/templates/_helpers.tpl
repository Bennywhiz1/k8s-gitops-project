{{- define "k8s-autoscaling-demo.name" -}}
{{- .Chart.Name -}}
{{- end -}}

{{- define "k8s-autoscaling-demo.fullname" -}}
{{- .Release.Name }}-{{ .Chart.Name -}}
{{- end -}}

{{- define "k8s-autoscaling-demo.labels" -}}
app.kubernetes.io/name: {{ include "k8s-autoscaling-demo.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}
