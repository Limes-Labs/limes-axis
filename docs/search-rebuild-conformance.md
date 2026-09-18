# Index generation rebuild: bounded maintenance conformance (#875)

[#875](https://github.com/Limes-Labs/limes-axis/issues/875) (parent #343) is
delivered as one rebuild/conformance slice:
[`services/api/src/axis_api/search_rebuild.py`](../services/api/src/axis_api/search_rebuild.py)
on top of the #873 projection ([#896](https://github.com/Limes-Labs/limes-axis/issues/896))
and the #874 query service ([#907](https://github.com/Limes-Labs/limes-axis/issues/907)).
No second search engine, no observability platform, no UI.

## Chosen mode: bounded maintenance (documented, not zero-downtime)

While a rebuild runs, queries keep reading the currently active generation.
The fresh generation becomes visible through **one atomic transaction** that
switches every identity at once. This slice does **not** claim online
zero-downtime rebuild from a live source: the corpus is an exported snapshot
whose authoritative revisions are reprojected verbatim
(`RebuildItem.searchable_text` is the already-normalized bounded text; the
rebuild never re-derives it). A dedicated live-catch-up mode is future work
and is deliberately not pretended here.

## Invariants

- **Generation isolation** — the rebuild computes one fresh
  `index_generation` at prepare time and never mutates the active generation
  in place before the switch.
- **Watermark binding** — `RebuildSource.watermark_event_id` is the declared
  last-accepted source event; `commit` records it on the generation-switched
  audit event. No switch without a declared watermark.
- **Atomic, validated switch** — `commit` re-reads the whole tenant index
  inside the switch transaction (`list_search_index_states`, tombstones
  included) and verifies: every rebuild identity live at its declared
  revision, every other identity tombstoned. Any drift fails closed with a
  fixed code (`identity_mismatch`, `content_mismatch`,
  `revoked_sentinel`) and the caller rolls back — nothing partially
  publishes, the previous generation keeps serving.
- **Recovery** — a killed rebuilder leaves either the fully valid prior
  generation or, after a from-scratch retry, the fresh one. No rebuild
  transaction is ever partially committed, so a mixed index cannot exist.
- **Cursor honesty** — after a switch every record carries the new
  generation, so #874 continuation cursors bound to the old generation
  fail closed (`search_cursor_expired`) instead of paging stale privileged
  content. Equal-revision re-projection under a strictly newer generation is
  the additive `generation_rebuild` reason in the #873 classifier; equal
  revisions at the same generation remain idempotent replays.
- **Metadata-only evidence** — rebuild evidence travels as audit events
  (`search.rebuild.started`, `search.rebuild.generation_switched`,
  `search.rebuild.failed`) carrying IDs, counts and codes, never text.

## Freshness / degraded evidence

`report_search_rebuild_evidence(repository, tenant_id=...)` reports:

| status | meaning |
| --- | --- |
| `ready` | a generation switch was committed; payload carries the supported generation, its source watermark and identity counts |
| `rebuilding` | a newer generation started but has not switched; the supported generation stays the last switched one |
| `unavailable` | the latest attempt failed; never fabricated as healthy |
| `not_applicable` | the tenant never rebuilt |

A pending newer rebuild is surfaced as `rebuild_in_progress` without
downgrading the supported generation's readiness; a failed attempt can never
look fresh.

## Tests

`services/api/tests/test_search_rebuild.py` maps the six acceptance
criteria on a 6-identity corpus (with a revoked sentinel): deterministic
rebuild identity/revision match (AC1), mid-rebuild update + revocation with
no revoked sentinel published (AC2), kill before switch + retry recovery
(AC3), old-generation cursor rejection (AC4), failed/stalled rebuild
evidence (AC5), and query-time denial independent of index lag (AC6). The
live-PostgreSQL scenario
(`tests/integration/test_search_index_postgres.py::test_generation_rebuild_on_real_postgres_rejects_old_cursors`)
exercises the full rebuild and old-cursor rejection on a migrated PG database.

## Reproducible run

```bash
cd services/api
uv run pytest tests/test_search_rebuild.py tests/test_search_index.py \
  tests/test_search_queries.py -q            # contract + conformance
AXIS_RUN_SEARCH_POSTGRES=1 \
AXIS_SEARCH_POSTGRES_DSN=postgresql://postgres:postgres@localhost:5432/postgres \
  uv run pytest tests/integration/test_search_index_postgres.py -q
```

Local run (2026-09-18, sqlite contract engine): 15 rebuild conformance tests
PASS; the PG scenario is NOT RUN locally (no local PostgreSQL/Docker) and
runs in CI.
