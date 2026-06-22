# Manufacturing Plant Reference Demo

This example documents the first synthetic reference scenario for Limes Axis:
the Plant Operations Cockpit.

The seed is intentionally small and public-safe. It represents a fictional demo
tenant, fictional plant context, role-based owners and system IDs. It must not
include customer data, personal names, private contacts, pricing, contracts or
secrets.

## Current Seed

The current seed is served by:

```text
GET /demo/manufacturing/overview
GET /demo/manufacturing/ontology
GET /demo/manufacturing/ontology/entities/{node_id}
GET /demo/manufacturing/workflows
GET /demo/manufacturing/workflows/runs
GET /demo/manufacturing/approvals
POST /demo/manufacturing/approvals/{approval_id}/decision
GET /demo/manufacturing/audit
GET /demo/manufacturing/audit/events
GET /demo/manufacturing/audit/export
GET /demo/manufacturing/agents
GET /demo/manufacturing/actions
POST /demo/manufacturing/actions/{action_id}/runs
GET /demo/manufacturing/model-routing
GET /demo/manufacturing/connectors
GET /demo/manufacturing/connectors/configurations
POST /demo/manufacturing/connectors/configurations
GET /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles
POST /demo/manufacturing/connectors/credential-handles/{handle_id}/rotations
POST /demo/manufacturing/connectors/file-csv/preview
```

It includes:

- Ravenna Works as the fictional plant;
- supplier delay, quality drift and maintenance risk signals;
- active workflow summaries;
- pending approval summaries;
- governed L1/L2 agents;
- recent audit evidence;
- read-only ontology nodes and relationships for source systems, permission
  scopes, risks, workflows, approvals and agents.
- read-only ontology entity details with inbound/outbound relationships,
  permission scopes, evidence refs and data access summaries.
- read-only workflow runs with runtime adapter metadata, pending signals,
  controls and timeline preview.
- API-backed persisted workflow runs and tenant-scoped timeline history.
- approval inbox proposals with evidence, data accessed, risk review,
  alternatives, model policy and audit event preview.
- persisted demo approval decisions with append-only audit events.
- web console decision submission to the persisted demo endpoint, with local
  fallback for standalone runs.
- demo approval decision permission checks using the approval's required scope.
- workflow signal execution through the Axis workflow runtime adapter when the
  runtime is available.
- read-only audit explorer events with tenant, event type and scope filters,
  evidence references and redacted payload previews.
- API-backed persisted audit event queries from append-only `audit_events`.
- redacted audit export bundles with manifest checksum, applied filters and
  retention-window enforcement, legal-hold bypass metadata and hash-chain
  integrity proof.
- read-only agent registry entries with autonomy boundaries, required
  permissions, model egress posture, action proposals, workflow links and
  approval references.
- action registry entries with typed input/output schemas, risk levels,
  approval modes, permissions, guardrails, workflow bindings, dry-run payload
  previews and API-backed action run request persistence.
- workflow signal execution from approval-gated action payloads through the
  Axis workflow runtime adapter, with redacted signal metadata in API responses
  and audit events.
- OIDC/JWKS actor binding for approval decisions and action run requests, with
  actor/scopes derived from bearer token claims when present or required.
- relationship-derived permission checks for authenticated ontology entity
  detail reads and action payload resource references.
- governance console OIDC session bridge for attaching a bearer token to
  approval, action and ontology entity detail API calls.
- replay/simulation preview artifacts derived from workflow history and redacted
  audit events.
- read-only model routing telemetry with provider boundaries, egress decisions,
  synthetic token/cost estimates, required permissions and audit evidence.
- preview-only file/CSV connector manifest for manufacturing asset intake, with
  schema validation, ontology proposal mapping and redacted audit event preview.
- tenant-scoped preview connector configuration for manufacturing asset intake,
  with raw credential fields rejected before persistence.
- metadata-only connector credential handles with external secret references
  and rotation history, without storing raw credential values.
- Postgres persistence foundation for approval records, action runs and
  append-only audit events.

## Next Expansion

The reference demo should grow into an end-to-end Platform scenario:

- realistic orders, machines, materials, suppliers, quality and maintenance
  entities;
- TypeDB-backed ontology relationships and permission-aware graph queries;
- broader API-backed use of Postgres approval/action/audit/workflow state;
- full OIDC authorization-code login, refresh and secure session management;
- deterministic workflow replay and broader policy simulation;
- broader relationship-aware permission enforcement beyond the current demo
  ontology-scope checks;
- physical audit retention deletion jobs, legal hold workflows and WORM/KMS
  ledger signing;
- production action registry execution, connector mutation and persisted agent state;
- live model provider adapters, budget enforcement, persisted usage telemetry
  and OpenTelemetry spans;
- persisted connector manifest management beyond the demo seed, production
  vault/KMS integration, scheduled sync, database connectors, connector run
  audit writes and connector-backed actions behind policy gates;
- persisted replay and simulation artifacts.
