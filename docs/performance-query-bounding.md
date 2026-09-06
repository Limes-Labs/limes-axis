# Query Bounding And Index Evidence

This document records which repository reads are bounded, which are not, and
what measured evidence justified the changes made for
[issue #363](https://github.com/Limes-Labs/limes-axis/issues/363).

A read is *bounded* when its cost is proportional to what the caller actually
returns. A read that is proportional to everything a tenant has ever
accumulated becomes slower for the tenants that use Axis most, which is the
wrong direction for a control plane.

## Inventory

`AxisPersistenceRepository` exposes 52 `list_*` reads. **Forty already take a
limit.** The twelve that do not are classified below by how they actually grow;
naming the naturally bounded ones matters as much as naming the risky ones, so
that a future reader does not re-derive the same conclusion.

### Grows with tenant scale

| Read | Growth | Status |
| --- | --- | --- |
| `list_current_data_asset_stewardship` | One row per declared asset | **Bounded by this change** — takes the asset ids the response returns |
| `count_data_resource_observations_by_asset` | One row per observed resource | **Bounded by this change** — grouped over the asset ids the response returns |
| `list_all_current_connector_manifests` | One row per connector | Open |

### Grows with time and is never pruned

No tenant action bounds these; they grow for as long as the tenant edits the
underlying object. They are the sharper long-term risk, and both back
revision-history responses whose shape would have to change to page them.

| Read | Growth |
| --- | --- |
| `list_connector_manifest_revisions` | One row per manifest revision, forever |
| `list_platform_policy_revisions` | One row per policy revision, forever |

### Naturally bounded

These need no limit, because something other than tenant growth caps them.

| Read | What caps it |
| --- | --- |
| `list_tenant_quotas` | The number of quota kinds |
| `list_action_runs_for_approval` | Runs attached to one approval |
| `list_agent_run_steps` | Steps in one run |
| `list_active_audit_legal_holds` | Active holds, an operator-scale set |
| `list_active_platform_policies_for_scope` | Active policies in one scope |
| `list_active_oidc_browser_sessions` | The per-actor concurrent-session cap |
| `list_platform_notification_acknowledgements` | Acknowledgements for one notification |

## The Catalog Read

`GET /data/assets` returns the assets named by the tenant's connector registry
— a single reference record, not a table scan. Its two supporting reads were
tenant-wide regardless:

- every current stewardship row for the tenant;
- a grouped observation count over every observation row for the tenant.

The projection then used only the entries whose asset id came from the
registry, so the surplus rows were read and discarded. The registry is now read
first, and both supporting reads are scoped to the asset ids the response will
contain. That is behaviour-preserving by construction: the discarded rows were
never part of the response.

## Measured Evidence

PostgreSQL 16, `EXPLAIN (ANALYZE, BUFFERS)`, single local container. Seeded
volumes: 200 tenants, 1.2M observation rows, 90k stewardship rows of which 30k
are current. The measured tenant holds 150 declared assets; its catalog
response contains 12.

Buffer counts and row counts are the stable figures. Timings are from a warm
single run on a developer machine and are indicative only.

### Stewardship read

| Variant | Index entries scanned | Rows returned | Shared buffers | Time |
| --- | --- | --- | --- | --- |
| Tenant-wide (before) | 450 | 150 | 397 | ~3.1 ms |
| Scoped to the response (after) | 36 | 12 | 69 | ~0.4 ms |

No new index was needed: the scoped predicate already matches the existing
`uq_data_asset_stewardship_tenant_asset_revision` index, which the tenant-wide
form could not use.

### Observation count read

| Variant | Index entries scanned | Rows aggregated | Shared buffers | Time |
| --- | --- | --- | --- | --- |
| Tenant-wide (before) | 6,000 | 6,000 | 208 | ~4.0 ms |
| Scoped, no composite index | 96,000 | 480 | 130 | ~3.7 ms |
| Scoped, composite index (after) | 480 | 480 | 48 | ~0.6 ms |

The middle row is why the index exists. With only the single-column `tenant_id`
and `asset_id` indexes the planner combines both with a `BitmapAnd`, and the
`asset_id` side matches every tenant holding the same asset id. Measured at 40
tenants it scanned 19,200 entries; at 200 tenants, 96,000 — linear in the
number of *other* tenants, while the requesting tenant's data was unchanged.
Scoping the query alone would therefore have replaced a tenant-proportional
read with a deployment-proportional one.

Migration `0065_data_asset_observation_tenant_asset_index` adds
`(tenant_id, asset_id)` on `data_asset_resource_observations`. It is the only
index this change adds, and it is added because the plans above show the
access shape changing, not because a composite index looked reasonable.

The migration uses PostgreSQL `CREATE INDEX CONCURRENTLY` outside the
transaction, following migration 0053, so the index build does not block
observation inserts, updates or deletes for the duration of the scan. The
build still uses I/O and can wait for other transactions. An interrupted
concurrent build can leave an invalid index: inspect its validity and recover
the index before rerunning the migration. Downgrade drops only this index
concurrently and retains observation data. See the
[PostgreSQL index-build guidance](https://www.postgresql.org/docs/16/sql-createindex.html#SQL-CREATEINDEX-CONCURRENTLY).

No data ever crossed a tenant boundary in either form; every variant filters on
`tenant_id`. The defect was cost coupling between tenants, not visibility.

## Verification

| Property | Test |
| --- | --- |
| Both supporting reads are scoped to the returned assets | `test_catalog_reads_are_bounded_to_the_returned_assets` |
| Rows for assets outside the catalog do not change the response, and every returned asset still resolves its stewardship and counts | `test_off_catalog_rows_do_not_change_the_catalog_response` |
| An empty catalog issues no read at all | `test_scoped_reads_return_nothing_without_asset_ids` |
| Asset ids are not a cross-tenant lookup key | `test_scoped_reads_stay_within_the_tenant` |

All live in `services/api/tests/test_data_assets.py`. The bounding test asserts
on the SQL actually sent to the database, so reintroducing a tenant-wide read
fails it.

`NOT RUN`: pagination for `list_connector_manifest_revisions` and
`list_platform_policy_revisions`. Both back responses that return a full
revision history, so bounding them changes those endpoints' public contracts.
That is a contract decision and belongs in its own reviewed change.

`NOT RUN`: `list_all_current_connector_manifests`.

`NOT RUN`: slow-query and pool-saturation telemetry. It is an observability
surface rather than a query-bounding change and is tracked separately.

`NOT RUN`: measurement on production-representative hardware, data
distribution and concurrency. The figures above come from one local container
with synthetic uniform data; they show the access shape changing, which is what
justified the index, and they are not a capacity statement.
