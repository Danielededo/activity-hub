{{- define "activity-hub.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "activity-hub.fullname" -}}
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

{{- define "activity-hub.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "activity-hub.labels" -}}
helm.sh/chart: {{ include "activity-hub.chart" . }}
app.kubernetes.io/name: {{ include "activity-hub.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{- define "activity-hub.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}
{{- default (include "activity-hub.fullname" .) .Values.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.serviceAccount.name -}}
{{- end -}}
{{- end -}}

{{- define "activity-hub.postgresqlFullname" -}}
{{- printf "%s-postgresql" (include "activity-hub.fullname" .) -}}
{{- end -}}

{{/*
Where the DATABASE_URL comes from: the chart's own secret when PostgreSQL is
bundled, or one you already have when it is not. Either way the backend reads a
single URL, so there is one code path in the app.
*/}}
{{- define "activity-hub.databaseSecretName" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-database" (include "activity-hub.fullname" .) -}}
{{- else -}}
{{- required "externalDatabase.existingSecret is required when postgresql.enabled is false" .Values.externalDatabase.existingSecret -}}
{{- end -}}
{{- end -}}

{{- define "activity-hub.databaseSecretKey" -}}
{{- if .Values.postgresql.enabled -}}database-url{{- else -}}{{ .Values.externalDatabase.existingSecretKey }}{{- end -}}
{{- end -}}

{{- define "activity-hub.postgresqlPassword" -}}
{{- if .Values.postgresql.auth.existingSecret -}}
{{- /* Read at render time so the URL in our secret matches yours. */ -}}
{{- $secret := lookup "v1" "Secret" .Release.Namespace .Values.postgresql.auth.existingSecret -}}
{{- if $secret -}}
{{- index $secret.data .Values.postgresql.auth.existingSecretPasswordKey | b64dec -}}
{{- else -}}
{{- required (printf "secret %s not found in namespace %s" .Values.postgresql.auth.existingSecret .Release.Namespace) "" -}}
{{- end -}}
{{- else -}}
{{- required "postgresql.auth.password is required (or set postgresql.auth.existingSecret)" .Values.postgresql.auth.password -}}
{{- end -}}
{{- end -}}
