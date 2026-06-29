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
- Service account and pod security context.
- Initial NetworkPolicy for ingress and egress shaping.
- Public-safe install notes and local readiness checks.
- Local API and web Dockerfile baselines.
- GHCR container release workflow with SBOM, keyless signing and provenance
  attestations for tag or manually approved release runs.

The baseline does not yet cover:

- High availability validation under load.
- Horizontal autoscaling and disruption budgets.
- TLS ingress and certificate automation.
- Sealed Secrets, External Secrets Operator or cloud KMS binding.
- Production backup, restore and disaster recovery.
- S3/MinIO WORM retention, legal hold operations and provider KMS policy.
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

The chart does not create Postgres, TypeDB, Temporal, MinIO or Keycloak. The
Docker Compose stack remains the local demo path; Kubernetes production
operators should bring hardened dependencies that match their infrastructure
policy.

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
`3000` and uses the web home route as a container healthcheck.

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
`workflow_dispatch`. Manual runs default to build-only mode; setting the
`push` input to `true` publishes images to GHCR. Published images use GitHub
OIDC for keyless signing through cosign, BuildKit `sbom: true`, BuildKit
`provenance: mode=max`, and GitHub registry-backed build provenance
attestations.

Validate the release workflow contract locally with:

```bash
make container-release-check
```

This baseline is intended to make release artifacts inspectable and
repeatable. It is not a production certification: registry retention policy,
promotion approvals, vulnerability scanning policy, long-term SBOM archival and
customer-specific deployment gates still need production hardening.

## Runtime Secrets

The chart uses `secrets.existingSecret` for sensitive values. The default name
is `limes-axis-runtime`.

Required keys:

- `AXIS_POSTGRES_DSN`
- `AXIS_TYPEDB_USERNAME`
- `AXIS_TYPEDB_PASSWORD`
- `AXIS_AUDIT_LEDGER_SIGNING_SECRET`

Do not put customer secrets in `values.yaml`. Use an external secret manager,
sealed secret workflow or platform-specific KMS integration before production
use. The disabled example Secret uses
`REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE` placeholders so accidental demo
secrets are not shipped as chart defaults.

## Install

Create or sync the runtime Secret before installing the chart:

```bash
kubectl create namespace limes-axis
kubectl -n limes-axis create secret generic limes-axis-runtime \
  --from-literal=AXIS_POSTGRES_DSN='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_USERNAME='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_TYPEDB_PASSWORD='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE' \
  --from-literal=AXIS_AUDIT_LEDGER_SIGNING_SECRET='REPLACE_WITH_EXTERNAL_SECRET_MANAGER_VALUE'
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

The repository includes local Dockerfiles, but production image coordinates
should point to images built, scanned, signed and published by the operator or
a future Axis release pipeline.

## Verification

Run the static repository deployment check:

```bash
make deployment-check
make container-check
make container-release-check
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
execution, object storage, S3/MinIO WORM retention and support operations are
hardened.

## Promotion Gate

Before customer production use, the deployment package must add and verify:

- promotion approval rules for production image release.
- registry retention, vulnerability scanning policy and long-term SBOM archive.
- TLS ingress and secure cookie/session behavior.
- high availability, autoscaling and upgrade rollback tests.
- backup, restore and disaster recovery runbooks.
- External Secrets or equivalent integration.
- S3/MinIO WORM retention and KMS-backed audit signing.
- production observability and incident response runbooks.
- cluster-specific threat review and penetration test scope.

Until those items are complete, this chart is an evaluation and hardening
baseline, not a production-ready enterprise deployment.
