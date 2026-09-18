# Full-text search index projection

[#873](https://github.com/Limes-Labs/limes-axis/issues/873) (parent #343)
delivers the backend storage/indexing slice: committed ontology promotions and
normalized document observations can be projected into a rebuildable,
tenant-scoped full-text index. There is no user-facing search endpoint, no
embeddings and no query surface in this slice — retrieval authorization and
rebuild evidence belong to later children.

Two new modules:

* [`search_index.py`](../services/api/src/axis_api/search_index.py) — the
  vocabulary and the monotonic projection classifier.
* [`search_indexing.py`](../services/api/src/axis_api/search_indexing.py) —
  the procedure that turns committed revisions into classified index writes
  inside the caller's transaction.

## Index records

`search_index_records` (migration 0067) is a derived, data-bearing projection:
tenant, stable source identity (`tenant_id` + `source_object_id`, unique per
tenant), kind (`ontology_asset` | `document`), content revision, source
locator, state (`live` | `tombstoned`), bounded text, text digest, language and
analyzer revision, policy/ACL revision reference, index generation, and the
indexing audit reference. Database check constraints enforce the text/state
coherence (live rows carry text and digest; tombstones carry neither) and
generation bounds. Deleting or rebuilding rows never touches the ontology
store or source artifacts.

## Monotonicity: replay, out-of-order events and tombstones

`classify_index_update` is the single decision point:

* **New records** apply without extra evidence.
* **Equal content revisions** are idempotent replays — the index never changes.
* **Live-over-live with a different revision** requires the caller to bind
  real ordering evidence (`supersedes_current=True`, sourced from the actual
  source/ontology revision comparison). Without it the update is superseded
  (`missing_ordering_evidence`): fail-closed, never guessed, and a retry after
  re-reading the source is safe.
* **Tombstones always apply** (deletion is monotone) and clear text and digest.
  A tombstone can only be replaced by live content carrying bound ordering
  evidence; late out-of-order live events cannot resurrect deleted rows.

The read-modify-write is serialized per record by
`get_search_index_record_for_update()` (`SELECT … FOR UPDATE`), the same
pattern used by terminal state transitions in this repository, so concurrent
workers produce exactly one winner per record.

## Commitment boundary and bounded text

Only ontology promotions whose graph mutation status is
`type_db_mutation_applied` project text; deferred/failed/unavailable mutations
record a metadata-only audit event and project nothing. Searchable text is
derived deterministically from the operator-approved promotion field summary
(or supplied verbatim for documents) and capped at 20 000 characters —
oversized input and unsupported languages are reported with fixed codes
(`search_text_too_large`, `unsupported_search_language`), never silently
truncated as complete.

## Audit and redaction

Indexing evidence is metadata-only: decision, reason, generation, text digest,
character count, language and source identity. Text, digests of other tenants'
content and policy payloads never enter audit; the `redacted()` projection is
what operators see.

## Verification status

* PASS (SQLite contract engine) — `uv run pytest tests/test_search_index.py -q`
  in services/api: 21 tests covering bounds, language behavior, digest binding,
  the full monotonic classifier matrix, repository-backed projection
  lifecycle, tenant isolation and audit redaction.
* PASS — full API suite `uv run pytest -q`: 2 691 passed, 45 skipped.
* PASS — `tests/integration/test_search_index_postgres.py` syntax and skips
  verified locally; the live-PostgreSQL run (migration chain on a disposable
  database + concurrent-winner fencing) is opt-in via
  `AXIS_RUN_SEARCH_POSTGRES=1` and executes in CI's Integration job where
  Docker is available.
* Mock-only tests: the classifier matrix (`classify_index_update` tests) is
  pure-logic; all persistence tests run against a real SQLAlchemy engine.
