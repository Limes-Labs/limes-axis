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

{{- define "limes-axis.workerImage" -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.worker.image.repository .Values.worker.image.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.worker.image.repository .Values.worker.image.tag -}}
{{- end -}}
{{- end -}}

{{- define "limes-axis.smokeTestImage" -}}
{{- if .Values.global.imageRegistry -}}
{{- printf "%s/%s:%s" .Values.global.imageRegistry .Values.tests.smoke.image.repository .Values.tests.smoke.image.tag -}}
{{- else -}}
{{- printf "%s:%s" .Values.tests.smoke.image.repository .Values.tests.smoke.image.tag -}}
{{- end -}}
{{- end -}}

{{/*
Required local services for the opt-in local-only egress profile. Names follow
issue #869 dependency ids so the chart graph stays traceable to the runtime
dependency inventory (docs/runtime-dependencies.local-profile.json).
*/}}
{{- define "limes-axis.requiredLocalOnlyServices" -}}
identity-validation,operational-database,workflow-engine,artifact-object-store,model-inference
{{- end -}}

{{/*
Reject an unbounded destination. An all-address rule would make the profile
indistinguishable from an allow-all policy.
*/}}
{{- define "limes-axis.assertBoundedCidr" -}}
{{- $cidr := .cidr | default "" | toString | trim -}}
{{- if or (eq $cidr "") (eq $cidr "0.0.0.0/0") (eq $cidr "::/0") -}}
{{- fail (printf "%s must declare a bounded CIDR; empty and all-address allow rules are not permitted in the local-only profile (got %q)" .context $cidr) -}}
{{- end -}}
{{- end -}}

{{/*
Fail-closed validation of the local-only egress graph. Runs before any rule is
rendered so a missing or unbounded binding never silently widens egress.
*/}}
{{- define "limes-axis.validateLocalOnly" -}}
{{- $networkPolicy := .Values.networkPolicy -}}
{{- $localOnly := $networkPolicy.localOnly | default dict -}}
{{- $dns := $localOnly.dns | default dict -}}
{{- $dnsMode := $dns.mode | default "cluster" -}}
{{- if $networkPolicy.allowedEgressCidrs -}}
{{- fail "networkPolicy.allowedEgressCidrs is not read in egressMode local_only; declare bounded destinations under networkPolicy.localOnly.services instead" -}}
{{- end -}}
{{- if not (has $dnsMode (list "cluster" "node_local" "explicit")) -}}
{{- fail (printf "networkPolicy.localOnly.dns.mode %q is not supported; use cluster, node_local or explicit" $dnsMode) -}}
{{- end -}}
{{- if and (eq $dnsMode "explicit") (not $dns.resolvers) -}}
{{- fail "networkPolicy.localOnly.dns.mode is explicit but networkPolicy.localOnly.dns.resolvers is empty; declare at least one resolver namespace/podSelector or ipBlock" -}}
{{- end -}}
{{- if eq $dnsMode "node_local" -}}
{{- include "limes-axis.assertBoundedCidr" (dict "cidr" ($dns.nodeLocalCidr | default "169.254.20.10/32") "context" "networkPolicy.localOnly.dns.nodeLocalCidr") -}}
{{- end -}}
{{- range $resolver := ($dns.resolvers | default list) -}}
{{- if $resolver.ipBlock -}}
{{- include "limes-axis.assertBoundedCidr" (dict "cidr" $resolver.ipBlock.cidr "context" "networkPolicy.localOnly.dns.resolvers[].ipBlock") -}}
{{- else if not (or $resolver.namespace $resolver.podSelector) -}}
{{- fail "networkPolicy.localOnly.dns.resolvers entries need a namespace, a podSelector (release namespace) or an ipBlock" -}}
{{- end -}}
{{- end -}}
{{- $declared := dict -}}
{{- range $service := ($localOnly.services | default list) -}}
{{- $name := $service.name | default "" -}}
{{- if not $name -}}
{{- fail "networkPolicy.localOnly.services entries require a name" -}}
{{- end -}}
{{- $_ := set $declared $name $service -}}
{{- end -}}
{{- range $required := (splitList "," (include "limes-axis.requiredLocalOnlyServices" .)) -}}
{{- if not (hasKey $declared $required) -}}
{{- fail (printf "networkPolicy.localOnly.services is missing required local service %q; declare it with state: local (namespace or ipBlock plus ports) or state: omitted with a reason. See docs/zero-egress-local-only-profile.md" $required) -}}
{{- end -}}
{{- $service := index $declared $required -}}
{{- $state := $service.state | default "local" -}}
{{- if not (has $state (list "local" "omitted")) -}}
{{- fail (printf "networkPolicy.localOnly.services[%s].state %q is not supported; use local or omitted" $required $state) -}}
{{- end -}}
{{- if eq $state "omitted" -}}
{{- if not ($service.reason | default "") -}}
{{- fail (printf "networkPolicy.localOnly.services[%s] is omitted without a reason; an omission needs an explicit, reviewable rationale" $required) -}}
{{- end -}}
{{- else -}}
{{- if not (or $service.namespace $service.podSelector $service.ipBlock) -}}
{{- fail (printf "networkPolicy.localOnly.services[%s] needs a namespace, a podSelector (release namespace) or an ipBlock destination" $required) -}}
{{- end -}}
{{- if not $service.ports -}}
{{- fail (printf "networkPolicy.localOnly.services[%s] needs at least one port" $required) -}}
{{- end -}}
{{- if $service.ipBlock -}}
{{- include "limes-axis.assertBoundedCidr" (dict "cidr" $service.ipBlock.cidr "context" (printf "networkPolicy.localOnly.services[%s].ipBlock" $required)) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/*
Scoped local-only egress rules: one rule for the configured resolvers and one
per declared local service. Rendered as YAML so the caller only re-indents.
*/}}
{{- define "limes-axis.localOnlyEgress" -}}
{{- $networkPolicy := .Values.networkPolicy -}}
{{- $localOnly := $networkPolicy.localOnly | default dict -}}
{{- $dns := $localOnly.dns | default dict -}}
{{- $dnsMode := $dns.mode | default "cluster" -}}
{{- $dnsPort := $networkPolicy.dnsPort | int -}}
{{- $dnsTargets := list -}}
{{- if eq $dnsMode "cluster" -}}
{{- $namespace := $dns.namespace | default "kube-system" -}}
{{- $selector := $dns.podSelector | default (dict "k8s-app" "kube-dns") -}}
{{- $dnsTargets = append $dnsTargets (dict "namespaceSelector" (dict "matchLabels" (dict "kubernetes.io/metadata.name" $namespace)) "podSelector" (dict "matchLabels" $selector)) -}}
{{- else if eq $dnsMode "node_local" -}}
{{- $namespace := $dns.namespace | default "kube-system" -}}
{{- $selector := $dns.podSelector | default (dict "k8s-app" "node-local-dns") -}}
{{- $dnsTargets = append $dnsTargets (dict "namespaceSelector" (dict "matchLabels" (dict "kubernetes.io/metadata.name" $namespace)) "podSelector" (dict "matchLabels" $selector)) -}}
{{- $dnsTargets = append $dnsTargets (dict "ipBlock" (dict "cidr" ($dns.nodeLocalCidr | default "169.254.20.10/32"))) -}}
{{- else -}}
{{- range $resolver := $dns.resolvers -}}
{{- if $resolver.ipBlock -}}
{{- $dnsTargets = append $dnsTargets (dict "ipBlock" (dict "cidr" $resolver.ipBlock.cidr)) -}}
{{- else -}}
{{- $target := dict -}}
{{- if $resolver.namespace -}}
{{- $_ := set $target "namespaceSelector" (dict "matchLabels" (dict "kubernetes.io/metadata.name" $resolver.namespace)) -}}
{{- end -}}
{{- with $resolver.podSelector -}}
{{- $_ := set $target "podSelector" (dict "matchLabels" .) -}}
{{- end -}}
{{- $dnsTargets = append $dnsTargets $target -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- $rules := list -}}
{{- $rules = append $rules (dict "to" $dnsTargets "ports" (list (dict "protocol" "UDP" "port" $dnsPort) (dict "protocol" "TCP" "port" $dnsPort))) -}}
{{- range $service := ($localOnly.services | default list) -}}
{{- if ne ($service.state | default "local") "omitted" -}}
{{- $target := dict -}}
{{- if $service.ipBlock -}}
{{- $target = dict "ipBlock" (dict "cidr" $service.ipBlock.cidr) -}}
{{- with $service.ipBlock.except -}}
{{- $_ := set $target.ipBlock "except" . -}}
{{- end -}}
{{- else -}}
{{- if $service.namespace -}}
{{- $_ := set $target "namespaceSelector" (dict "matchLabels" (dict "kubernetes.io/metadata.name" $service.namespace)) -}}
{{- end -}}
{{- with $service.podSelector -}}
{{- $_ := set $target "podSelector" (dict "matchLabels" .) -}}
{{- end -}}
{{- end -}}
{{- $ports := list -}}
{{- range $port := $service.ports -}}
{{- $ports = append $ports (dict "protocol" ($port.protocol | default "TCP") "port" ($port.port | int)) -}}
{{- end -}}
{{- $rules = append $rules (dict "to" (list $target) "ports" $ports) -}}
{{- end -}}
{{- end -}}
{{- toYaml $rules -}}
{{- end -}}
