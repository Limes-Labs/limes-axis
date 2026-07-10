# Runbook: Incident Response

Baseline incident response playbook for Limes Axis demo, design-partner and
production-readiness environments. It aligns with the severity model in
[`docs/support-operations.md`](../support-operations.md) and the threats in
[`docs/threat-model.md`](../threat-model.md). It is an operational baseline
for the open repository, not a signed customer incident-response commitment;
customer-specific incident ownership stays outside this repository
(`AXIS_SUPPORT_CUSTOMER_INCIDENT_OPERATIONS_CONFIGURED` gates that claim).

## Severity Levels

| Severity | Examples | Immediate Posture |
| --- | --- | --- |
| S1 | Suspected data exposure, cross-tenant access, credential/secret exposure, audit evidence tampering, unapproved external egress | Stop demo/customer use, preserve evidence, disable the implicated execution flags, open a security review immediately |
| S2 | API unavailable, migration failure, broken demo readiness gate, workflow runtime outage | Restore the service path or document the blocker before the next walkthrough |
| S3 | Single console page degraded while API evidence is healthy, degraded non-critical adapter | Triage with route-specific tests and browser evidence |
| S4 | Documentation mismatch, wording issue, missing checklist item | Fix through normal PR review |

Production response-time targets are configured through
`AXIS_SUPPORT_S1_RESPONSE_MINUTES` … `AXIS_SUPPORT_S4_RESPONSE_MINUTES` and
reported (as numbers, without contacts) by `/support/diagnostics`.

## 1. Declare And Contain

- Assign an incident id (`inc-<UTC timestamp>-<slug>`) and an incident lead.
- For S1: revoke or suspend implicated principals
  (`/identity/sessions/{session_ref}/revoke`, tenant suspension through
  `/platform/tenants/{tenant_id}/suspend` when a tenant boundary is
  implicated), and set the implicated execution flags to `false`
  (`AXIS_MODEL_ROUTING_EXECUTION_ENABLED`,
  `AXIS_AGENT_RUN_EXECUTION_ENABLED`,
  `AXIS_CONNECTOR_SYNC_EXECUTION_ENABLED`,
  `AXIS_CONNECTOR_LIVE_SYNC_EXECUTION_ENABLED`,
  `AXIS_CONNECTOR_SCHEDULED_LIVE_SYNC_ENABLED`,
  `AXIS_EXTERNAL_MODEL_EGRESS_ENABLED`) — every one of them fails closed.
- For suspected credential exposure, start
  [`docs/runbooks/secret-rotation.md`](./secret-rotation.md) in parallel.

## 2. Evidence Capture — Audit Ledger First

The append-only audit ledger is the primary evidence source. Capture it
before restarting services or changing state.

1. Query the ledger for the affected tenant and window
   (`GET /demo/manufacturing/audit/events` with tenant/event-type/actor
   filters; requires `audit:read`).
2. Produce a governed export bundle (`GET /demo/manufacturing/audit/export`)
   — it carries a manifest, checksum and hash-chain integrity proof, plus the
   ledger signature proof when `AXIS_AUDIT_LEDGER_SIGNING_*` is configured.
   Store the bundle with the incident record.
3. For S1, place legal holds so retention cannot delete evidence:
   `POST /demo/manufacturing/audit/legal-holds` (DB layer) and
   `POST /demo/manufacturing/audit/object-legal-holds` (object-store layer).
4. Review evidence invariants on the implicated surfaces (connector lease,
   egress policy, checkpoint and claim registries report public-safe
   `*_evidence_invariants`); an invariant that says secret material was
   accessed or external execution started is itself S1 evidence.

Only after the ledger is preserved, capture supporting diagnostics:

```bash
curl -s http://127.0.0.1:8000/support/diagnostics | python3 -m json.tool
curl -s http://127.0.0.1:8000/ready | python3 -m json.tool
curl -s http://127.0.0.1:8000/deployment/readiness | python3 -m json.tool
make demo-check-live   # when the local console is part of the incident
```

`/support/diagnostics` (built by
`services/api/src/axis_api/support_diagnostics.py`) is public-safe by design:
it reports posture, blockers and runbook links without tokens, secrets, DSNs
or personal contacts, so it can be attached to public issues. Session device
metadata (owner/admin-scoped session listing) can support anomaly review for
identity incidents.

## 3. Triage And Diagnose

- Reproduce with the narrowest executable check: the per-surface API tests,
  `services/api/tests/test_tenant_isolation.py` for any suspected tenant
  boundary issue, and the [`security review
  checklist`](../security-review-checklist.md) section that matches the
  threat.
- Map the incident to a threat-model id (TM-001 … TM-006) and record it; that
  drives which controls and tests must change afterwards.
- Check recent flag changes first: any enablement of a live execution flag is
  audit-relevant and should correlate with ledger events.

## 4. Escalate

Escalation channels are role-based classes (for example
`customer_success_manager`, `platform_engineering_on_call`) configured in
`AXIS_SUPPORT_ESCALATION_CHANNELS` — never personal names or numbers in this
repository. For S1 security findings from external reporters, follow
[`SECURITY.md`](../../SECURITY.md) (private disclosure), not the public issue
tracker. Escalate to the incident review required by
`AXIS_SUPPORT_INCIDENT_REVIEW_REQUIRED=true` for every S1/S2.

## 5. Communicate

Template for status updates (initial, periodic, and resolution):

```text
Incident: <incident id> — <one-line public-safe summary>
Severity: S<1-4>   Status: investigating | contained | monitoring | resolved
Started (UTC): <time>   Last update (UTC): <time>
Impact: <tenants/surfaces affected, stated without customer data>
Actions taken: <containment, flags disabled, holds placed>
Evidence: <audit export bundle id/checksum, diagnostics captured>
Next update by (UTC): <time>
```

Keep updates public-safe: no tokens, secrets, personal data, customer names
or raw payloads. The status page (`AXIS_SUPPORT_STATUS_PAGE_URL`) carries
customer-facing state in production profiles.

## 6. Resolve And Review

- Hold the post-incident review (required for S1/S2): timeline from the audit
  ledger, root cause, threat-model mapping, control gaps.
- Land regression tests with the fix (extend the tenant-isolation matrix,
  per-surface tests or rehearsal contracts as appropriate) and update
  [`docs/threat-model.md`](../threat-model.md) if the risk picture changed.
- Release legal holds only after the review closes
  (`POST /demo/manufacturing/audit/legal-holds/{hold_id}/release`).
- Complete credential rotation cleanup (revocation of old material) per the
  secret rotation runbook.
