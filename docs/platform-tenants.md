# Platform Tenant Lifecycle and Quotas

The tenant lifecycle slice turns tenants from migration-seeded rows into
governed platform resources. It adds operator-driven provisioning, suspension
and reactivation, a per-tenant quota store, and real enforcement wiring for
suspended tenants and quota overrides. This is the entry gate to the
multi-tenant SaaS reference in the Enterprise track.

## Current Scope

- `POST /platform/tenants` provisions a tenant with an idempotency key,
  optional bootstrap admin actor and `platform.tenant.provisioned` audit
  evidence. Provisioning requires the `platform:tenant:operator` and
  `platform:tenant:provision` scopes.
- `GET /platform/tenants` lists tenants with an optional lifecycle status
  filter. Authenticated reads require the `platform:tenant:operator` and
  `platform:tenant:read` scopes.
- `POST /platform/tenants/{tenant_id}/suspend` and
  `POST /platform/tenants/{tenant_id}/reactivate` transition the lifecycle
  status with `platform.tenant.suspended` / `platform.tenant.reactivated`
  audit evidence. Both require the `platform:tenant:operator` and
  `platform:tenant:suspend` scopes.
- `GET /platform/tenants/{tenant_id}/quotas` and
  `PUT /platform/tenants/{tenant_id}/quotas` read and replace the typed
  per-tenant quota set. Updates require the `platform:tenant:operator` and
  `platform:tenant:quota` scopes; reads require the operator and read scopes.

## Operator Authorization Model

Tenant lifecycle is a platform-operator surface, not a tenant surface. No
cross-tenant admin convention existed before this slice, so it introduces one:
every operation requires the dedicated `platform:tenant:operator` scope in
addition to the action scope, and the usual principal-tenant match check is
deliberately absent — the operator authenticates under their own tenant and
acts on other tenants. Actor impersonation is still rejected: when an OIDC
principal is present, `requested_by` is bound to the verified actor and the
verified token scopes replace self-asserted ones.

The demo-mode caveat applies as everywhere: in unauthenticated local demo mode
(`AXIS_OIDC_AUTH_REQUIRED` disabled and no bearer token attached), actor and
scopes are self-asserted in the request body. The routes are only truly
OIDC-bound when authentication is present or required.

## Lifecycle Model

A tenant carries a `status` (`active`, `suspended`, `pending_deletion` — the
enum is extensible), display metadata (`display_name`, `description`),
provisioning evidence (`created_by`, `provision_idempotency_key`,
`bootstrap_admin_actor_id`, audit references) and lifecycle timestamps
(`suspended_at`/`suspended_by`/`suspension_reason`, `reactivated_at`/
`reactivated_by`). Migration `0047_tenant_lifecycle` chains after
`0046_oidc_session_lifecycle`; existing seeded tenants migrate to
`status=active` through server defaults with zero behavior change.

Provisioning follows the action-run idempotency convention: replaying the same
idempotency key with the same payload returns the persisted tenant with
`idempotent_replay=true` and HTTP 200; reusing the key with a different payload
or reusing the tenant id under a new key returns a `CONFLICT`. An optional
bootstrap admin creates the actor row inside the same transaction. Scope grants
stay IdP-owned: the requested bootstrap scopes are recorded as audit evidence
only, never as a live grant.

Suspension requires an active tenant and a reason; reactivation requires a
non-active tenant and clears the suspension fields (history stays in the audit
ledger). Lifecycle audit events are written in the target tenant's ledger with
the operator recorded as actor, so a tenant's own audit history shows who
suspended or reactivated it and why.

## Quota Model

`tenant_quotas` holds one row per tenant and typed quota key:

- `api_requests_per_window` — overrides the global API rate limit
  (`AXIS_API_RATE_LIMIT_REQUESTS`) for that tenant on the protected paths;
- `max_concurrent_sessions` — overrides the global concurrent browser-session
  cap (`AXIS_OIDC_SESSION_MAX_CONCURRENT`; `0` means unlimited);
- `max_connector_sync_rows_per_run` — caps the governed live-sync row limit
  per run below the connector profile bound.

Quota rows are update-in-place rather than revisioned: the `PUT` endpoint
replaces the typed quota set (a key set to a value is upserted, a key left
unset is cleared), and the append-only history lives in the
`platform.tenant.quota.updated` audit trail written for every individual key
change with previous and new values. This is the simplest existing pattern
that still audits every change; revisioned quota rows can be layered on later
if rollback bundles become necessary.

## Enforcement Points

Enforcement is wired at real choke points, not decoratively:

- **Suspended tenants fail closed.** The shared OIDC principal dependency —
  the single place where tenant scoping is resolved for every OIDC-bound
  route, covering bearer tokens and browser session cookies — rejects requests
  for suspended or pending-deletion tenants with a 403, a distinct
  `tenant_suspended` / `tenant_pending_deletion` reason and a
  `platform.tenant.suspended_request.denied` audit event in the tenant's
  ledger. Unauthenticated demo-mode requests carry no verified tenant context
  and are not covered, matching the demo-mode caveat used across the API.
  Session-cookie plumbing endpoints that do not resolve a principal (for
  example `POST /identity/session/refresh`) can still rotate a session, but
  every resource access with that session is rejected at the principal
  boundary.
- **Per-tenant rate limits.** The API rate-limit middleware resolves the
  tenant from the HMAC-verified session cookie and applies the tenant's
  `api_requests_per_window` quota to a tenant-shared bucket, falling back to
  the global per-client limit when no tenant is resolvable or no quota exists.
  Bearer requests deliberately fall back to the global limit: the middleware
  never trusts an unverified tenant claim to select a higher limit, and full
  JWT verification belongs to the principal resolver, not the middleware.
  Rate-limited responses carry `scope: tenant_quota` or
  `scope: client_endpoint` so operators can tell which limit applied.
- **Concurrent sessions.** The OIDC callback reads the
  `max_concurrent_sessions` quota when present and revokes the oldest active
  sessions beyond the effective cap, exactly like the global setting.
- **Live-sync row caps.** Governed live-sync execution caps the plan's
  `max_records` (and per-batch read sizes) at
  `max_connector_sync_rows_per_run` when the quota is below the connector
  profile bound; the capped bound appears in the
  `connector.run.sync_execution_started` audit payload.

## Tenant State Cache

Suspension checks and per-tenant rate limits run on the hot request path, so
tenant status and quotas are read through a bounded in-process cache
(`AXIS_TENANT_STATE_CACHE_TTL_SECONDS`, default 5 seconds, at most 1024 tenant
entries). The staleness window equals the TTL: a suspension or quota change
made on another replica or process takes effect locally within at most one
TTL. Lifecycle and quota routes invalidate the local entry immediately, so
single-process deployments observe changes at once. A TTL of `0` disables
caching and reads fresh state on every request. If the status lookup itself
fails (for example the database is unreachable), the check defers to the route
layer, which surfaces the same persistence failure on its own database access.

## Boundaries

The slice is a foundation. It does not yet include:

- tenant deletion or data export (`pending_deletion` is modeled and blocked at
  the principal boundary, but no deletion pipeline exists);
- an approval-workflow gate on lifecycle transitions or quota changes;
- per-tenant quotas beyond the three typed keys;
- a console surface for tenant administration;
- distributed rate-limit or cache coordination across replicas (each process
  enforces from its own cache within the TTL staleness window).

Those capabilities remain Enterprise work behind the typed operator scopes,
the audited lifecycle transitions and the quota audit trail.

## Acceptance Notes

- API tests cover the provisioning happy path with bootstrap admin actor and
  audit evidence, idempotent replay, idempotency conflicts, duplicate tenants,
  duplicate bootstrap actors, invalid tenant ids and permission denials for
  each new scope.
- Lifecycle tests cover suspend → fail-closed 403 with audit evidence →
  reactivate restores access, lifecycle conflicts, unknown tenants, operator
  cross-tenant authorization and actor impersonation rejection.
- Quota tests cover typed updates, clears, per-change audit events, unchanged
  keys producing no events, validation bounds, unknown tenants and read/update
  scope enforcement.
- Enforcement tests cover the per-tenant rate limit tripping before the global
  limit, global fallback without a quota, tampered-cookie rejection, the
  concurrent-session override, the live-sync row cap (including bounded batch
  reads and the audited capped bound) and the cache staleness window with
  explicit invalidation.
- The OpenAPI contract is regenerated and checked; migration identifier tests
  cover the extended `tenants` schema and the new `tenant_quotas` table.
- Public documentation avoids customer data, personal names, contacts,
  pricing, credentials and deployment secrets.
