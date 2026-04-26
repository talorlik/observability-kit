{{- define "observability-lib.labels" -}}
service.name: {{ required "observability.serviceName is required" .Values.observability.serviceName | quote }}
deployment.environment: {{ required "observability.environment is required" .Values.observability.environment | quote }}
service.owner: {{ required "observability.owner is required" .Values.observability.owner | quote }}
{{- end -}}

{{- define "observability-lib.scrapeAnnotation" -}}
{{- if eq .Values.observability.subscriptionMode "low-touch" -}}
observability.opentelemetry.io/scrape: "true"
{{- end -}}
{{- end -}}

{{- define "observability-lib.instrumentationEnabled" -}}
{{- if eq .Values.observability.subscriptionMode "instrumentation" -}}
true
{{- else -}}
false
{{- end -}}
{{- end -}}
