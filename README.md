# Limes Axis

The sovereign AI control plane for European operations.

Limes Axis is an open-source, self-hostable foundation for governing enterprise
data, workflows, humans and AI agents in one operational control plane.

It is not another chatbot, dashboard or single-purpose agent framework. Axis is
designed to sit above existing systems of record, model the organization as an
operational ontology, and let humans and AI agents act through typed,
permissioned, auditable workflows.

## What Axis Is For

European organizations increasingly want AI inside real operations, but not at
the cost of losing control over data, approvals, audit trails or deployment.
Axis is built around a few core ideas:

- integrate above existing ERP, CRM, MES, databases, documents and internal tools;
- model operational context through an ontology;
- give humans, services and AI agents explicit identities and permissions;
- route agent actions through typed schemas, policy checks and approval gates;
- keep every important read, proposal, approval and action auditable;
- support SaaS, dedicated, private-cloud and on-prem deployment paths;
- avoid required managed-service dependencies for the open-source core.

The first reference demo will use a realistic operations cockpit for
manufacturing, but Axis is designed as a platform for European operations more
generally.

## Current Status

Axis is in the Platform Foundation track. The repository now includes the
monorepo structure, self-hosted local runtime, FastAPI foundation, Postgres
migration baseline, TypeDB ontology boundary, workflow runtime port, Temporal
adapter, typed action registry, model egress guard, permission primitives and a
Next.js governance console shell. Foundation hardening adds API readiness,
generated OpenAPI checks, opt-in runtime integration tests, API status in the
console and Playwright smoke tests in CI. The first Platform slice adds a
manufacturing overview reference for the governance console overview, now read
from a persisted tenant-scoped bootstrap record instead of browser fallback or
runtime seed code. The ontology slice adds a persisted, read-only manufacturing
graph for typed nodes, source-system links, relationship mapping, permission
scopes and entity detail pages. The
approval slice adds an API-owned approval inbox with evidence, risk review,
decision options and local audit preview, now read from a persisted
tenant-scoped bootstrap record for the listing and decision validation paths.
The workflow slice adds a read-only runtime console for workflow state, pending
signals and history preview. The
audit slice adds an explorer for reference and persisted ledger events, filters
and redacted payload previews. The agent registry slice adds a read-only
governed agent view with autonomy boundaries, required permissions, model egress
posture, proposals, workflow links and approval references. The action registry slice
adds a typed action catalog with schemas, risk levels, approval modes,
permissions, guardrails, workflow bindings, dry-run payload previews and
API-backed action run creation with idempotency enforcement. The
model routing slice adds read-only route telemetry, provider boundaries, blocked
egress visibility, estimated token/cost telemetry and audit evidence. The
persistence foundation adds Postgres schema and repository methods for approval
records, action runs and append-only audit events. The approval persistence
slice adds an API-backed decision endpoint that records approval decisions and
audit events. The approval console persistence slice submits reviewer decisions
to that endpoint and reports API persistence errors instead of creating local
decision previews when the console runs standalone. The approval permission slice enforces the
required demo approval scope before decision persistence and returns a 403 when
the actor scopes are insufficient. The workflow signal slice sends approval
decisions through the Axis workflow runtime port to Temporal when the runtime is
available, and records an explicit degraded status when it is not. The action
run slice records typed dry-run/proposal requests from action payloads, enforces
idempotency keys and appends action audit events without enabling live connector
execution. The action workflow signal slice sends approval-gated action payloads
through the workflow runtime adapter after persistence, while preserving
explicit degraded status when the runtime is unavailable. The OIDC actor-binding
slice validates bearer tokens against configurable OIDC/JWKS settings, derives
tenant, actor and scopes from token claims, binds approval and action mutation
requests to the authenticated principal when present or required, and rejects
actor impersonation before persistence. The relationship permission slice uses
ontology relationship scopes to protect authenticated entity detail reads and
to reject action payloads that reference cross-domain ontology resources without
the required relationship scope. The governance console session bridge lets a
user attach a bearer token for local OIDC-backed API calls, so approval submits,
action run requests and ontology entity detail reads can exercise the same
token-bound API paths without a full production login flow. Ontology graph list
reads now pass through an Axis query runtime boundary that can filter returned
relationships by OIDC-derived scopes and can be switched from the deferred
reference runtime to a TypeDB read boundary independently from graph mutations.
The API also exposes a public-safe OIDC readiness report at
`/identity/oidc/readiness`, and `/ready` includes a short identity summary, so
demo and enterprise evaluation sessions can distinguish local OIDC demos from a
profile configured for enterprise SSO without exposing tokens, passwords or raw
JWKS material. The browser SSO callback requires an OIDC `openid` authorization
scope, validates the provider `id_token` signature, issuer, expiry, client
audience, authorized party when present, login nonce and cross-token subject
binding before creating the Axis HTTP-only session cookie, while still avoiding
provider token persistence. `/deployment/readiness` adds a wider public-safe
deployment posture report for
identity, external model egress, live connector execution, audit signing and
object-store readiness. It is a gate for evaluation and hardening work, not a
production certification. `/support/diagnostics` provides a public-safe support
bundle for design-partner triage and demo operations, including support
blockers and links to the relevant runbooks without exposing sensitive runtime
material. The `/settings` console reads those readiness, identity, deployment
and support contracts directly from the API and shows an API-required state
instead of browser-local settings fallback records when they are unavailable.
The audit query slice reads persisted `audit_events` through a tenant-scoped API
endpoint and the web console now requires API-backed audit/export records
instead of constructing browser-local bundles. The audit retention/export slice adds a demo
JSON export bundle with manifest, checksum, redacted event payload previews,
retention-window enforcement and a deterministic hash-chain integrity proof.
When OIDC is present or required, persisted audit reads, exports, retention
deletion and legal-hold administration derive tenant, actor and scopes from the
verified principal rather than trusting request-body identity fields.
The platform policy engine foundation adds tenant-scoped policies with typed
rule conditions, append-only idempotent revisions, a deterministic dry-run
evaluation endpoint and enforcement on action run creation: a matching deny
policy rejects the run with `POLICY_VIOLATION` evidence and a matching
require-approval policy forces the run into the existing approval-gated path.
The workflow persistence slice adds Postgres-backed workflow runs and timeline
events, with the workflow console preferring persisted state when records
exist. The replay/simulation foundation derives public-safe replay artifacts
from workflow history and audit events, adds governed policy-set version diff
previews over historical events, and exposes a read-only `/simulation` console
for policy preview inspection. Replay outputs can now be persisted as governed
audit artifacts with `simulation.replay_output.persisted` evidence, retention
metadata and idempotency protection. Replay queries now enforce retention-aware
windows before returning timeline, audit and persisted output records, with a
legal-hold bypass for governance review.

The web console runtime libraries no longer export browser-local fallback seed
records, including the connector console records; those pages are API-required
and protected by a regression test that blocks reintroducing default runtime
seed records.

## Demo Environment

Use [`docs/demo-readiness.md`](./docs/demo-readiness.md) for the repeatable SME
and enterprise evaluation demo runbook. The demo path uses the local
self-hosted stack, Alembic migrations, Axis API routes and API-required console
pages. Static checks are available with `make demo-check`; once the API and web
console are running, `make demo-check-live` verifies the live endpoints,
browser no-store CORS for the dev and Playwright demo origins, OIDC readiness,
deployment readiness, support diagnostics and the persisted manufacturing
operations snapshot used by the overview cockpit.
Use [`docs/support-operations.md`](./docs/support-operations.md) for the
current support and operations baseline for demo and design-partner evaluation
environments. It is not a production support contract or SLA.
Use [`docs/backup-restore.md`](./docs/backup-restore.md) to plan, capture and
restore the local Docker Compose demo state with `pg_dump`, MinIO and TypeDB
volume archives and checksum manifests. This is a repeatable demo runbook, not
a production disaster recovery claim.
Use [`docs/deployment.md`](./docs/deployment.md) and `make deployment-check`
for the first Kubernetes/Helm deployment baseline. The chart in
`infra/helm/limes-axis` deploys the API and web console around operator-supplied
images and externally managed Postgres, TypeDB, Temporal, OIDC and object-store
dependencies. It is an evaluation and hardening baseline, not a production
certification. Use `make container-check`, `make container-build-api` and
`make container-build-web` for the first local API/web container image build
baseline; image provenance, signing and registry release automation remain
Enterprise hardening work. Use `make container-release-check` for the first
GHCR release workflow baseline: it verifies the tag/manual build path, manual
publish evidence gate, keyless signing, SBOM and provenance boundaries before
future release runs. Image publication now requires a release approval issue,
a rollback plan issue, a rollback drill id and an explicit rollback-plan
acknowledgement, then runs through the `axis-container-release` GitHub
Environment so repository admins can enforce reviewer protection on publish
runs without blocking build-only tag checks.
Use `make container-security-check` for the container vulnerability scanning
policy baseline and `make container-scan-local` to run the same Trivy
CRITICAL/fixed-vulnerability gate against local API and web images, with JSON
reports written under `.axis/trivy-reports/`. Use
`make vulnerability-management-check` for the SARIF/code-scanning and
vulnerability exceptions baseline: the workflow publishes HIGH/CRITICAL SARIF
for API and web images, and `.github/vulnerability-exceptions.json` keeps
exception expiry, owner-role and promotion-review rules explicit.
Use [`docs/threat-model.md`](./docs/threat-model.md) and `make security-check`
for the current repository-grounded security review baseline. It covers assets,
trust boundaries, abuse paths, existing controls and open enterprise hardening
risks; it is not a production certification.
The manufacturing overview, workflow console, approval inbox, audit explorer,
model routing, ontology graph/detail, connector registry, agent registry and
action registry API reference surfaces now read tenant-scoped
`demo_reference_records` bootstrap rows and return explicit API errors when
those records are missing or invalid. Approval decisions and action runs
validate against those persisted reference records before writing operational
state; action runs also derive ontology relationship scopes from the persisted
ontology reference. The workflow console, approval inbox, audit explorer, agent
registry, action registry and ontology reference runtime factories have also
been removed from the API module; tests validate the Alembic bootstrap payloads directly.
Remaining API-owned reference
records are tracked for migration to persisted, tenant-scoped bootstrap
records. The model routing reference runtime factory has also been removed;
tests validate the Alembic bootstrap payload directly while live provider
routing remains out of scope.

The connector foundation adds a
public-safe connector manifest registry, a preview-only manufacturing file/CSV
connector and a `/connectors` console for schema mapping, permissions, runtime
boundaries, tenant-scoped preview configuration and redacted ontology proposal
previews without enabling live sync or connector mutation. The connector
registry runtime factory has been removed from the API module; the public
registry reference is loaded from the persisted bootstrap payload. Connector
preview endpoints resolve manifests, schema fields, runtime row limits and
public-safe sample rows from that persisted connector registry reference before
returning redacted preview output. Connector configuration writes resolve
manifests from the persisted connector registry reference and require the
tenant-scoped manifest to be `active_preview` before storing runtime boundary
metadata, and credential handle creation uses the same persisted registry
before storing external secret reference metadata and requires `active_preview`
before writing credential handle metadata or audit evidence. Credential lease
requests also require `active_preview` before lease runtime, metadata or audit
evidence can run. Ontology proposal writes also resolve connector runtime
boundary metadata from that persisted registry and require `active_preview`
before recording proposal audit evidence,
connector run creation uses it and requires `active_preview` before storing
run/audit runtime boundary metadata, and manual import request creation also
requires `active_preview` before writing approval-gated import audit evidence.
Ontology promotion execution requires the same `active_preview` manifest before
the controlled mutation adapter or promotion/audit writes can run. Promotion
policy authoring, enablement and revision paths also validate connector ids
against the persisted registry reference before writing policy/audit evidence,
and promotion policy set activation/replacement/rollback uses it before writing
set/audit evidence.
The external DB preview slice adds a metadata-only Postgres operational mirror manifest and
`/demo/manufacturing/connectors/external-db/preview`, using profile ids and
credential handles while blocking raw DSNs, SQL text and live queries.
Persisted connector manifests can now be registered tenant-scoped with
`connector.manifest.registered` audit evidence without enabling live sync. Draft connector
promotion policies can now be revised append-only with idempotency evidence,
while enabled required policies remain immutable until a governed policy-set
transition adopts a future version. The credential handle slice adds
metadata-only external secret references and rotation history for connector
credentials, while still refusing to store raw credential values. Credential
leases can now be requested, renewed and revoked with Vault/KMS policy metadata,
permission decisions and adapter evidence, without returning secret material.
Lease requests require a tenant-scoped connector manifest in `active_preview`;
the runtime is deferred by default and can switch to the self-hosted Vault/KMS
adapter with `AXIS_CREDENTIAL_LEASE_EXECUTION_ENABLED=true`.
It can also use provider-specific Vault/KMS adapter profiles with
`AXIS_CREDENTIAL_LEASE_PROVIDER_ADAPTERS_ENABLED=true`; those profiles validate
HashiCorp Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, KMS
and local env references without reading or returning secret material.
Credential lease registry reads now write `connector.credential_leases_read`
audit evidence and report lease evidence invariants when a lease is missing an
audit event, references a missing or mismatched ledger event, or carries
evidence that says secret material was accessed.
The connector run record slice adds metadata-only run records linked to
append-only audit events, and governed connector dry-runs now pass through a
deferred execution adapter that writes `connector.run.execution_deferred`
evidence without starting live sync or retrieving credential material. Scheduled
sync plans can also be recorded through run records with
`connector.run.sync_scheduled` audit evidence and a deferred scheduler adapter,
still without starting external sync. Scheduled plans can now be dispatch-claimed
with `connector.run.sync_dispatch_deferred` evidence, idempotency replay and a
deferred dispatch adapter, still without connector egress. Dispatch-claimed
plans can now receive a sync execution attempt through a deferred execution
adapter, or through the self-hosted demo executor when
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED=true`; both paths keep raw credentials,
external egress and graph mutation out of the default boundary. External DB sync
can opt into the Postgres profile adapter boundary with
`AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED=true`, returning profile/table/count
evidence without raw connection strings or credential material. Live-query
requests first pass through
`AXIS_EXTERNAL_DB_LIVE_QUERY_PREFLIGHT_ENABLED=true`, which can mark policy
gates as passed only when the self-hosted egress policy boundary validates a
persisted tenant-scoped connector egress policy for the connector profile and
the run uses a lease-scoped secret reference. A separate opt-in,
`AXIS_EXTERNAL_DB_LIVE_QUERY_EXECUTION_ENABLED=true`, can execute a bounded
read-only Postgres live read only when the connector manifest is `active_live`,
the run requests `live_query_execute=true`, the configured profile/schema/table
match the run, requested columns are omitted or allowlisted, the private
endpoint reference and endpoint-target hash bind the secret DSN to the persisted
egress policy, and all preflight gates pass. The live-read path persists counts,
public-safe profile/checkpoint evidence and query status only: no DSNs, SQL
text, row payloads, credential material or graph mutations are stored or
returned. The passed preflight records redacted egress policy evidence from
persisted policy records, private-endpoint evidence, endpoint-target hash
evidence, credential lease evidence and secret reference resolver evidence from
the validated lease result. Unknown,
unpersisted or unapproved egress policies are blocked before secret retrieval is
considered; missing lease references and lease evidence that indicates secret
material was returned are also blocked. The resolver remains reference-only and
does not return credential material.
Egress policy registry reads now write `connector.egress_policies_read` audit
evidence and report policy evidence invariants when a policy is missing audit
evidence, references an unresolved or mismatched ledger event, or carries
evidence that says an external query or credential material access started.
Sync execution attempts now also persist tenant-scoped
`connector_sync_checkpoints` rows with public-safe cursor/result evidence so
future provider adapters have a real retry/checkpoint boundary without storing
raw credentials or running live queries by default. Those checkpoints are
queryable through `/demo/manufacturing/connectors/runs/checkpoints` with
tenant, connector, run, status, `created_after`, `created_before` and limit
filters. Reads require `connectors:sync:checkpoint:read`, and the `/connectors`
console passes that scope before showing checkpoints per selected connector
when the Axis API is available. Invalid time windows are rejected before
checkpoint storage reads. Valid reads append
`connector.run.sync_checkpoints_read` audit evidence with public-safe filters,
counts and checkpoint ids only.
Worker-safe checkpoint claims are also persisted through
`/demo/manufacturing/connectors/runs/checkpoints/{checkpoint_id}/claims`.
Claims require `connectors:sync:checkpoint:claim`, create a lease-style record
with append-only `connector.run.sync_checkpoint_claimed` audit evidence and do
not start external sync or return secret material. A second unexpired active
claim for the same checkpoint is rejected with 409 before duplicate audit or
worker ownership evidence is written. Expired claims are marked `expired` with
`connector.run.sync_checkpoint_claim_expired` before replacement ownership is
created. Claim records are queryable through
`/demo/manufacturing/connectors/runs/checkpoints/claims` with tenant, connector,
run, checkpoint, worker, status, `created_after`, `created_before`, cursor and
limit filters. Invalid time windows are rejected before storage reads. Reads
return `has_more` and `next_cursor` for stable cursor-based pagination. Reads require
`connectors:sync:checkpoint:claim:read` and append
`connector.run.sync_checkpoint_claims_read` audit evidence with filters,
pagination metadata, counts, claim evidence invariant count and claim ids only.
The registry reports public-safe `claim_evidence_invariants` for missing,
unresolved, mismatched or unsafe claim audit evidence. The `/connectors` console
requests the same registry with that read scope and renders worker ownership,
lease, renewal/release, invariant status and secret-material evidence for claims
attached to the selected connector checkpoints. Dedicated renewal/release endpoints extend or
close the same persisted claim with separate scopes and audit evidence.
External DB live-query preflight now requires an active checkpoint claim owned
by the executing worker before the provider-specific runtime boundary is
called. When `live_query_requested=true`, `execute-sync` must provide
`checkpoint_claim_id` so Axis binds the preflight to one active, unexpired
worker lease for the same connector and run. The claim must be backed by
`connector.run.sync_checkpoint_claimed` audit evidence that resolves in the
tenant-scoped append-only audit ledger for the same connector, run,
checkpoint, claim and worker, with worker-lease-only payload and eligible
persisted checkpoint evidence backed by `connector.run.sync_execution_preflight_passed`
audit and its evidence ref. The referenced audit id must resolve to a tenant-scoped
append-only audit event for the same connector/run/checkpoint with public-safe audit
payload before provider runtime entry, and that target preflight checkpoint
result evidence must keep `external_query_started=false`,
`credential_material_returned=false` and `graph_mutation_started=false`. The
target claim result must also stay
worker-lease-only with `external_sync_started=false`,
`secret_material_returned=false` and `worker_claim_only=true`; valid preflights
include public-safe claim evidence in the sync result.
The checkpoint registry reports public-safe `evidence_invariants` when a
persisted checkpoint has missing, unresolved, mismatched or unsafe audit
evidence. Sync execution audit payloads include the generated checkpoint id so
new checkpoint records can satisfy the same invariant contract.
The connector ontology proposal slice persists preview-derived proposals for review
with `connector.ontology_proposals.recorded` audit events. The manual import request
slice records approval, workflow and idempotency gates for proposal import
requests with `connector.manual_import.requested` audit events after resolving
connector runtime boundary metadata from the persisted registry reference.
Missing or invalid registry references fail before any manual import row or
audit event is written. Manual import decisions now record approval outcomes,
workflow signal evidence and
`connector.manual_import.decision_recorded` audit events. Approved proposals can
now be promoted through a controlled TypeDB ontology mutation boundary with
`connector.ontology_promotion.applied` audit evidence, while still avoiding
connector execution and external sync; this promotion path now also requires a
tenant-scoped connector manifest in `active_preview` before the ontology
mutation adapter is called. Connector promotion policies can now be
authored as tenant-scoped governance metadata with
`connector.promotion_policy.authored` audit evidence and enabled through a
separate approval/workflow-gated transition with
`connector.promotion_policy.enabled` evidence. Enabled required policies are
now auto-selected during controlled ontology promotion when `policy_id` is
omitted, so required gates cannot be bypassed before the TypeDB mutation
boundary is called. Promotion policy authoring, enablement and revision now
fail before policy/audit writes when the persisted connector registry reference
is missing or invalid. Versioned promotion policy sets can now activate a single
required-gate set per connector after validating the connector through the same
persisted registry reference, so multiple enabled required policies are
evaluated together with `connector.promotion_policy_set.activated` evidence
instead of being selected implicitly; once a set is active, single-policy
`policy_id` selection is rejected to avoid partial gate evaluation. Replacing or
rolling back an active policy set now requires approval and workflow signal
evidence, writes `connector.promotion_policy_set.replaced` or
`connector.promotion_policy_set.rolled_back`, and supersedes the prior active
set. Replacement can also adopt approved draft policy revisions atomically:
the current required policy is superseded, the revised policy becomes
`enabled` / `required`, `connector.promotion_policy.revision_adopted` is
written, and the new active set stores the adoption evidence in the same
transaction. Policy and policy-set promotion rejections now write
`connector.ontology_promotion.rejected` audit evidence before returning the
validation response. The connector console now includes compact policy
authoring, enablement and policy-set evidence controls that can post to the API
or keep local public-safe previews when the API is unavailable.

## Architecture Defaults

- Frontend: Next.js + React.
- Backend/API: Python + FastAPI.
- API style: REST/OpenAPI first.
- Data: Postgres + TypeDB.
- Workflow runtime: Temporal OSS self-hosted behind an Axis adapter.
- Identity: OIDC-first, with Keycloak/self-hosted support.
- Tenancy: multi-tenant SaaS, single-tenant managed and on-prem/private cloud.
- Agents: L0-L4 autonomy model and typed action registry.
- Permissions: RBAC + ABAC + relationship-aware checks.
- Audit: append-only audit ledger.
- Observability: OpenTelemetry-first.
- Deployment: Docker Compose for local/dev, Kubernetes/Helm for production.
- Tooling direction: `uv`, `pnpm`, Docker.

## Local Runtime

The development runtime is self-hosted through Docker Compose:

```bash
cp .env.example .env
make dev-stack-up
```

Services:

- Postgres: `localhost:5432`
- TypeDB gRPC: `localhost:1729`
- TypeDB HTTP: `http://localhost:8001`
- Temporal: `localhost:7233`
- Temporal UI: `http://localhost:8088`
- MinIO API: `http://localhost:9000`
- MinIO Console: `http://localhost:9001`
- Keycloak: `http://localhost:8080`

Stop the stack with:

```bash
make dev-stack-down
```

## Development

Install dependencies:

```bash
make install
```

Run checks:

```bash
make lint
make test
make build-web
make openapi-check
```

Run opt-in integration checks against the local Docker runtime:

```bash
make dev-stack-up
make test-integration
```

Run web smoke tests against the production build:

```bash
pnpm --filter @limes-axis/web exec playwright install chromium
pnpm --filter @limes-axis/web test:e2e
```

Run the live overview smoke test when the local API is running:

```bash
pnpm --filter @limes-axis/web test:e2e:live
```

Run the web console locally:

```bash
pnpm --filter @limes-axis/web dev --hostname 127.0.0.1 --port 3000
```

Apply the Postgres migrations:

```bash
cd services/api
uv run alembic upgrade head
```

## Repository Strategy

Axis starts as one public repository to keep the core coherent. It is still
designed with extractable boundaries from day one.

Cloud, Enterprise, connectors, SDKs, deployment and docs may become separate
repositories when they develop different release cadences, ownership, security
requirements or customer-specific concerns.

## Roadmap

See [`plan.md`](./plan.md) for the public milestone roadmap.

The roadmap is organized as:

- Foundation: trustworthy self-hostable platform base.
- Platform: usable governance control plane with reference demo.
- Enterprise: deployment, security, support and compliance hardening.

Architecture and acceptance notes:

- [`docs/architecture.md`](./docs/architecture.md)
- [`docs/foundation-acceptance.md`](./docs/foundation-acceptance.md)
- [`docs/platform-overview.md`](./docs/platform-overview.md)
- [`docs/platform-ontology.md`](./docs/platform-ontology.md)
- [`docs/platform-workflows.md`](./docs/platform-workflows.md)
- [`docs/platform-approvals.md`](./docs/platform-approvals.md)
- [`docs/platform-audit.md`](./docs/platform-audit.md)
- [`docs/platform-agents.md`](./docs/platform-agents.md)
- [`docs/platform-actions.md`](./docs/platform-actions.md)
- [`docs/platform-persistence.md`](./docs/platform-persistence.md)
- [`docs/platform-model-routing.md`](./docs/platform-model-routing.md)
- [`docs/platform-simulation.md`](./docs/platform-simulation.md)
- [`docs/platform-manufacturing-operations.md`](./docs/platform-manufacturing-operations.md)
- [`docs/platform-connectors.md`](./docs/platform-connectors.md)
- [`docs/platform-settings.md`](./docs/platform-settings.md)
- [`docs/threat-model.md`](./docs/threat-model.md)
- [`docs/support-operations.md`](./docs/support-operations.md)

Reference examples:

- [`examples/manufacturing-plant`](./examples/manufacturing-plant)

## Contributing

Axis is early. Contributions are welcome once contribution and CLA processes are
in place.

See [`CONTRIBUTING.md`](./CONTRIBUTING.md) and [`CLA.md`](./CLA.md).

## License

Apache-2.0. See [`LICENSE`](./LICENSE).
