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
- Optional cert-manager ingress-shim annotations for operator-managed TLS
  certificate issuance.
- Optional `HorizontalPodAutoscaler` and `PodDisruptionBudget` templates for
  API and web console workloads.
- Deployment rollout controls for API and web console workloads, including
  `RollingUpdate` strategy values, `revisionHistoryLimit`,
  `terminationGracePeriodSeconds` and optional container `lifecycle`
  pass-through hooks.
- A rollout rehearsal script and runbook for `helm upgrade --install`,
  `kubectl rollout status`, optional API `/ready` polling and `helm rollback`
  against an operator-selected Kubernetes context.
- A HA restart rehearsal script and runbook for sequential API/web
  `kubectl rollout restart`, `kubectl rollout status`,
  `kubectl wait --for=condition=available`, optional HPA/PDB checks, optional
  API `/ready` polling and `helm test`.
- A bounded load rehearsal script and runbook that creates short-lived Fortio
  Kubernetes Jobs, waits for completion, captures `kubectl logs` evidence and
  cleans up Jobs against operator-selected API and web targets.
- A Helm smoke test hook that runs with `helm test` and checks the API `/ready`
  endpoint plus the web console service from inside the cluster.
- A production backup rehearsal plan for in-cluster Postgres `pg_dump` capture
  and `pg_restore --list` restore-catalog validation without printing database
  connection secrets.
- A production restore rehearsal plan for restoring a captured Postgres dump
  into a separately configured isolated restore target without printing target
  connection secrets.
- A TypeDB recovery rehearsal plan that exports the runtime graph with
  `database export` and imports it into a separately configured isolated
  restore target with `database import` without printing TypeDB credentials.
- An object storage recovery rehearsal plan that writes a bounded S3-compatible
  probe object, copies it to a separately configured isolated restore bucket
  with MinIO Client and verifies the restored bytes by checksum without
  printing S3 credentials.
- A Temporal recovery rehearsal plan that uses Temporal CLI from an isolated
  non-root Pod to capture cluster health, namespace metadata, workflow list
  and a replay-compatible workflow history JSON without printing Temporal
  credential material.
- A secret rotation rehearsal plan that compares the active runtime Secret
  with a separately staged Secret, captures redacted fingerprint evidence and
  checks key parity without printing secret values.
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
- Public-safe production support-readiness configuration for SLO response
  targets, escalation channel classes, customer runbook presence, status page
  presence and required incident review.

The baseline does not yet cover:

- Sustained customer-profile high availability validation under load.
- Full load testing, capacity planning and rollout-drain validation.
- TLS certificate issuance operations, DNS ownership checks and secure
  cookie/session review.
- Production secret-manager rotation drills, access reviews, workload restart
  validation, KMS policy review and incident procedures.
- Full production backup, restore and disaster recovery operations across
  Postgres, TypeDB, Temporal persistence and object storage.
- S3-compatible object storage with object lock, legal hold operations and
  provider KMS policy.
- Cluster observability, alerting, global abuse throttling and on-call runbooks.
- Signed customer SLAs, named staffing commitments and customer-specific
  incident operations.

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
- Optional cert-manager installation and issuer when
  `ingress.certManager.enabled=true`.

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

When a cluster already runs cert-manager, operators can set
`ingress.certManager.enabled=true` and provide `issuerName`, `issuerKind` and
`issuerGroup`. The chart then emits ingress-shim annotations so cert-manager can
create a `Certificate` for each configured `ingress.tls[].secretName`. Built-in
`ClusterIssuer` and `Issuer` values use the standard cert-manager annotations;
external issuers also emit issuer kind and issuer group annotations.

The chart does not install an Ingress controller, cert-manager, DNS records or
certificate issuers. Operators must provision those resources according to
their cluster policy and verify DNS ownership, certificate renewal and secure
cookie/session behavior against the final public hostnames before production
use.

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

## HA Restart Rehearsal

The repository includes a real HA restart rehearsal tool:

```bash
make deployment-ha-rehearsal-plan
AXIS_KUBE_CONTEXT=production-eu make deployment-ha-rehearsal
```

The detailed runbook lives in
[`docs/deployment-ha-rehearsal.md`](./deployment-ha-rehearsal.md). The script
is intentionally split into plan and execute modes. Plan mode prints the exact
`kubectl` and `helm test` commands. Execute mode runs against the
operator-provided Kubernetes context, captures workload and pod inventory,
optionally requires HPA and PDB resources, restarts API and web Deployments one
at a time, waits for rollout status and Kubernetes availability, can poll an
externally reachable API `/ready` URL after each restart and can run the Helm
smoke test hook.

This verifies controlled restart mechanics. It is not a load test, node
failover test, zone failover test, production SLO proof or disaster recovery
certification.

## Load Rehearsal

The repository includes a bounded load rehearsal tool:

```bash
make deployment-load-rehearsal-plan
AXIS_KUBE_CONTEXT=production-eu make deployment-load-rehearsal
```

The detailed runbook lives in
[`docs/deployment-load-rehearsal.md`](./deployment-load-rehearsal.md). The
script is intentionally split into plan and execute modes. Plan mode prints the
exact `kubectl create job`, `kubectl wait`, `kubectl logs` and cleanup
commands. Execute mode runs against the operator-provided Kubernetes context
and creates short-lived `fortio` Jobs for the configured targets.

By default, the script targets the in-cluster API `/ready` endpoint and the web
home service URL for the Helm release. Operators can provide explicit
`--target name=url` values to rehearse ingress, service mesh or customer-like
paths.

This verifies bounded Job-based request execution and service reachability. It
is not a sustained capacity plan, autoscaler-tuning proof, node failover test,
zone failover test, denial-of-service test or production SLO certification.

## Helm Smoke Tests

The chart includes an optional `helm test` smoke pod. It uses the pinned
`busybox` image configured under `tests.smoke.image`, runs with a restricted
container security context and checks both in-cluster services:

- `http://<release>-api:<api.service.port>/ready`
- `http://<release>-web:<web.service.port>/`

The hook is enabled by default with `tests.smoke.enabled=true` and is not run
during `helm upgrade --install`. Run it explicitly after an install or during a
rollout rehearsal:

```bash
helm test limes-axis --namespace limes-axis --timeout 10m
```

The chart NetworkPolicy includes a narrow same-release egress rule for the
smoke test path so the hook can reach the API and web pods without opening a
generic egress path. Operators can disable the hook with
`--set tests.smoke.enabled=false` if their cluster provides a separate
post-install validation path.

This test verifies service reachability and basic application readiness from
inside the cluster. It is not a load test, dependency failover test, SSO test,
connector execution test or production certification.

## Production Backup Rehearsal

The repository includes a production backup rehearsal helper for Kubernetes
clusters:

```bash
make deployment-backup-rehearsal-plan
```

The plan creates a short-lived Kubernetes Job that reads
`AXIS_POSTGRES_DSN` from the configured runtime Secret through `envFrom`,
runs `pg_dump "$AXIS_POSTGRES_DSN" --format=custom --no-owner`, validates the
dump catalog with `pg_restore --list`, captures a SHA-256 checksum and copies
`postgres.dump`, `postgres.restore.list` and `postgres.dump.sha256` to a local
evidence directory. The plan prints the Secret reference and Kubernetes
commands, but does not print the DSN value or other secret material. The Job
uses an explicit non-root security context, a short-lived `emptyDir` mounted at
`/backup` and configurable `--run-as-user` / `--run-as-group` values for
Postgres client images that use a UID/GID different from `postgres:16-alpine`.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu make deployment-backup-rehearsal
```

Operators can pass additional script arguments with
`AXIS_PRODUCTION_BACKUP_ARGS`, for example `--namespace`, `--runtime-secret`,
`--backup-id`, `--local-backup-dir`, `--image`, `--timeout`, `--run-as-user`,
`--run-as-group` or `--keep-job`.

This is a backup-capture and restore-catalog rehearsal for the current
Postgres operational store. It is not a full production disaster recovery
procedure: Temporal state policy, object-store retention, RPO/RTO evidence,
offsite retention and customer-specific approval gates remain hardening work.

## Production Restore Rehearsal

The repository also includes a production restore rehearsal helper for
Kubernetes clusters:

```bash
make deployment-restore-rehearsal-plan
```

The plan creates a temporary non-root Pod, copies a local `postgres.dump` and
`postgres.dump.sha256` into an in-cluster `emptyDir`, verifies the checksum,
validates the restore catalog with `pg_restore --list`, restores the dump with
`pg_restore --clean --if-exists --no-owner` and writes local evidence files for
the restore catalog, target probe and calculated checksum.

The restore target must be a separate Kubernetes Secret from the Axis runtime
Secret. It must contain `AXIS_POSTGRES_RESTORE_DSN` and carry the annotation
`limes-axis.io/restore-target=isolated`. The script checks the annotation and
the presence of the restore DSN key without printing the DSN value. The script
also refuses common runtime Secret names such as `limes-axis-runtime` for the
restore target.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu make deployment-restore-rehearsal
```

Operators can pass additional script arguments with
`AXIS_PRODUCTION_RESTORE_ARGS`, for example `--namespace`,
`--restore-target-secret`, `--restore-id`, `--dump-path`, `--checksum-path`,
`--local-evidence-dir`, `--image`, `--timeout`, `--run-as-user`,
`--run-as-group` or `--keep-pod`.

This is an isolated Postgres restore rehearsal for a captured Axis dump. It is
not a full production disaster recovery procedure: it does not restore
Temporal state or object storage, does not validate customer-specific retention
or legal-hold policy and does not establish RPO/RTO commitments.

## TypeDB Recovery Rehearsal

The repository includes a TypeDB recovery rehearsal helper for Kubernetes
clusters:

```bash
make deployment-typedb-recovery-rehearsal-plan
```

The plan creates a temporary non-root Pod using an operator-supplied container
image that includes TypeDB Console. It reads the Axis runtime TypeDB connection
values from the runtime Secret, first verifies `console --help`, runs TypeDB
Console `database export` to write `typedb.schema.typeql` and `typedb.data`,
records `typedb.sha256`, then imports the export into an isolated target using
`database import`.

The runtime Secret must provide `AXIS_TYPEDB_ADDRESS`,
`AXIS_TYPEDB_USERNAME`, `AXIS_TYPEDB_PASSWORD` and `AXIS_TYPEDB_DATABASE`. The
restore target must be a separate Kubernetes Secret from the Axis runtime
Secret. It must provide `AXIS_TYPEDB_RESTORE_ADDRESS`,
`AXIS_TYPEDB_RESTORE_USERNAME`, `AXIS_TYPEDB_RESTORE_PASSWORD` and
`AXIS_TYPEDB_RESTORE_DATABASE`, and it must carry the annotation
`limes-axis.io/typedb-restore-target=isolated`. The script checks the
annotation and required keys without printing connection values or password
material. The restore database should be an isolated, empty target chosen for
the rehearsal.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu \
AXIS_TYPEDB_RECOVERY_IMAGE=registry.example.com/platform/typedb-console:3.11.5 \
make deployment-typedb-recovery-rehearsal
```

`AXIS_TYPEDB_RECOVERY_IMAGE` must point to an image that contains TypeDB
Console for the target TypeDB version. The local TypeDB server image is not
assumed to include Console. Operators can pass additional script arguments with
`AXIS_TYPEDB_RECOVERY_ARGS`, for example `--namespace`, `--runtime-secret`,
`--restore-target-secret`, `--recovery-id`, `--local-evidence-dir`,
`--timeout`, `--run-as-user`, `--run-as-group` or `--keep-pod`. Runtime
environments that intentionally run TypeDB without TLS can set
`AXIS_TYPEDB_TLS_DISABLED=true` or `AXIS_TYPEDB_RESTORE_TLS_DISABLED=true`
inside the relevant Kubernetes Secret.

This is an export/import recovery rehearsal for the Axis TypeDB graph. It is
not a full production disaster recovery procedure: it does not coordinate
write quiescence across API, worker and connector processes, does not restore
Temporal state or object storage, does not establish retention policy, and does
not prove RPO/RTO commitments.

## Temporal Recovery Rehearsal

The repository includes a Temporal recovery rehearsal helper for Kubernetes
clusters:

```bash
make deployment-temporal-recovery-rehearsal-plan
```

The plan creates a temporary non-root Pod using an operator-supplied image that
contains Temporal CLI. It reads `AXIS_TEMPORAL_ADDRESS` and
`AXIS_TEMPORAL_NAMESPACE` from the Axis runtime ConfigMap, reads optional
Temporal auth settings from the runtime Secret and recovery Secret, first
verifies `temporal --help`, then captures:

- `temporal.cluster-health.json` with `operator cluster health`;
- `temporal.namespace.json` with `operator namespace describe`;
- `temporal.namespace-list.json` with `operator namespace list`;
- `temporal.workflow-list.json` with `workflow list`;
- `temporal.workflow-history.json` with `workflow show --output json`;
- `temporal.sha256` with checksums for the captured evidence.

The recovery Secret must be separate from the Axis runtime Secret. It must
provide `AXIS_TEMPORAL_RECOVERY_WORKFLOW_ID`, and it must carry the annotation
`limes-axis.io/temporal-recovery-target=isolated`. It may also provide
`AXIS_TEMPORAL_RECOVERY_RUN_ID`, `AXIS_TEMPORAL_RECOVERY_WORKFLOW_LIMIT`,
`AXIS_TEMPORAL_API_KEY` and `AXIS_TEMPORAL_TLS_ENABLED=true` when the target
Temporal service requires TLS or API-key auth. The script checks required keys
and the isolation annotation without printing API keys or other credential
material.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu \
AXIS_TEMPORAL_RECOVERY_IMAGE=registry.example.com/platform/temporal-cli:stable \
make deployment-temporal-recovery-rehearsal
```

`AXIS_TEMPORAL_RECOVERY_IMAGE` must point to an image that contains Temporal
CLI. Operators can pass additional script arguments with
`AXIS_TEMPORAL_RECOVERY_ARGS`, for example `--namespace`,
`--runtime-config-map`, `--runtime-secret`, `--recovery-secret`,
`--recovery-id`, `--local-evidence-dir`, `--timeout`, `--run-as-user`,
`--run-as-group` or `--keep-pod`.

This is a bounded read-only recovery evidence probe for Temporal. It proves
that an isolated operator path can reach the configured Temporal namespace,
capture replay-compatible workflow history for a selected workflow and produce
checksummed evidence. It does not restore Temporal persistence, does not replay
workflow code, does not validate history archival, does not coordinate
quiescence and does not establish RPO/RTO commitments.

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

## Object Storage Recovery Rehearsal

The repository includes an object storage recovery rehearsal helper for
S3-compatible deployments:

```bash
make deployment-object-storage-recovery-rehearsal-plan
```

The plan creates a temporary non-root Pod using an operator-supplied image that
contains MinIO Client. It reads source endpoint and bucket settings from the
Axis runtime ConfigMap, reads source credentials from the Axis runtime Secret,
and reads the isolated restore endpoint, bucket and credentials from a separate
restore target Secret. The script first runs a MinIO Client preflight, then
uses `mc alias set`, writes a small recovery probe object to the source bucket,
uses `mc cp` to copy that object into the isolated restore bucket, uses
`mc cat` to read the restored object back, and compares the restored checksum
with the original `object-store.sha256`.

The restore target Secret must be separate from the Axis runtime Secret. It
must provide `AXIS_CONNECTOR_EXPORT_S3_RESTORE_ENDPOINT`,
`AXIS_CONNECTOR_EXPORT_S3_RESTORE_BUCKET`,
`AXIS_CONNECTOR_EXPORT_S3_RESTORE_ACCESS_KEY` and
`AXIS_CONNECTOR_EXPORT_S3_RESTORE_SECRET_KEY`, and it must carry the annotation
`limes-axis.io/object-store-restore-target=isolated`. The script checks the
annotation and required keys without printing access keys or secret keys.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu \
AXIS_OBJECT_STORAGE_RECOVERY_IMAGE=registry.example.com/platform/minio-mc:stable \
make deployment-object-storage-recovery-rehearsal
```

`AXIS_OBJECT_STORAGE_RECOVERY_IMAGE` must point to an image that contains MinIO
Client (`mc` or `mcli`). Operators can pass additional script arguments with
`AXIS_OBJECT_STORAGE_RECOVERY_ARGS`, for example `--namespace`,
`--runtime-config-map`, `--runtime-secret`, `--restore-target-secret`,
`--recovery-id`, `--probe-prefix`, `--local-evidence-dir`, `--timeout`,
`--run-as-user`, `--run-as-group` or `--keep-pod`.

This is a bounded object storage recovery probe for governed Axis evidence. It
does not mirror a full bucket, does not validate provider-specific KMS,
does not review customer bucket policies, does not prove legal-hold operations
and does not establish RPO/RTO commitments. The probe intentionally writes a
small object under the configured probe prefix so the recovery path exercises a
real source-to-isolated-target copy instead of a dry-run-only plan.

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
- `AXIS_OIDC_CLIENT_SECRET`
- `AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET`
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

## OIDC Authorization-Code Session

Axis supports an API-owned OIDC authorization-code entrypoint for browser SSO:

- `GET /identity/oidc/authorize` creates a PKCE authorization request and
  redirects to the configured provider.
- `GET /identity/oidc/callback` verifies the state cookie, exchanges the code
  at the token endpoint and sets an HTTP-only Axis session cookie.
- `GET /identity/oidc/logout` revokes the local Axis browser session, clears
  the Axis cookie and redirects the browser to the configured OIDC end-session
  endpoint.
- `GET /identity/oidc/onboarding` returns a public-safe IdP onboarding report
  with the configured issuer, discovery URL, OIDC endpoints, exact redirect
  URIs, post-logout redirect URIs, scopes, claim mappings, recommended IdP
  controls and remaining readiness action items.
- `GET /identity/session` validates the signed Axis session cookie and returns
  only public-safe actor, tenant, scope and posture metadata.
- `POST /identity/session/logout` revokes the persisted Axis browser session,
  writes audit evidence and clears the browser cookie without a federated IdP
  redirect.

Configure non-sensitive client and endpoint values in the chart ConfigMap:

- `AXIS_OIDC_CLIENT_ID`
- `AXIS_OIDC_AUTHORIZATION_URL`
- `AXIS_OIDC_TOKEN_URL`
- `AXIS_OIDC_REDIRECT_URI`
- `AXIS_OIDC_END_SESSION_URL`
- `AXIS_OIDC_POST_LOGOUT_REDIRECT_URI`
- `AXIS_OIDC_SCOPES`
- `AXIS_OIDC_SESSION_COOKIE_SECURE=true`

Keep `AXIS_OIDC_CLIENT_SECRET` and
`AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET` in `secrets.existingSecret` or an
external secret manager. The callback does not return token material to the web
console. The Axis session cookie stores only API-owned actor, tenant, scope,
expiry and session-id claims; the `oidc_browser_sessions` table stores only a
keyed session-id hash plus actor, tenant, scopes, expiry and revocation
metadata, providing server-side session revocation without storing provider
tokens. The federated logout redirect uses `client_id` and
`post_logout_redirect_uri`; Axis does not persist or forward `id_token_hint`,
access tokens or refresh tokens. The IdP onboarding report never returns
confidential client material, cookie-signing material, provider tokens or raw
JWKS material. Refresh-token rotation and production SSO operations runbooks
remain Enterprise hardening work.

## API Rate Limiting

Axis includes configurable in-process API rate limiting for public and sensitive
routes. It is disabled by default for local demos and enabled in the Helm
production values for:

- `GET /identity/oidc/authorize`
- `GET /identity/oidc/callback`
- `GET /identity/oidc/logout`
- `POST /identity/session/logout`
- `GET /deployment/readiness`
- `GET /support/diagnostics`

Configure the limiter with:

- `AXIS_API_RATE_LIMIT_ENABLED`
- `AXIS_API_RATE_LIMIT_REQUESTS`
- `AXIS_API_RATE_LIMIT_WINDOW_SECONDS`
- `AXIS_API_RATE_LIMIT_PATHS`

When a client exceeds the configured budget, the API returns `429` with
`Retry-After`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` and
`X-RateLimit-Reset`. The deployment readiness endpoint reports
`api_rate_limiting` as a production blocker when the limiter is not enabled.

This is a self-hostable baseline, not a complete global abuse-control system.
For multi-replica or internet-facing production deployments, operators should
pair it with ingress, gateway or edge-level throttling, alerting and incident
runbooks.

## Support Readiness Configuration

The chart exposes public-safe support model settings used by
`/support/diagnostics`:

- `AXIS_SUPPORT_MODEL_ENABLED`
- `AXIS_SUPPORT_COVERAGE`
- `AXIS_SUPPORT_S1_RESPONSE_MINUTES`
- `AXIS_SUPPORT_S2_RESPONSE_MINUTES`
- `AXIS_SUPPORT_S3_RESPONSE_MINUTES`
- `AXIS_SUPPORT_S4_RESPONSE_MINUTES`
- `AXIS_SUPPORT_ESCALATION_CHANNELS`
- `AXIS_SUPPORT_CUSTOMER_RUNBOOK_URL`
- `AXIS_SUPPORT_STATUS_PAGE_URL`
- `AXIS_SUPPORT_INCIDENT_REVIEW_REQUIRED`

The diagnostics endpoint returns support readiness booleans, response target
minutes and escalation channel classes. It does not echo customer runbook URLs,
status page URLs or personal contact details. `production_support_ready=true`
requires production deployment readiness plus a configured `24x7` support
model, positive ordered S1-S4 response targets, at least two escalation channel
classes, HTTPS runbook/status-page configuration and required incident review.

This is a readiness contract for operators and design partners. It is not a
signed SLA, staffing commitment or compliance attestation.

## Secret Rotation Rehearsal

The repository includes a Kubernetes secret rotation rehearsal helper:

```bash
make deployment-secret-rotation-rehearsal-plan
```

The plan creates a temporary non-root Pod that mounts the active runtime Secret
read-only at `/rotation/active`, mounts a separately staged Secret read-only at
`/rotation/staged`, compares required Axis secret keys with `cmp -s`, records
redacted key status in `secret-rotation.keys`, records SHA-256 fingerprints in
`secret-rotation.sha256` and writes `secret-rotation.summary.json`. The helper
does not use `envFrom`, so secret values are not placed into process
environment variables, and the plan does not print raw secret values.

The staged Secret must be separate from the active runtime Secret and must
carry `limes-axis.io/secret-rotation-target=staged`. Both Secrets must contain
the required runtime keys listed above. By default, execution fails if no
required key differs between active and staged Secrets; operators can pass
`--allow-unchanged` through `AXIS_SECRET_ROTATION_ARGS` only for dry validation
of key parity.

To execute against a selected cluster context:

```bash
AXIS_KUBE_CONTEXT=prod-eu \
AXIS_SECRET_ROTATION_IMAGE=registry.example.com/platform/busybox-coreutils:stable \
make deployment-secret-rotation-rehearsal
```

`AXIS_SECRET_ROTATION_IMAGE` must point to an image that includes `sh`, `cmp`
and `sha256sum`. Operators can pass additional script arguments with
`AXIS_SECRET_ROTATION_ARGS`, for example `--namespace`, `--active-secret`,
`--staged-secret`, `--rotation-id`, `--local-evidence-dir`, `--timeout`,
`--run-as-user`, `--run-as-group`, `--allow-unchanged` or `--keep-pod`.

This is a rotation readiness rehearsal, not an automatic production rotation.
It does not update the active Secret, does not restart workloads, does not
validate the upstream secret manager or KMS policy and does not replace access
review, rollback, incident-response or customer approval procedures. Treat the
fingerprint evidence as operator-confidential even though it does not contain
raw secret values.

## Install

Create or sync the runtime Secret before installing the chart:

```bash
kubectl create namespace limes-axis
kubectl -n limes-axis create secret generic limes-axis-runtime \
  --from-literal=AXIS_POSTGRES_DSN='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_USERNAME='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_PASSWORD='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_AUDIT_LEDGER_SIGNING_SECRET='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_OIDC_CLIENT_SECRET='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_OIDC_SESSION_COOKIE_SIGNING_SECRET='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
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
  --set api.env.AXIS_OIDC_JWKS_URL=https://keycloak.example.com/realms/axis/protocol/openid-connect/certs \
  --set api.env.AXIS_OIDC_CLIENT_ID=limes-axis-web \
  --set api.env.AXIS_OIDC_AUTHORIZATION_URL=https://keycloak.example.com/realms/axis/protocol/openid-connect/auth \
  --set api.env.AXIS_OIDC_TOKEN_URL=https://keycloak.example.com/realms/axis/protocol/openid-connect/token \
  --set api.env.AXIS_OIDC_REDIRECT_URI=https://api.axis.example.com/identity/oidc/callback \
  --set api.env.AXIS_OIDC_END_SESSION_URL=https://keycloak.example.com/realms/axis/protocol/openid-connect/logout \
  --set api.env.AXIS_OIDC_POST_LOGOUT_REDIRECT_URI=https://axis.example.com/signed-out \
  --set api.env.AXIS_OIDC_SESSION_COOKIE_SECURE=true
```

Enable Ingress routing only when the cluster has an Ingress controller and TLS
Secret ready:

```bash
helm upgrade --install limes-axis infra/helm/limes-axis \
  --namespace limes-axis \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set 'ingress.tls[0].secretName=axis-tls' \
  --set 'ingress.tls[0].hosts[0]=axis.example.com' \
  --set 'ingress.tls[0].hosts[1]=api.axis.example.com'
```

When cert-manager is already installed, the chart can request certificate
issuance through ingress-shim annotations while still referencing the same TLS
Secret:

```bash
helm upgrade --install limes-axis infra/helm/limes-axis \
  --namespace limes-axis \
  --set ingress.enabled=true \
  --set ingress.className=nginx \
  --set ingress.certManager.enabled=true \
  --set ingress.certManager.issuerName=letsencrypt-prod \
  --set ingress.certManager.issuerKind=ClusterIssuer \
  --set 'ingress.tls[0].secretName=axis-tls' \
  --set 'ingress.tls[0].hosts[0]=axis.example.com' \
  --set 'ingress.tls[0].hosts[1]=api.axis.example.com'
```

The repository includes local Dockerfiles, but production image coordinates
should point to images built, scanned, signed and published by the operator or
a future Axis release pipeline.

## Verification

Run the static repository deployment check:

```bash
make deployment-check
make deployment-rollout-rehearsal-plan
make deployment-backup-rehearsal-plan
make deployment-restore-rehearsal-plan
make deployment-typedb-recovery-rehearsal-plan
make deployment-object-storage-recovery-rehearsal-plan
make deployment-temporal-recovery-rehearsal-plan
make deployment-secret-rotation-rehearsal-plan
make deployment-ha-rehearsal-plan
make deployment-load-rehearsal-plan
helm test limes-axis --namespace limes-axis --timeout 10m
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
It may report `production_ready=false` until OIDC, rate limiting, audit signing,
connector execution, object storage, customer bucket operations and support
operations are hardened.

## Promotion Gate

Before customer production use, the deployment package must add and verify:

- release approval issue and reviewer settings for production image release.
- registry retention and long-term SBOM archive.
- enforced release promotion approvals and recurring rollback drills.
- operational review cadence for high-severity findings and expiring
  vulnerability exceptions.
- cert-manager issuer policy, DNS ownership checks, certificate renewal
  evidence and secure cookie/session behavior.
- high availability, scheduling/topology, autoscaling and upgrade rollback
  tests, including rollout-drain validation.
- backup restore drills against isolated Postgres, TypeDB and object-storage
  targets plus Temporal namespace/history evidence, disaster recovery runbooks
  and RPO/RTO evidence.
- production secret-manager rotation drills, access reviews, workload restart
  validation and incident procedures.
- S3/MinIO bucket-policy review, restore drills and KMS-backed audit signing.
- global abuse throttling, production observability and incident response
  runbooks.
- cluster-specific threat review and penetration test scope.

Until those items are complete, this chart is an evaluation and hardening
baseline, not a production-ready enterprise deployment.
