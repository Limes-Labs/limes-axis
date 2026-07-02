# Support Operations Runbook

This runbook defines the current public-safe support and operations baseline for
Limes Axis demo and design-partner evaluation environments. It is not a
production support contract, SLA, SOC process or compliance attestation.

## Scope

In scope:

- Local Docker Compose demo support.
- SME feedback and enterprise evaluation walkthrough support.
- Public-safe diagnostic capture through `/support/diagnostics`.
- Readiness posture review through `/ready`, `/identity/oidc/readiness`,
  `/deployment/readiness`, `make demo-check-live` and `make security-check`.
- Triage of API, web console, persistence, workflow and connector-boundary
  issues in the open-source repository.

Out of scope:

- 24/7 production support.
- Customer incident response ownership.
- Production SLOs, SLAs, RPO/RTO commitments or warranty terms.
- Managed Cloud, Enterprise private deployment support and customer-specific
  connector execution.
- Handling customer credentials, production datasets or private infrastructure
  access in the public repository.

## Public-Safe Diagnostic Bundle

Before a support or design-partner session, capture:

```bash
curl -s http://127.0.0.1:8000/support/diagnostics | python3 -m json.tool
make demo-check
make security-check
make demo-check-live
```

The support diagnostics endpoint is designed to be safe to share in public
issues or design-partner notes. It reports:

- service and environment profile;
- demo-support and production-support readiness booleans;
- deployment posture summary;
- identity readiness summary;
- model egress, connector execution, audit signing and object-store posture;
- support blockers;
- links to the relevant runbooks and threat model.

It must not return bearer tokens, raw JWKS, credential material, signing
material or database DSNs.

## Triage Flow

1. Confirm the environment profile from `/support/diagnostics`.
2. Confirm `/health` and `/ready` return HTTP 200.
3. Run `make demo-check` to validate static repository expectations.
4. Run `make security-check` to validate threat-model and posture contracts.
5. Run `make demo-check-live` while API and web are running.
6. If the issue is browser-visible, run `pnpm --filter @limes-axis/web test:e2e`
   and capture the failing route or console surface.
7. If the issue involves live services, run `make test-integration` with Docker
   services up.
8. Record the failing check name, route, command and timestamp in the issue or
   customer note.

## Severity Guidance

| Severity | Example | Response Goal |
| --- | --- | --- |
| S1 | Data exposure, cross-tenant access, audit evidence tampering | Stop demo/customer use, preserve evidence, open security review immediately |
| S2 | API unavailable, migration failure, broken demo readiness gate | Restore demo path or document blocker before the next walkthrough |
| S3 | Single console page degraded while API evidence is healthy | Triage with route-specific tests and browser evidence |
| S4 | Documentation mismatch, wording issue, missing checklist item | Fix through normal PR review |

## Evidence To Preserve

- Command output from the failed check.
- API route and HTTP status.
- Browser route and screenshot when UI is involved.
- Current git SHA.
- Docker Compose service status.
- Whether the issue appears in local demo, production-like evaluation or both.
- Any relevant audit event id, workflow run id or connector run id.

Do not paste customer credentials, raw tokens, private JWKS, database DSNs,
connector secrets or private production records into public issues.

## Escalation Boundaries

Escalate immediately when:

- `/support/diagnostics` reports unexpected production support readiness.
- `/deployment/readiness` omits known production blockers.
- `make security-check` fails.
- A tenant mismatch, actor impersonation or permission bypass is suspected.
- Audit integrity, legal hold or retention controls appear inconsistent.
- Connector credential handles, leases or external egress controls expose
  sensitive material.

## Current Production Gaps

- Production support model, named escalation paths and SLOs are not complete.
- Production backup, restore, retention, HA and disaster recovery are not
  complete across every stateful dependency.
- Enterprise SSO operations beyond the readiness/profile report are not
  complete.
- S3/MinIO WORM adapter readiness and a bounded object-store recovery
  rehearsal are implemented, but production bucket provisioning review, KMS
  policy, legal operations and full-bucket restore drills remain Enterprise
  work.
- A bounded Temporal namespace/history evidence rehearsal is implemented, but
  Temporal persistence restore, deterministic replay operations, archival
  policy review and RPO/RTO evidence remain Enterprise work.
- A bounded Secret rotation rehearsal is implemented, but upstream
  secret-manager rotation, access reviews, workload restart validation,
  rollback criteria and incident procedures remain Enterprise work.
- Live customer connector execution remains gated and should not be enabled
  without provider policy bundles, audit evidence and customer approval.
