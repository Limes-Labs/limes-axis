# Deployment Baseline

This page defines the first Kubernetes and Helm deployment baseline for the
Limes Axis open core. It is a self-hostable package for enterprise evaluation,
cluster planning and future hardening. It is not a production certification.

The chart lives in `infra/helm/limes-axis` and currently deploys only the Axis
API and web console. The repository includes local API and web image builds,
while production operators must still supply signed, published images and the
external services that the open core depends on.

## Scope

The baseline covers:

- API deployment and service.
- Web console deployment and service.
- ConfigMap for public-safe runtime configuration.
- Kubernetes Secret reference for sensitive runtime values.
- Example Secret template disabled by default.
- Optional External Secrets Operator `ExternalSecret` template that syncs the
  same runtime Secret name from an operator-managed `SecretStore` or
  `ClusterSecretStore`.
- Optional Kubernetes `Ingress` template for routing web and API hosts, with
  TLS secret references supplied by the operator.
- Optional `HorizontalPodAutoscaler` and `PodDisruptionBudget` templates for
  API and web console workloads.
- Deployment rollout controls for API and web console workloads, including
  `RollingUpdate` strategy values, `revisionHistoryLimit`,
  `terminationGracePeriodSeconds` and optional container `lifecycle`
  pass-through hooks.
- A rollout rehearsal script and runbook for `helm upgrade --install`,
  `kubectl rollout status`, optional API `/ready` polling and `helm rollback`
  against an operator-selected Kubernetes context.
- Service account and pod security context.
- Initial NetworkPolicy for ingress and egress shaping.
- Public-safe install notes and local readiness checks.
- Local API and web Dockerfile baselines.
- GHCR container release workflow with SBOM, keyless signing, provenance
  attestations, build-only checks and a GitHub Environment reviewer protection
  hook for manually approved publish runs.
- Container vulnerability scanning policy baseline for API and web images.
- Vulnerability management baseline with SARIF publication and expiring
  exception policy.

The baseline does not yet cover:

- High availability validation under load.
- Load testing, capacity planning and rollout-drain validation.
- TLS certificate automation and secure cookie/session review.
- Production secret rotation drills, KMS policy review and incident procedures.
- Production backup, restore and disaster recovery.
- S3-compatible object storage with object lock, legal hold operations and
  provider KMS policy.
- Cluster observability, alerting and on-call runbooks.

## Dependencies

Axis remains self-hostable and does not require managed services, but the Helm
chart expects production-grade dependencies to be provided outside the chart:

- external Postgres with `AXIS_POSTGRES_DSN` stored in a Kubernetes Secret.
- TypeDB reachable through `AXIS_TYPEDB_ADDRESS`.
- Temporal OSS reachable through `AXIS_TEMPORAL_ADDRESS`.
- OIDC provider, normally Keycloak or an enterprise IdP, with issuer, audience
  and JWKS URL configured.
- S3-compatible object storage for governed export paths.
- Kubernetes Ingress controller when `ingress.enabled=true`.

The chart does not create Postgres, TypeDB, Temporal, MinIO or Keycloak. The
Docker Compose stack remains the local demo path; Kubernetes production
operators should bring hardened dependencies that match their infrastructure
policy.

## Ingress And TLS

The chart can render a Kubernetes `networking.k8s.io/v1` `Ingress` when
`ingress.enabled=true`. Ingress is disabled by default. When enabled, each host
entry routes paths to either the web console service or the API service by name.
TLS is configured through `ingress.tls[]` entries and references an existing
Kubernetes TLS Secret through `secretName`.

The chart does not install an Ingress controller, cert-manager, DNS records or
certificate issuers. Operators must provision those resources according to
their cluster policy and verify secure cookie/session behavior against the
final public hostnames before production use.

## Availability Controls

The chart can render Kubernetes `autoscaling/v2` `HorizontalPodAutoscaler`
objects and `policy/v1` `PodDisruptionBudget` objects for both the API and web
console. They are disabled by default and can be enabled independently with
`api.autoscaling.enabled`, `web.autoscaling.enabled`, `api.pdb.enabled` and
`web.pdb.enabled`.

When an autoscaler is enabled for a workload, the corresponding Deployment does
not render a fixed `replicas` value; the HPA owns replica count inside the
configured `minReplicas` and `maxReplicas` bounds. PDBs use `minAvailable` and
select the same component labels as the API and web Deployments.

These controls are a chart-level availability baseline. They do not replace
load testing, capacity planning, cluster resource quotas, node failure tests,
upgrade rollback drills or production SLO review.

## Rollout Controls

The API and web Deployments expose per-workload rollout controls. By default,
both workloads use a Kubernetes `RollingUpdate` strategy with
`maxUnavailable: 0`, `maxSurge: 1`, `revisionHistoryLimit: 5` and
`terminationGracePeriodSeconds: 30`. The chart also exposes a container-level
`lifecycle` pass-through for each workload so operators can add pre-stop or
other lifecycle hooks that match their image, ingress and workload-draining
policy.

The default lifecycle value is empty. Axis does not assume a shell, sidecar or
cluster-specific drain endpoint inside the container image. Operators should
configure lifecycle hooks only after validating the deployed image and ingress
behavior, then test rollouts, readiness gates, connection draining, rollback
criteria and interrupted in-flight requests in their target cluster.

## Rollout Rehearsal

The repository includes a real rollout rehearsal tool:

```bash
make deployment-rollout-rehearsal-plan
AXIS_KUBE_CONTEXT=production-eu make deployment-rollout-rehearsal
```

The detailed runbook lives in
[`docs/deployment-rollout-rehearsal.md`](./deployment-rollout-rehearsal.md).
The script is intentionally split into plan and execute modes. Plan mode prints
the exact `helm` and `kubectl` commands. Execute mode runs against the
operator-provided Kubernetes context, waits for API and web Deployment rollout,
can poll an externally reachable API `/ready` URL and can run `helm rollback`
when the rehearsal includes rollback validation.

This is an operational rehearsal baseline. It is not a production
certification and does not replace cluster-specific load, failover,
backup/restore, SSO, secret-rotation or incident-response drills.

## Scheduling Controls

The API and web Deployments expose Kubernetes scheduling pass-through values:
`nodeSelector`, `affinity`, `tolerations` and `topologySpreadConstraints`.
They are empty by default and can be configured independently for each
workload. This lets operators target dedicated node pools, tolerate tainted
nodes, express pod affinity or anti-affinity, and spread replicas across
failure domains such as zones or hosts.

The chart does not infer cluster topology. Operators must set selectors and
`topologySpreadConstraints` that match their cluster labels, capacity model and
availability targets, then verify scheduling behavior during load tests,
rollout drains and node-failure exercises.

The chart also does not install External Secrets Operator or create a
`SecretStore`/`ClusterSecretStore`. When `secrets.externalSecret.enabled=true`,
the chart renders an `ExternalSecret` that targets `secrets.existingSecret`;
cluster operators remain responsible for installing the operator, binding it to
their secret manager and reviewing the underlying KMS, access and rotation
policy.

## Object Storage

Governed connector evidence materializations use the object-store adapter
configured on the API service.

For local demos, keep the default filesystem adapter:

- `AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER=local_filesystem`
- `AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ROOT=.axis/object-store`

For S3-compatible evaluation or production-style deployments, configure:

- `AXIS_CONNECTOR_EXPORT_OBJECT_STORE_ADAPTER=s3_compatible`
- `AXIS_CONNECTOR_EXPORT_S3_ENDPOINT`
- `AXIS_CONNECTOR_EXPORT_S3_REGION`
- `AXIS_CONNECTOR_EXPORT_S3_BUCKET`
- `AXIS_CONNECTOR_EXPORT_S3_SECURE_TRANSPORT=true`
- `AXIS_CONNECTOR_EXPORT_S3_OBJECT_LOCK_ENABLED=true`
- `AXIS_CONNECTOR_EXPORT_S3_RETENTION_MODE=GOVERNANCE` or `COMPLIANCE`
- `AXIS_CONNECTOR_EXPORT_S3_RETENTION_DAYS=<positive integer>`
- `AXIS_CONNECTOR_EXPORT_S3_LEGAL_HOLD_ENABLED=true` when legal hold should be
  applied to written objects.

`AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY` and
`AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY` must come from `secrets.existingSecret`
or an external secret manager integration. They are not rendered into the
ConfigMap and are not returned by readiness or support diagnostics.

The readiness endpoint reports the object-store gate as ready only when the
S3-compatible adapter has endpoint, bucket, credentials, secure transport,
object lock and positive retention days configured. This proves the Axis
adapter is configured to write retained objects; it does not replace customer
bucket provisioning review, KMS policy, restore drills, legal operations or
external compliance review.

## Container Images

The repository includes local container image baselines:

```bash
make container-check
make container-build-api
make container-build-web
```

`services/api/Dockerfile` builds the FastAPI service with `uv`, installs only
production Python dependencies, runs as UID `10001`, exposes port `8000` and
uses the API `/health` route as a container healthcheck.

`apps/web/Dockerfile` builds the Next.js console with `pnpm`, installs
production Node dependencies for runtime, runs as UID `10001`, exposes port
`3000` and uses the web home route as a container healthcheck. The runtime
stage removes the bundled `npm` and `npx` package-manager surface because the
production command does not require them.

These local builds are useful for hardening the Helm path and for evaluation
clusters. They are not image provenance, signing, SBOM publication or registry
release automation.

## Container Release Workflow

The repository includes a real release supply-chain baseline in
`.github/workflows/container-release.yml`.

The workflow builds both public images:

- `ghcr.io/${{ github.repository_owner }}/limes-axis-api`
- `ghcr.io/${{ github.repository_owner }}/limes-axis-web`

It runs on `v*` Git tags and can also be started manually with
`workflow_dispatch`. Tag pushes and default manual runs execute the
`build-images` job only; they do not publish images to GHCR.

Publishing is split into a separate governed path. The
`validate-promotion-evidence` job runs only for a manual run where `push=true`
and checks that the operator supplied a release approval issue, the required
rollback plan issue evidence, a rollback drill identifier and
`rollback_plan_acknowledged=true`. The
gate checks that the approval and rollback issue URLs belong to
`Limes-Labs/limes-axis`, verifies them with `gh issue view`, requires a
non-empty rollback drill id and blocks publication if the rollback plan has not
been explicitly acknowledged.

The `publish-images` job depends on the evidence gate and declares the
`axis-container-release` GitHub Environment. Repository administrators must
configure required reviewers on that environment before production use; the
workflow declaration provides the hook for GitHub Environment reviewer
protection without forcing reviewer approval for build-only tag checks.
Published images use GitHub OIDC for keyless signing through cosign, BuildKit
`sbom: true`, BuildKit `provenance: mode=max`, and GitHub registry-backed build
provenance attestations.

Validate the release workflow contract locally with:

```bash
make container-release-check
```

This baseline is intended to make release artifacts inspectable and
repeatable. It is not a production certification: GitHub environment reviewer
settings, registry retention policy, vulnerability exception lifecycle,
long-term SBOM archival, periodic rollback drill operations and
customer-specific deployment gates still need production hardening.

## Container Vulnerability Scanning

The repository includes a container security workflow in
`.github/workflows/container-security.yml`. It builds the API and web images
from the repository Dockerfiles and scans both with Trivy.

The first blocking policy is intentionally narrow and repeatable:

- scan API and web images on relevant pull requests, pushes to `main` and
  manual runs;
- scan OS and library vulnerabilities;
- block fixed `CRITICAL` vulnerabilities;
- use `ignore-unfixed` so the gate focuses on issues with an available upgrade
  path;
- pinned to the v0.36.0 commit for `aquasecurity/trivy-action`:
  `ed142fd0673e97e23eac54620cfb913e5ce36c25`;
- run Trivy `v0.71.2`.

Validate the workflow contract locally with:

```bash
make container-security-check
```

Run the same critical fixed-vulnerability policy against local images with:

```bash
make container-scan-local
```

The local scan writes machine-readable JSON reports under
`.axis/trivy-reports/`, which is ignored by git with the rest of the local Axis
runtime state.

The workflow also generates `HIGH` and `CRITICAL` vulnerability SARIF reports
for each image and uploads them to GitHub code scanning with
`github/codeql-action/upload-sarif` pinned to
`8aad20d150bbac5944a9f9d289da16a4b0d87c1e`. This requires the workflow-scoped
`security-events: write` permission. SARIF upload is skipped for pull requests
from forks because GitHub does not grant the same code-scanning write capability
to untrusted fork contexts.

The repository tracks vulnerability exceptions in
`.github/vulnerability-exceptions.json`. The first policy requires owner roles,
review tickets, promotion review and exception expiry. `HIGH` exceptions may
last at most 45 days and `CRITICAL` exceptions may last at most 14 days. There
are no approved vulnerability exceptions in the current baseline.

Validate the vulnerability management baseline with:

```bash
make vulnerability-management-check
```

This is a real vulnerability scan gate, but it is not a production
certification. Enterprise hardening still needs GitHub environment reviewer
settings, operational exception review meetings, registry retention, release
rollback criteria and customer-specific deployment gates.

## Runtime Secrets

The chart uses `secrets.existingSecret` for sensitive values. The default name
is `limes-axis-runtime`.

Required keys:

- `AXIS_POSTGRES_DSN`
- `AXIS_TYPEDB_USERNAME`
- `AXIS_TYPEDB_PASSWORD`
- `AXIS_AUDIT_LEDGER_SIGNING_SECRET`
- `AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY`
- `AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY`

Do not put customer secrets in `values.yaml`. Use an external secret manager,
sealed secret workflow or platform-specific KMS integration before production
use. The disabled example Secret uses
`REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE` placeholders so accidental demo
secrets are not shipped as chart defaults.

For clusters that already run External Secrets Operator, enable
`secrets.externalSecret.enabled=true`. The rendered `ExternalSecret` uses
`external-secrets.io/v1`, references `secretStoreRef`, writes to
`secrets.existingSecret`, and maps each Axis runtime key through
`data[].remoteRef`. The placeholder `remoteKey` values in `values.yaml` must be
replaced with the customer's real secret-manager paths before installation.

## Install

Create or sync the runtime Secret before installing the chart:

```bash
kubectl create namespace limes-axis
kubectl -n limes-axis create secret generic limes-axis-runtime \
  --from-literal=AXIS_POSTGRES_DSN='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_USERNAME='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_PASSWORD='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_AUDIT_LEDGER_SIGNING_SECRET='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_CONNECTOR_EXPORT_S3_ACCESS_KEY='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_CONNECTOR_EXPORT_S3_SECRET_KEY='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE'
```

If the cluster uses External Secrets Operator instead, preinstall the operator,
create the appropriate `SecretStore` or `ClusterSecretStore`, then let the
chart render the synchronization object:

```bash
helm upgrade --install limes-axis infra/helm/limes-axis \
  --namespace limes-axis \
  --create-namespace \
  --set secrets.externalSecret.enabled=true \
  --set secrets.externalSecret.secretStoreRef.name=production-secrets \
  --set secrets.externalSecret.secretStoreRef.kind=ClusterSecretStore
```

Install or upgrade the release:

```bash
helm upgrade --install limes-axis infra/helm/limes-axis \
  --namespace limes-axis \
  --create-namespace \
  --set api.image.repository=ghcr.io/limes-labs/limes-axis-api \
  --set api.image.tag=0.1.0 \
  --set web.image.repository=ghcr.io/limes-labs/limes-axis-web \
  --set web.image.tag=0.1.0 \
  --set api.env.AXIS_PUBLIC_BASE_URL=https://axis.example.com \
  --set api.env.AXIS_API_BASE_URL=https://api.axis.example.com \
  --set web.env.NEXT_PUBLIC_AXIS_API_BASE_URL=https://api.axis.example.com \
  --set api.env.AXIS_OIDC_ISSUER=https://keycloak.example.com/realms/axis \
  --set api.env.AXIS_OIDC_JWKS_URL=https://keycloak.example.com/realms/axis/protocol/openid-connect/certs
```

Enable Ingress routing only when the cluster has an Ingress controller and TLS
Secret ready:

```bash
helm upgrade --install limes-axis infra/helm/limes-axis \
  --namespace limes-axis \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.tls[0].secretName=axis-tls \
  --set ingress.tls[0].hosts[0]=axis.example.com \
  --set ingress.tls[0].hosts[1]=api.axis.example.com
```

The repository includes local Dockerfiles, but production image coordinates
should point to images built, scanned, signed and published by the operator or
a future Axis release pipeline.

## Verification

Run the static repository deployment check:

```bash
make deployment-check
make deployment-rollout-rehearsal-plan
make container-check
make container-release-check
make container-security-check
make vulnerability-management-check
```

After a cluster install, verify Kubernetes state and API readiness:

```bash
kubectl -n limes-axis get pods,svc
kubectl -n limes-axis port-forward svc/limes-axis-api 8000:8000
curl http://127.0.0.1:8000/ready
curl http://127.0.0.1:8000/deployment/readiness
```

The readiness endpoint should be shared honestly during enterprise evaluation.
It may report `production_ready=false` until OIDC, audit signing, connector
execution, object storage, customer bucket operations and support operations
are hardened.

## Promotion Gate

Before customer production use, the deployment package must add and verify:

- release approval issue and reviewer settings for production image release.
- registry retention and long-term SBOM archive.
- enforced release promotion approvals and recurring rollback drills.
- operational review cadence for high-severity findings and expiring
  vulnerability exceptions.
- TLS certificate automation, DNS ownership checks and secure cookie/session
  behavior.
- high availability, scheduling/topology, autoscaling and upgrade rollback
  tests, including rollout-drain validation.
- backup, restore and disaster recovery runbooks.
- production secret-manager rotation drills, access reviews and incident
  procedures.
- S3/MinIO bucket-policy review, restore drills and KMS-backed audit signing.
- production observability and incident response runbooks.
- cluster-specific threat review and penetration test scope.

Until those items are complete, this chart is an evaluation and hardening
baseline, not a production-ready enterprise deployment.
