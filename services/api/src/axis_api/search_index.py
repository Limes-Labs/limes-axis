"""Bounded full-text search index projection (issue #873; parent #343).

The index is a **derived, data-bearing projection** of already-committed
ontology promotions and normalized document observations — never a new source
of truth, a public cache, or a query surface. This module owns the index
record vocabulary and the monotonic projection state machine; actual
PostgreSQL persistence travels through ``AxisPersistenceRepository`` and the
existing transaction boundaries.

Core invariants:

* **Monotonic fencing**: an update is applied only when the caller binds real
  source ordering evidence (``supersedes_current=True``) or the record is
  new. Equal revisions are idempotent replays. A tombstone can be replaced
  only by a live revision carrying strictly newer ordering evidence, so late
  out-of-order events cannot resurrect deleted rows or overwrite newer text.
* **Authorization binding**: every record carries the policy/ACL revision it
  was indexed under. Retrieval authorization belongs to later children, but
  the projection never forgets which authorization evidence must be current
  before any text can be served.
* **Bounded text**: searchable text is capped at construction; unsupported
  language analyzers are reported explicitly with a fixed code rather than
  silently indexed as complete.
* **Rebuildability**: the projection is disposable. ``index_generation``
  exists so a rebuild can proceed under a fresh generation without mutating
  any authoritative ontology or source artifact.

No text or secret material appears in evidence or audit helpers.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest, Identifier
from pydantic import Field, model_validator

SEARCH_INDEX_ADAPTER = "axis-postgres-full-text-index"
SEARCH_INDEX_SCHEMA_VERSION = "1.0"

#: Maximum approved searchable text accepted per record, in characters.
MAX_SEARCHABLE_TEXT_CHARS = 20_000

IndexKind = Literal["ontology_asset", "document"]
IndexState = Literal["live", "tombstoned"]


class SearchIndexError(ValueError):
    """Fixed public-safe codes; text content and details are never attached."""

    TEXT_TOO_LARGE = "search_text_too_large"
    UNSUPPORTED_LANGUAGE = "unsupported_search_language"
    INVALID_RECORD = "invalid_search_index_record"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


SUPPORTED_LANGUAGES = frozenset({"en", "it", "de", "fr", "es", "simple"})


def validate_language(language: str) -> None:
    """Explicit analyzer contract; unknown languages are reported, not guessed."""

    if language not in SUPPORTED_LANGUAGES:
        raise SearchIndexError(SearchIndexError.UNSUPPORTED_LANGUAGE)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


class SearchableDocument(ContractModel):
    """One bounded, already-authorized text unit proposed for indexing.

    ``source_object_id`` must be the stable source/ontology identity (for
    ontology assets the tenant-namespaced graph key; for documents the #863
    digest key). ``content_revision`` is the opaque source revision the text
    was captured at; ``policy_revision_ref`` names the current authorization
    evidence the projection must respect.
    """

    kind: IndexKind
    tenant_id: Identifier
    source_object_id: Identifier
    content_revision: Identifier
    source_locator: str = Field(min_length=1, max_length=500)
    searchable_text: str = Field(min_length=1, max_length=MAX_SEARCHABLE_TEXT_CHARS)
    language: str = Field(min_length=2, max_length=12)
    analyzer_revision: Identifier
    policy_revision_ref: Identifier

    @model_validator(mode="after")
    def bounded_document(self) -> SearchableDocument:
        if len(self.searchable_text) > MAX_SEARCHABLE_TEXT_CHARS:
            raise SearchIndexError(SearchIndexError.TEXT_TOO_LARGE)
        return self


class SearchProjection(ContractModel):
    """The exact indexable payload for one document; text stays inside it."""

    kind: IndexKind
    searchable_text: str
    language: str
    analyzer_revision: Identifier
    text_digest: Digest
    searchable_chars: int = Field(ge=1, strict=True)


def project_searchable_document(document: SearchableDocument) -> SearchProjection:
    """Normalize one document into its indexable projection payload.

    Reports rather than silently truncating: oversized text fails at
    document construction and unsupported languages raise a fixed code here.
    The digest binds the exact text so a replay carrying different content
    under the same revision is a conflict, never a silent overwrite.
    """

    validate_language(document.language)
    return SearchProjection(
        kind=document.kind,
        searchable_text=document.searchable_text,
        language=document.language,
        analyzer_revision=document.analyzer_revision,
        text_digest=canonical_text_digest(document),
        searchable_chars=len(document.searchable_text),
    )


def canonical_text_digest(document: SearchableDocument) -> Digest:
    return hashlib.sha256(
        _canonical_json(
            {
                "kind": document.kind,
                "source_object_id": document.source_object_id,
                "content_revision": document.content_revision,
                "text": document.searchable_text,
            }
        ).encode("utf-8")
    ).hexdigest()


class IndexProjection(ContractModel):
    """The monotonic decision for one index update; no text is carried."""

    decision: Literal["applied", "superseded"]
    reason: Literal[
        "new_record",
        "newer_revision",
        "idempotent_replay",
        "older_revision",
        "tombstone",
        "tombstone_not_resurrected",
        "missing_ordering_evidence",
    ]
    next_state: IndexState
    next_content_revision: str | None
    next_generation: int = Field(ge=1, strict=True)


def classify_index_update(
    *,
    current_state: IndexState | None,
    current_content_revision: str | None,
    current_generation: int,
    incoming_state: IndexState,
    incoming_content_revision: str,
    incoming_generation: int,
    supersedes_current: bool,
) -> IndexProjection:
    """Monotonic classification for one index event.

    Source revisions are opaque: equality means replay, difference means the
    caller must bind real ordering evidence (``supersedes_current``) before a
    live update can replace live content. ``missing_ordering_evidence`` is the
    fail-closed answer for different-revision live-over-live updates without
    that binding — retry after re-reading the source, never guess. Tombstones
    always apply (deletions are monotone), and only strictly newer ordering
    evidence can replace a tombstone with live content.
    """

    if current_state is None:
        return IndexProjection(
            decision="applied",
            reason="new_record",
            next_state=incoming_state,
            next_content_revision=incoming_content_revision,
            next_generation=incoming_generation,
        )
    if incoming_state == "tombstoned":
        return IndexProjection(
            decision="applied",
            reason="tombstone",
            next_state="tombstoned",
            next_content_revision=incoming_content_revision,
            next_generation=incoming_generation,
        )
    if incoming_content_revision == current_content_revision:
        return IndexProjection(
            decision="superseded",
            reason="idempotent_replay",
            next_state=current_state,
            next_content_revision=current_content_revision,
            next_generation=current_generation,
        )
    if current_state == "live":
        if not supersedes_current:
            return IndexProjection(
                decision="superseded",
                reason="missing_ordering_evidence",
                next_state=current_state,
                next_content_revision=current_content_revision,
                next_generation=current_generation,
            )
        return IndexProjection(
            decision="applied",
            reason="newer_revision",
            next_state="live",
            next_content_revision=incoming_content_revision,
            next_generation=incoming_generation,
        )
    # Tombstone on the record: only bound ordering evidence revives it.
    if not supersedes_current:
        return IndexProjection(
            decision="superseded",
            reason="tombstone_not_resurrected",
            next_state="tombstoned",
            next_content_revision=current_content_revision,
            next_generation=current_generation,
        )
    return IndexProjection(
        decision="applied",
        reason="newer_revision",
        next_state="live",
        next_content_revision=incoming_content_revision,
        next_generation=incoming_generation,
    )


class IndexProjectionOutcome(ContractModel):
    """Metadata-only evidence for indexing progress; no text, digests only."""

    tenant_id: Identifier
    source_object_id: Identifier
    decision: Literal["applied", "superseded"]
    reason: str
    index_generation: int = Field(ge=1, strict=True)
    content_revision: str | None
    text_digest: Digest | None = None
    error_code: str | None = None

    def redacted(self) -> dict:
        return self.model_dump(mode="json")
