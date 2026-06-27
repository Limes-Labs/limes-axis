# Demo Readiness

This page defines the repeatable local demo contract for Limes Axis. It is
written for real SME and enterprise feedback sessions: the environment must use
the Axis API, migrations, persisted bootstrap records and local self-hosted
services, not browser-local mock data.

## Current Position

Axis is ready for a structured SME feedback demo when the acceptance checklist
below passes on the demo machine.

Axis is ready for an enterprise evaluation demo as an architecture and product
workflow walkthrough when the same checklist passes and the limitations section
is shared before the session. It is not yet a production enterprise deployment:
Helm, backup/restore, SSO hardening, WORM retention and production operations
runbooks remain tracked Enterprise work.

## No Browser-Local Mock Data

The governance console is API-required. Demo records shown in the browser must
come from Axis API responses backed by persisted tenant-scoped bootstrap rows,
Postgres operational state, generated audit artifacts or explicit deferred
runtime evidence.

The demo may include deterministic reference records because those records are
part of the migrated demo tenant state. It must not rely on hidden browser
fallback data, local random factories or UI-only mock objects.

## Local Runtime

The local demo stack is self-hosted through Docker Compose:

- Postgres for operational state and migrations.
- TypeDB for the ontology boundary.
- Temporal for workflow runtime integration.
- MinIO for the S3-compatible object-store path.
- Keycloak for self-hosted OIDC evaluation.

Start the service stack:

```bash
make demo-stack-up
```

Apply database migrations:

```bash
make demo-db-upgrade
```

Run the API:

```bash
make demo-api
```

Run the governance console in a second terminal:

```bash
make demo-web
```

The local console is configured for both `localhost:3000` and
`127.0.0.1:3000` development access, and the API also allows the
`localhost:3100` and `127.0.0.1:3100` origins used by Playwright against the
production Next.js build. This keeps the in-app Browser, local review sessions
and automated browser checks on the same Axis API.

Run static demo checks:

```bash
make demo-check
```

Run static and live checks after the API and web console are running:

```bash
make demo-check-live
```

Run browser smoke tests against the production Next.js build:

```bash
pnpm --filter @limes-axis/web test:e2e
```

Run the live browser smoke test when the local API is running:

```bash
pnpm --filter @limes-axis/web test:e2e:live
```

Stop the stack:

```bash
make demo-stack-down
```

## Acceptance Checklist

- [ ] `make demo-stack-up` starts Postgres, TypeDB, Temporal, Temporal UI, MinIO
      and Keycloak.
- [ ] `make demo-db-upgrade` applies all Alembic migrations against the local
      Postgres database.
- [ ] `make demo-api` starts FastAPI on `http://127.0.0.1:8000`.
- [ ] `make demo-web` starts the Next.js console on `http://127.0.0.1:3000`.
- [ ] `make demo-check` passes static repository checks.
- [ ] `make demo-check-live` passes `/health`, `/ready` and web home checks.
- [ ] `make demo-check-live` passes the browser no-store CORS preflight used by
      API-required console pages, including the `3100` origins used by
      production-build Playwright checks.
- [ ] `make demo-check-live` verifies the manufacturing operations snapshot
      returns persisted tenant-scoped domain rollups.
- [ ] The console shell uses the Axis brand palette and passes browser checks
      for dark theme tokens, visible API-backed state and no horizontal
      overflow.
- [ ] `pnpm --filter @limes-axis/web test:e2e` passes API-unavailable smoke
      tests against a production build with browser-local fallbacks disabled.
- [ ] `pnpm --filter @limes-axis/web test:e2e:live` passes the live overview
      smoke test against the running Axis API.
- [ ] The overview page loads from `/demo/manufacturing/overview`.
- [ ] The overview page composes `/demo/manufacturing/operations/snapshot` into
      the first-screen operational cockpit.
- [ ] The ontology page loads from `/demo/manufacturing/ontology`.
- [ ] The workflow page loads from `/demo/manufacturing/workflows`.
- [ ] The approval inbox loads from `/demo/manufacturing/approvals`.
- [ ] The audit explorer loads from `/demo/manufacturing/audit`.
- [ ] The agents page loads from `/demo/manufacturing/agents`.
- [ ] The actions page loads from `/demo/manufacturing/actions`.
- [ ] The model routing page loads from `/demo/manufacturing/model-routing`.
- [ ] The simulation page loads from `/demo/manufacturing/simulation/replay`.
- [ ] The connectors page loads from `/demo/manufacturing/connectors`.
- [ ] The manufacturing operations snapshot loads from
      `/demo/manufacturing/operations/snapshot`.
- [ ] A daily plant brief can be generated with persisted audit evidence.
- [ ] Quality, maintenance and supplier risk scenarios can be generated with
      persisted audit evidence.
- [ ] Connector manifest, configuration, credential handle and credential lease
      paths reject raw secret material.
- [ ] Connector evidence snapshots and exports use persisted audit artifacts.
- [ ] External model egress remains disabled unless explicitly configured.
- [ ] Live source-system connector execution remains blocked unless the guarded
      opt-in runtime boundary is configured.

## SME Feedback Demo

The SME demo should focus on operational governance:

- How Axis sits above ERP, MES, QMS, CMMS and supplier systems.
- How the ontology turns operational records into governed relationships.
- How approvals, actions, workflows, audit and agent boundaries are connected.
- How sensitive connector operations are staged through manifests, credential
  handles, leases, egress policies and evidence snapshots.
- How a plant manager or operations leader can review risk, action proposals
  and evidence without trusting an ungoverned agent.

Feedback to collect:

- Which operational systems must be connected first.
- Which approval gates map to existing SOPs.
- Which fields must be added to the manufacturing operations reference.
- Which audit exports are needed for internal governance or customers.
- Which deployment posture is acceptable: SaaS, managed single tenant,
  private cloud or on-prem.

## Enterprise Evaluation Demo

The enterprise evaluation demo should be framed as a product and architecture
walkthrough, not a production readiness claim.

Show:

- The self-hosted local stack and absence of required managed services.
- The OIDC/Keycloak direction and token-bound mutation paths.
- Tenant-scoped persisted reference records.
- Append-only audit events, export manifests and signature evidence.
- Deferred runtime boundaries for risky or external operations.
- The expansion path from one public repository into cloud, enterprise, SDK,
  connector, deployment and docs repositories when thresholds are reached.

Confirm before the session:

- No customer secrets are entered.
- No production source systems are connected.
- No unmanaged external model egress is enabled.
- No production deployment or compliance certification is claimed.

## Current Limitations

- Full live connector execution is not yet the default demo path.
- Full manufacturing operations reference demo remains open until TypeDB graph
  response mapping, production relationship metadata, approval actions,
  workflow execution and replay are fully backed by real persistence paths.
- Helm charts and production Kubernetes deployment guides are not complete.
- Backup and restore procedures are not complete.
- Enterprise SSO hardening is not complete.
- WORM/object-store retention for enterprise audit exports is not complete.
- Production support and operations runbooks are not complete.
- External model-provider execution is disabled by default.

## Automated Checks

The `services/api/scripts/check_demo_environment.py` script verifies:

- Demo Makefile targets.
- Local Docker Compose runtime services.
- Critical OpenAPI routes.
- Demo readiness documentation and README links.
- Browser no-store CORS preflight for API-required console fetches across the
  local dev and Playwright production-build origins.
- Manufacturing operations snapshot contract with persisted domain rollups.
- Optional live API and web checks when URLs are provided.

The check is intentionally conservative. If a demo command, route or document
is removed, the test suite should fail before a feedback session relies on a
broken path.
