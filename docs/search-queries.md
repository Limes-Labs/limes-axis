# Full-text search queries: bounded authorized results (#874)

[#874](https://github.com/Limes-Labs/limes-axis/issues/874) (parent #343) adds
the read side of the #873 index projection as one query service plus one
governed API/SDK surface:
[`services/api/src/axis_api/search_queries.py`](../services/api/src/axis_api/search_queries.py),
`GET /operations/search`, `AxisClient.search.query(...)`, and the public
`search-result-page.schema.json` contract. No UI (#346), no embeddings/RAG
(#344/#345), no search-engine passthrough, no new policy authority.

## What it is

- **One query service over #873 storage.** The repository owns the data and
  the bounded candidate window (tenant + state filters, ANDed containment
  terms with escaped LIKE, optional kind/locator narrowing); the service owns
  authorization, representation and continuation.
- **Authorization before representation.** Tenant binding, approved resource
  kinds, optional filters and ACL re-evaluation all run before anything
  user-visible is produced.
- **Current authority, not index-time authority.** Index-time ACL references
  are optimization and audit evidence. A record captured under a policy
  revision that is no longer current (`policy_revision_ref` differs from the
  searcher's current revision) cannot be re-evaluated and is served only as a
  metadata-only hit (`withheld_reason: access_not_evaluable`) until it is
  re-indexed. Explicit current denials are invisible: no hit, no facet, no
  label.

## Guarantees

1. **No leak paths.** Text requires the current evaluation outcome to be
   positive and the record to be live. A record whose access cannot be
   evaluated may appear as a metadata-only hit — never as text. Snippets are
   exact authorized spans of the stored plain text, never raw marked-up
   source. The sentinel matrix in `test_search_queries.py` asserts the
   restricted payload appears in no surface: hits, snippets, counts, facets,
   cursors or error details.
2. **Authorized subset accounting.** `metadata.returned`, `metadata.withheld`
   and `metadata.facets` cover the emitted authorized page only — never
   global counts with rows hidden afterwards.
3. **Bounded by construction.** Query ≤ 240 chars (whitespace-normalized),
   page ≤ 25, locator filter ≤ 120, one opaque cursor ≤ 600 chars; every
   violation is a fixed public-safe code (`search_query_too_large`,
   `search_page_too_large`, …), never an echo of the request.
4. **Continuations are re-authorized.** The cursor is an HMAC-bound opaque
   token carrying the tenant, the presenting searcher reference, the
   query/filter digest, the index generation and an expiry (≤ 15 minutes).
   Another principal's cursor is rejected (`search_cursor_invalid`), a
   changed query/filter invalidates it, an index rebuild invalidates it
   (`search_cursor_expired` rather than silently shifting results), and the
   scope gate re-runs on every continuation.
5. **No skipped rows.** The cursor advances by hits actually emitted;
   candidates withheld inside a window are re-fetched in the next window, so
   a denial that arrives mid-pagination never silently skips a matching row.
6. **Explicit freshness.** Every page carries the index generation and the
   policy revision it was served under. `index_stale` reports an empty
   generation; the service never falls back to unrestricted source queries.
7. **No result cache.** Cross-principal cache identity is the hard part of
   search; until there is a designed invalidation story there is no cache.

## Transport shape

`GET /operations/search?tenant_id=…&q=…&kind=document&locator=…&page_size=…&cursor=…`
(governed by the `search:read` scope, demo-mode convention included). The
Python SDK exposes `client.search.query(tenant_id, query, kinds=…, locator=…,
page_size=…, cursor=…)` for both sync and async clients, and the JSON Schema
package publishes `search-result-page.schema.json` as the language-neutral
contract, bound to the API by a package contract test.

## Current boundary

Authorization surfaces deployed today are the tenant binding, the approved
kind set and the policy-revision comparison; hosts with a live per-object ACL
authority pass a richer `SearcherAuthority` (per-object denials, locator
fragments) into the same service. The PostgreSQL-backed authorization cases
run in the opt-in integration module (`AXIS_RUN_SEARCH_POSTGRES=1`), which
additionally proves wildcard-bearing terms cannot bypass the LIKE escape and
that foreign tenants are rejected at both the service and storage layers.
