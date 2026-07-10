# Security Review Checklist

This checklist operationalizes [`docs/threat-model.md`](./threat-model.md) for
PR review and pre-release review of the public Limes Axis repository. Each
section names the threat-model themes it covers, the executable checks that
back it and what a reviewer should verify by hand. It is a review aid, not a
certification.

Run before review:

```bash
make security-check
make lint
make test-api
```

## 1. Authentication And Session (TM-001, TM-006)

Executable checks: `services/api/tests/test_oidc_authorization_code_session.py`,
`test_oidc_session_lifecycle.py`, `test_identity_session_metadata.py`,
`test_health.py`.

- [ ] New or changed mutation endpoints bind the OIDC principal when a bearer
  token or session cookie is present, and reject actor/tenant impersonation
  before persistence.
- [ ] Cookie-authenticated state-changing routes stay behind
  `BrowserSessionCsrfMiddleware` (no new CSRF exemptions without review).
- [ ] No endpoint returns bearer tokens, raw JWKS, refresh tokens, session ids
  in clear form, or signing material; readiness/onboarding reports stay
  public-safe.
- [ ] Session lifecycle invariants hold: refresh rotation, idle/absolute
  timeouts, concurrent-session caps and keyed-hash session references.
- [ ] Local-demo-only relaxations (OIDC optional) are not presented as
  production defaults; `/deployment/readiness` gates still block.

## 2. Tenant Isolation (TM-001)

Executable check: `services/api/tests/test_tenant_isolation.py` — the
canonical table-driven matrix. Any new tenant-scoped read, list or write
surface must be added to its enforced case tables in the same PR.

- [ ] Every new query filters by `tenant_id` at the repository layer; no route
  trusts a caller-supplied `tenant_id` when a principal is bound (principal
  tenant binding is enforced on connector read/write routes and must stay
  that way).
- [ ] Cross-tenant reads by id return 403/404 (never 200 with data);
  cross-tenant listings omit foreign records; cross-tenant mutations are
  rejected without writing audit rows to the victim tenant.
- [ ] Suspended tenants stay fail-closed at the OIDC principal boundary.
- [ ] Per-tenant quotas and usage metering account to the request tenant only.

## 3. Egress (TM-003, TM-005)

Executable checks: `test_connector_execution.py`,
`test_connector_lease_scoped_live_sync.py`, `test_connector_live_sync.py`,
`test_connector_egress_policies.py`, `test_model_invocations.py`,
`test_agent_runs.py`.

- [ ] New execution paths are off by default behind an explicit `AXIS_` flag
  and record an honest deferred status when disabled — never fabricated
  output.
- [ ] External model egress remains blocked while
  `AXIS_EXTERNAL_MODEL_EGRESS_ENABLED=false`; model endpoints declare a
  hosting boundary and non-self-hosted routing requires explicit
  configuration.
- [ ] Connector live paths keep the full gate chain: `active_live` manifest,
  credential lease evidence, persisted egress policy, checkpoint claim and
  runtime egress enforcement; unknown or unapproved policies block before
  secret resolution is considered.
- [ ] Kubernetes profiles keep restricted/offline NetworkPolicy modes and the
  readiness gate that requires them for production.

## 4. Secrets And Leases (TM-002)

Executable checks: `test_connector_credential_handles.py`,
`test_connector_credential_leases.py`, `test_connector_secret_resolution` paths
inside the live-sync tests, `test_secret_rotation_rehearsal.py`.

- [ ] No surface stores or returns raw secrets, DSNs, SQL text or credential
  material; credential handles and leases stay reference-only metadata.
- [ ] Lease-scoped secret resolution keeps `secret_material_returned=false`
  evidence invariants; resolver output never includes credential values.
- [ ] Logs, audit payloads, export bundles and error messages are checked for
  secret shapes when connector or model provider inputs change.
- [ ] Secret rotation follows
  [`docs/runbooks/secret-rotation.md`](./runbooks/secret-rotation.md); rehearse
  with `make deployment-secret-rotation-rehearsal-plan` before production
  rotation.

## 5. Audit And WORM (TM-004)

Executable checks: `test_audit.py`, `test_audit_queries.py`,
`test_object_storage.py`, `test_connector_evidence_invariants.py`.

- [ ] Audit rows remain append-only; no code path updates or deletes ledger
  rows outside the permission-gated retention deletion flow.
- [ ] Export bundles keep checksum/hash-chain integrity proofs and redacted
  payload previews; ledger signing configuration
  (`AXIS_AUDIT_LEDGER_SIGNING_*`) is not weakened.
- [ ] S3-compatible COMPLIANCE retention still verifies bucket object-lock at
  bootstrap and fails closed on export when missing; legal holds (DB and
  object-store layers) keep blocking premature deletion.
- [ ] New governed actions write audit evidence with public-safe payloads and
  resolvable evidence references.

## 6. Deployment And Operations (TM-006)

Executable checks: `make deployment-check`,
`make deployment-profile-render-check`, `make container-check`,
`make container-security-check`, `make vulnerability-management-check`,
`test_deployment_readiness.py`, `test_support_diagnostics.py`.

- [ ] `/deployment/readiness` and `/support/diagnostics` stay public-safe and
  keep gating production claims (identity, egress, tenancy, DR, support).
- [ ] Demo materials do not overclaim: local compose is not production DR,
  rehearsal scripts are not executed operations, flags off by default are
  documented as off by default.
- [ ] Incidents follow
  [`docs/runbooks/incident-response.md`](./runbooks/incident-response.md);
  evidence capture is audit-ledger-first.
- [ ] Helm/values changes keep schema validation, rollout, HA and rehearsal
  targets working (`deployment-*-rehearsal-plan` targets still render).

## When To Re-Run The Full Threat Model

Re-review [`docs/threat-model.md`](./threat-model.md) — not just this
checklist — before:

- enabling any live execution flag against customer systems;
- adding a new connector family or model provider adapter;
- changing identity, permission or audit primitives;
- claiming production deployment readiness for a new tenancy profile.
