# Limes Axis Public Plan

Last updated: 2026-06-22

## Summary

Limes Axis is the sovereign AI control plane for European operations.

It starts as an open-source core that can run locally or in controlled
infrastructure, then expands into managed cloud, dedicated enterprise and
on-prem deployment paths.

Axis is designed to integrate first and replace gradually: existing systems stay
in place while Axis becomes the governed layer where data, workflows, people,
permissions and AI agents operate together.

## Product Principles

- Sovereignty must be practical: the open core must not require managed services.
- AI agents must be governed, permissioned, observable and auditable.
- Human approval remains central for risky actions.
- Operational ontology is the core context layer.
- Workflow execution must be durable and inspectable.
- Public open-source core and commercial operations should reinforce each other.
- The initial repository is unified, but future extraction into modules/repos is
  expected when parts grow large enough.

## Public Architecture Direction

Axis will use:

- Python + TypeScript as the two-language rule.
- Next.js + React for the governance console.
- FastAPI for the core API.
- REST/OpenAPI for public and internal contracts.
- Postgres for operational and transactional data.
- TypeDB for operational ontology and relationship-aware reasoning.
- Temporal OSS as the initial self-hosted workflow runtime behind an adapter.
- OIDC-first identity, with self-hosted Keycloak support.
- RBAC, ABAC and relationship-aware permissions.
- Append-only audit ledger.
- Provider-agnostic model routing with no external data egress by default.
- Docker Compose for local development and Kubernetes/Helm for production paths.

## Milestone Roadmap

### Foundation

- [x] Create the initial monorepo structure.
- [x] Add Python/FastAPI service foundation.
- [x] Add Next.js governance console foundation.
- [x] Add local Docker Compose runtime.
- [x] Add Postgres, TypeDB and Temporal local services.
- [x] Define tenant, actor, audit, action and workflow schemas.
- [x] Define the operational ontology primitives.
- [x] Define the Workflow Runtime Port and Temporal adapter.
- [x] Define the typed action registry.
- [x] Define the L0-L4 agent autonomy model.
- [x] Add OIDC/Keycloak identity boundary.
- [x] Add initial test, lint and CI commands.
- [x] Add repository issue, PR and security policy templates.
- [x] Generate and check the OpenAPI contract.
- [x] Add API readiness checks and console API status.
- [x] Add opt-in Postgres, TypeDB and Temporal integration tests.
- [x] Add Playwright smoke tests to the web CI gate.

Foundation acceptance is tracked in
[`docs/foundation-acceptance.md`](./docs/foundation-acceptance.md).

### Platform

- [x] Build the governance console overview.
- [x] Build the ontology explorer.
- [x] Build the workflow console.
- [x] Build the agent registry.
- [x] Build the action registry UI.
- [x] Build the approval inbox.
- [x] Build the audit explorer.
- [x] Build the model routing and cost observability layer.
- [x] Add the Postgres persistence foundation for approvals, actions and audit events.
- [x] Add API-backed approval decisions with audit writes.
- [x] Connect the approval console to persisted decision submission with local fallback.
- [x] Enforce demo approval decision permissions before persistence.
- [x] Signal approval decisions through the workflow runtime adapter.
- [x] Persist typed action run requests with idempotency enforcement.
- [x] Signal workflow runtime from typed action payloads behind policy.
- [x] Bind approval/action mutation endpoints to OIDC-derived actor identity
  and scopes.
- [x] Enforce relationship-derived ontology scopes on entity detail reads and
  action payload resource references.
- [x] Route ontology graph reads through a permission-aware query adapter with
  optional TypeDB read boundary.
- [x] Add a governance console OIDC session bridge for bearer-token API calls.
- [x] Query persisted audit events from the audit explorer.
- [x] Add demo audit export manifests, retention enforcement and integrity proof.
- [x] Persist workflow run state and tenant-scoped history views.
- [x] Build replay and simulation foundations.
- [x] Persist replay simulation outputs as governed audit artifacts.
- [x] Add retention-aware replay windows for simulation responses.
- [x] Add connector manifest foundation and file/CSV preview.
- [x] Add metadata-only external database connector preview.
- [x] Add tenant-scoped persisted connector manifest records.
- [x] Add tenant-scoped connector configuration persistence.
- [x] Persist connector ontology proposals without graph mutation.
- [x] Record manual connector import requests behind approval, workflow and
  idempotency gates.
- [x] Add Vault/KMS credential lease records with renew/revoke evidence.
- [x] Add optional self-hosted Vault/KMS lease runtime adapter.
- [x] Author connector promotion policies before required enforcement.
- [x] Enforce enabled required connector promotion policies before ontology
  mutation execution.
- [x] Add connector console policy authoring controls with API/local preview.
- [x] Add connector promotion policy enablement workflow with audit evidence.
- [x] Add versioned connector promotion policy sets for multi-policy required gates.
- [x] Add governed connector promotion policy set replacement and rollback evidence.
- [x] Add atomic adoption of approved draft policy revisions during policy-set replacement.
- [x] Add deferred scheduled connector sync planning from run records.
- [x] Add idempotent deferred dispatch claims for scheduled connector sync.
- [x] Add scheduled connector sync execution boundary with opt-in self-hosted runtime.
- [x] Add Postgres external DB sync adapter boundary with public-safe profile evidence.
- [ ] Build the full connector framework beyond preview-only manifests.
- [ ] Build the manufacturing operations reference demo.

The governance console overview is backed by the first public-safe synthetic
manufacturing seed. The full manufacturing reference demo remains open until it
has ontology relationships, approval actions, workflow execution and replay.

The governance console includes a local OIDC session bridge for demo and
developer workflows. A user can attach a bearer token in the console toolbar;
the console decodes actor, tenant and scopes for display and sends the token as
`Authorization: Bearer ...` to approval decision, action run and ontology entity
detail API calls. Full OIDC authorization-code login, refresh, secure cookie
session management and provider configuration remain Platform/Enterprise work.

The ontology explorer and entity detail pages are currently read-only and backed
by the synthetic manufacturing graph. Graph reads now pass through the Axis
ontology query runtime, expose query metadata and can filter relationships by
OIDC-derived relationship scopes when a bearer token is present or OIDC auth is
required by configuration. The TypeDB read boundary is optional and separated
from graph mutations. Live TypeDB response mapping, persisted relationship
metadata and broader graph authorization remain Platform work.

The workflow console is currently read-only and backed by the synthetic
manufacturing workflow seed, with a persisted workflow run endpoint available
when Postgres records exist. Approval decisions now signal the workflow runtime
adapter when available. Deterministic replay, workflow history retention and
workflow mutation controls remain Platform work.

The approval queue is still read-only for listing. A demo decision endpoint now
persists approval decisions and appends audit events, and the web console
submits reviewer decisions to it when available while keeping a standalone local
fallback. The decision endpoint enforces the required demo approval scope before
persistence and signals the workflow runtime adapter. When a bearer token is
present, or when OIDC auth is required by configuration, the endpoint validates
the token against configurable OIDC/JWKS settings and derives tenant, actor and
scopes from token claims before persistence. Broader relationship-aware
permission enforcement remains Platform work.

The audit explorer is backed by the synthetic manufacturing audit seed and can
query persisted `audit_events` through the demo API when records exist. The demo
API can also return a redacted JSON export bundle with manifest checksum,
applied filters, retention-window enforcement and hash-chain integrity proof.
Retention deletion execution, legal hold workflow and production-grade
tenant-scoped query permissions remain Platform work.

The replay/simulation foundation derives public-safe replay artifacts from
workflow run history, timeline events and redacted audit evidence. The
`/simulation` page shows baseline versus simulated policy decisions and
governed connector policy-set version diffs over historical events for the
manufacturing demo. Replay outputs can now be persisted as governed audit
artifacts with `simulation.replay_output.persisted` evidence, retention
metadata and idempotency protection. Replay responses now enforce
retention-aware query windows across timeline, audit and persisted output
records, with a legal-hold bypass for governance review. Temporal deterministic
replay, arbitrary policy diffing, physical deletion jobs and production legal
hold workflows remain Platform and Enterprise work.

The connector foundation exposes a public-safe manifest registry, a
preview-only file/CSV connector for manufacturing asset intake and a
metadata-only external database preview connector. The API can validate CSV
rows, map them to ontology entity proposals and return a redacted audit event
preview through `/demo/manufacturing/connectors` and
`/demo/manufacturing/connectors/file-csv/preview`. It can also preview declared
external DB table metadata through
`/demo/manufacturing/connectors/external-db/preview`, using profile ids and
credential handles while blocking raw connection material, SQL text and live
queries. Tenant-scoped connector manifests can now be registered through
`/demo/manufacturing/connectors/manifests`, writing
`connector.manifest.registered` audit evidence while rejecting raw connection
fields, SQL/query text and credential material. The API also stores and
queries tenant-scoped preview connector configuration through
`/demo/manufacturing/connectors/configurations`, rejecting raw credential
fields in configuration payloads. The API now also stores metadata-only
credential handles and rotation history through
`/demo/manufacturing/connectors/credential-handles`, using external secret
references instead of raw credential values. Short-lived credential leases can
now be requested, renewed and revoked through
`/demo/manufacturing/connectors/credential-leases`, writing
`connector.credential_lease.*` audit evidence while returning only references,
timestamps, permission decisions and adapter evidence. The lease runtime is
deferred by default and can use the optional self-hosted Vault/KMS adapter when
`AXIS_CREDENTIAL_LEASE_EXECUTION_ENABLED=true`, still without returning secret
material. Connector run records can now be written through
`/demo/manufacturing/connectors/runs`; each record stores only redacted
summaries and links to an append-only
`connector.run.recorded` audit event. Governed dry-run connector execution now
calls the deferred Axis
connector execution adapter, requires credential handle ids, writes
`connector.run.execution_deferred` audit evidence and still does not start live
sync. Scheduled sync plans can now be recorded through the same run endpoint
with `execution_mode=scheduled_sync_plan`, active credential lease evidence,
schedule metadata and `connector.run.sync_scheduled` audit evidence, while the
deferred scheduler adapter keeps `external_sync_started=false`.
Scheduled plans can now be dispatch-claimed through
`/demo/manufacturing/connectors/runs/{run_id}/dispatch`, requiring
`connectors:sync:dispatch`, active lease evidence and an idempotency key. The
dispatch boundary writes `connector.run.sync_dispatch_deferred` and still keeps
`external_sync_started=false`.
Dispatch-claimed plans can now receive a sync execution attempt through
`/demo/manufacturing/connectors/runs/{run_id}/execute-sync`, requiring
`connectors:sync:execute`, active lease evidence and an idempotency key. The
default execution runtime writes `connector.run.sync_execution_deferred`; the
opt-in self-hosted demo runtime, enabled with
`AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED=true`, can write
`connector.run.sync_execution_completed` without external egress, credential
material retrieval or graph mutation.
External DB sync can opt into the Postgres profile adapter boundary with
`AXIS_EXTERNAL_DB_SYNC_EXECUTION_ENABLED=true`, adding public-safe
provider/profile/table/count evidence while still omitting raw connection
strings and credential material.
Preview-derived ontology proposals can now be persisted through
`/demo/manufacturing/connectors/ontology-proposals`; each proposal is
audit-backed and initially marked with `graph_mutation_status=not_applied`.
Manual connector import requests can now be recorded through
`/demo/manufacturing/connectors/manual-imports`; each request is tenant-scoped,
idempotent, approval-gated, workflow-referenced and audit-backed with
`connector.manual_import.requested`, while graph mutation remains
`not_applied`. Decisions can now be recorded through
`/demo/manufacturing/connectors/manual-imports/{import_id}/decision`; each
decision stores the approval outcome, workflow signal status and
`connector.manual_import.decision_recorded` audit evidence without executing
the connector. Approved proposal promotion can now be requested through
`/demo/manufacturing/connectors/ontology-proposals/promotions`; each promotion
requires approval evidence, workflow signal evidence, idempotency and
`connectors:ontology:promote`, then applies or defers the TypeDB graph mutation
through the Axis ontology mutation adapter with append-only
`connector.ontology_promotion.*` audit evidence. Replays with the same
idempotency key and payload return the existing request or promotion instead of
writing duplicate audit events. Connector promotion policies can now be
authored through `/demo/manufacturing/connectors/promotion-policies`; each
policy records the authoring permission, required promotion scopes, approved
manual import state, workflow signal state, allowed risk levels and
`connector.promotion_policy.authored` audit evidence without executing
connectors or mutating TypeDB. Policies are enabled through
`/demo/manufacturing/connectors/promotion-policies/{policy_id}/enable`, which
requires `connectors:promotion_policy:enable`, an approved decision, workflow
signal evidence and writes `connector.promotion_policy.enabled`. Draft policies
can be revised append-only through
`/demo/manufacturing/connectors/promotion-policies/{policy_id}/revise`, which
requires `connectors:promotion_policy:revise`, approved revision evidence,
workflow signal evidence and an idempotency key. Enabled required policies are
not revised in place; future versions must be adopted through a governed
policy-set transition. Enabled required policies are auto-selected when a
promotion request omits `policy_id` and are enforced before the TypeDB mutation
adapter is called. When more than one enabled required policy applies,
`/demo/manufacturing/connectors/promotion-policy-sets`
can activate a versioned active set with
`connectors:promotion_policy_set:activate`; the promotion endpoint evaluates all
policies in that set and stores `policy_set_id`, `policy_ids` and
`policy_set_enforced` evidence. When a policy set is active, explicit single
`policy_id` selection is rejected so promotions cannot bypass the full
required-gate set. Replacing or rolling back an active set requires
`replaces_policy_set_id`, an approved transition decision and workflow evidence.
Replacement writes `connector.promotion_policy_set.replaced`; rollback restores a
superseded target through a new active version, writes
`connector.promotion_policy_set.rolled_back` and marks the previous active set
`superseded`. Replacement can carry `policy_revision_adoptions` so approved
draft revisions are adopted atomically with the set transition; Axis writes
`connector.promotion_policy.revision_adopted`, supersedes the current required
policy and stores adoption evidence on the new active set. Policy and
policy-set promotion rejections write
`connector.ontology_promotion.rejected` audit evidence with the effective
policy context before the API returns 422. If multiple required policies exist
without an active set, Axis still rejects implicit selection.
The `/connectors` console shows runtime boundaries, required permissions,
blocked operations, tenant configuration, credential handle posture, connector
run evidence, deferred execution metadata, persisted ontology proposal
evidence, promotion evidence, manual import decision evidence, promotion policy
authoring/enforcement evidence, versioned policy-set evidence and schema
mapping with an offline fallback seed.
It can author promotion policies through the API when available, enable them
with approval/workflow evidence or record local public-safe previews when the API
is offline.
Manifest lifecycle transitions beyond preview-only registration,
provider-specific Vault/KMS adapters, provider-specific scheduled live sync
beyond the self-hosted execution boundary, live external database adapters and
connector-backed production actions remain Platform work.

The agent registry is currently read-only and backed by the synthetic
manufacturing agent seed. Production action execution, persisted agent state,
tenant-scoped agent configuration, runtime policy enforcement and model cost
observability remain Platform work.

The action registry UI is currently backed by the synthetic manufacturing
action seed for catalog browsing. Typed dry-run/proposal action requests can now
be persisted through the demo API with idempotency enforcement and append-only
audit events. Approval-gated action payloads now signal the Axis workflow
runtime adapter after persistence, with explicit degraded status when the
runtime is unavailable. When a bearer token is present, or when OIDC auth is
required by configuration, action run creation derives tenant, actor and scopes
from token claims and rejects actor impersonation before persistence. Action
payload fields marked as ontology references also require the scopes attached to
their connected ontology relationships, preventing cross-domain resource
references from bypassing the typed action permission check. Live production
execution, connector invocation and broader relationship-aware permission
enforcement remain Platform work.

The model routing and cost observability layer is currently read-only and backed
by synthetic manufacturing route telemetry. Live provider adapters,
provider-specific billing ingestion, tenant budget enforcement, persisted usage
records, OpenTelemetry spans from runtime code and audit writes from live route
decisions remain Platform work.

### Enterprise

- [ ] Add single-tenant managed deployment path.
- [ ] Add on-prem/private cloud reference architecture.
- [ ] Add Helm charts and production deployment guides.
- [ ] Add backup and restore procedures.
- [ ] Add enterprise-grade audit export workflows beyond the current retention
  and integrity controls.
- [ ] Add enterprise identity and SSO hardening.
- [ ] Add security review and threat model documentation.
- [ ] Add support and operations runbooks.

## Expansion Rule

Axis starts unified, but the architecture must keep boundaries extractable.

Future repositories may include:

- `limes-axis-cloud`
- `limes-axis-enterprise`
- `limes-axis-connectors`
- `limes-axis-sdk`
- `limes-axis-deploy`
- `limes-axis-docs`

Extraction should happen when a module has at least two of these traits:

- independent release cadence;
- separate team or ownership;
- enterprise-only secrets, permissions or deployment logic;
- customer-specific integrations;
- independent SDK versioning;
- large connector surface;
- cloud operations that differ materially from the open-source core;
- documentation needs that outgrow the product repo.

## Contribution Policy

The project uses Apache-2.0 for the open-source core and plans to require a
Contributor License Agreement before accepting substantial external
contributions.

The CLA text in this repository is an initial project baseline and should be
reviewed legally before broad external contribution intake.

## What Is Intentionally Not Promised Yet

- No production readiness claim.
- No completed ERP/MES/CRM integrations.
- No uncontrolled autonomous agents.
- No dependency on a proprietary hosted model provider.
- No promise that commercial Cloud or Enterprise code will live in this repo.
