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
  searcher's current revision) cannot be re-evaluated and is omitted until it
  is re-indexed. Explicit current denials are omitted the same way: no hit,
  no identity, no facet, no count. A metadata-only hit would not be safe
  here, because its presence alone proves the restricted text matched the
  query.

## Guarantees

1. **No leak paths.** Any representation requires the current evaluation
   outcome to be positive. A permitted record without searchable text is the
   only metadata-only hit (`withheld_reason: not_textually_searchable`). Snippets are
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
4. **Continuations are re-authorized.** The cursor binds the tenant, the
   presenting searcher reference and the query/filter digest (as one digest),
   the effective policy revision (as a digest), the index generation, a
   resume position and an expiry (≤ 15 minutes). Its MAC key is a published
   constant, so the MAC detects corruption, not forgery, and the cursor is
   never an authority: every bound field is compared with the presenting
   request. Another principal's cursor or a changed query/filter is rejected
   (`search_cursor_invalid`); a policy-revision change or an index rebuild
   expires it (`search_cursor_expired`) instead of silently shifting
   results; the scope gate and per-candidate authorization re-run on every
   continuation.
5. **No repeated or skipped rows, no hidden-row count in the cursor.**
   Candidates are paged by keyset on the tenant-unique `source_object_id`,
   whose order does not depend on authorization. The cursor is readable by
   its holder, so its resume position is the last hit already emitted to
   the searcher, never an invisible candidate and never a count of them;
   the continuation re-examines (and again omits) invisible candidates
   after that hit. Invisible candidates do not shorten a page: the service
   scans further windows of `page_size + 1` candidates, at most four per
   request. A cursor is issued only when a further visible hit was seen, or
   when that scan budget ran out with candidates left. In that case the
   page is a bounded partial page, possibly empty; an empty page's cursor
   keeps its resume hit and adds one whole budget to a `skip` count
   (≤ 1 000 000), so every request makes progress. That budget case is the
   remaining existence signal about invisible candidates: it shows that a
   run of at least one budget minus the page size of matching candidates is
   invisible to the searcher, and nothing about any one record. Keyset
   paging also keeps concurrent inserts and tombstones from shifting rows
   between pages; only the `skip` part of a budget-exhausted cursor is
   positional.
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

`search:read` is not yet one of the canonical realm roles in
`axis_api.idp_bootstrap` or the local Keycloak realm. Until an operator
provisions it, IdP-backed callers receive 403. The route fails closed.

Query cost is not index-backed yet. Each candidate window is a case-folded
`LIKE` containment scan over the tenant's live rows, ordered by
`source_object_id` with `OFFSET`, plus one `max(index_generation)` aggregate.
That cost grows linearly with the tenant's index size and is bounded per
request only by the window budget above. Analyzer/`tsvector` or trigram
indexing is future work, and no capacity figure is claimed.
