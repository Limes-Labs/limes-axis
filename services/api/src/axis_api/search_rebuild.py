"""Bounded index generation rebuild coordination (#875; parent #343).

``search_index.py`` owns the per-record monotonic classifier and
``search_indexing.py`` the inline projection procedure; this module owns the
*rebuild orchestration* on top of them. The chosen mode is deliberately
**bounded maintenance**: while a rebuild is prepared, queries keep reading the
currently active generation until one atomic transaction switches every
identity to the fresh generation. This slice does NOT claim online
zero-downtime rebuild from a live source — the corpus is an exported snapshot
whose authoritative revisions are reprojected verbatim.

Invariants (AC mapping in ``docs/search-rebuild-conformance.md``):

* **Generation isolation**: everything a rebuild writes carries one fresh
  ``index_generation`` computed at prepare time; the active generation is
  never mutated in place before the switch.
* **Watermark binding**: the rebuild refuses to switch without the declared
  authoritative source watermark (last accepted source event) recorded on the
  started event — no switch from an unbound fixture.
* **Atomic, validated switch**: ``commit`` re-reads the whole tenant inside
  the switch transaction and verifies every rebuild identity landed live at
  its declared revision and that no *other* identity remains live. A revoked
  or missing sentinel fails the switch (fixed code, nothing partially
  published) — the caller rolls back and the previous generation keeps
  serving.
* **Recovery is whole-transaction**: a killed rebuilder leaves either the
  fully valid prior generation or, after a retry from scratch, the fresh one.
  There is no mixed state because no rebuild transaction is ever partially
  committed.
* **Cursor honesty**: after a switch every record's ``index_generation``
  differs, so outstanding #874 continuation cursors bound to the old
  generation fail closed instead of paging stale privileged content.
* **Metadata-only evidence**: rebuild evidence travels as audit events
  carrying IDs, counts and codes — never text.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from axis_sdk.connector_authoring.contracts import ContractModel, Field, Identifier

from axis_api.persistence import AxisPersistenceRepository
from axis_api.search_index import MAX_SEARCHABLE_TEXT_CHARS, SearchableDocument
from axis_api.search_indexing import (
    index_document_observation,
    tombstone_document,
)

SEARCH_REBUILD_AUDIT_ACTOR = "axis-search-rebuild"
REBUILD_STARTED_EVENT = "search.rebuild.started"
REBUILD_GENERATION_SWITCHED_EVENT = "search.rebuild.generation_switched"
REBUILD_FAILED_EVENT = "search.rebuild.failed"


class SearchRebuildError(ValueError):
    """Fixed public-safe codes; corpus content is never attached."""

    NOT_STARTED = "search_rebuild_not_started"
    ALREADY_COMMITTED = "search_rebuild_already_committed"
    SOURCE_WATERMARK_MISSING = "search_rebuild_source_watermark_missing"
    EMPTY_SOURCE = "search_rebuild_empty_source"
    IDENTITY_MISMATCH = "search_rebuild_identity_mismatch"
    CONTENT_MISMATCH = "search_rebuild_content_mismatch"
    REVOKED_SENTINEL = "search_rebuild_revoked_sentinel"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


class RebuildItem(ContractModel):
    """One authoritative item of the exported corpus snapshot.

    ``searchable_text`` is the already-normalized bounded text the corpus
    builder derived from approved authoritative revisions — the rebuild
    reprojects it verbatim rather than re-deriving it.
    """

    kind: str
    source_object_id: Identifier
    content_revision: Identifier
    source_locator: str = Field(min_length=1, max_length=500)
    searchable_text: str = Field(min_length=1, max_length=MAX_SEARCHABLE_TEXT_CHARS)
    language: str = "en"
    analyzer_revision: Identifier = "axis-analyzer-v1"
    policy_revision_ref: Identifier


class RebuildSource(ContractModel):
    """The declared rebuild corpus plus its authoritative source watermark."""

    tenant_id: Identifier
    watermark_event_id: UUID
    items: list[RebuildItem]


class RebuildOutcome(ContractModel):
    """Metadata-only rebuild decision; no text, counts and codes only."""

    decision: str
    reason: str
    index_generation: int = Field(ge=0, strict=True)
    identities: int = Field(ge=0, strict=True)
    tombstoned: int = Field(ge=0, strict=True)
    error_code: str | None = None

    def redacted(self) -> dict:
        return self.model_dump(mode="json")


def _current_generation(repository: AxisPersistenceRepository, tenant_id: str) -> int:
    """The tenant's currently active index generation (stable aggregate)."""

    _, _, generation = repository.list_search_index_records(
        tenant_id=tenant_id, query_terms=[], offset=0, limit=1
    )
    return generation


@dataclass
class RebuildContext:
    """Prepare → build → commit orchestration for one tenant rebuild.

    Every write goes through the #873 projection procedure inside the
    caller's transaction; ``commit`` validates and records the atomic
    generation switch in that same transaction. Nothing here commits or
    rolls back — the caller owns the boundary (worker/API convention).
    """

    repository: AxisPersistenceRepository
    source: RebuildSource
    actor_id: str = SEARCH_REBUILD_AUDIT_ACTOR
    target_generation: int = field(default=0, init=False)
    _items: dict[str, RebuildItem] = field(default_factory=dict, init=False)
    _watermark_event_id: UUID | None = field(default=None, init=False)
    _prepared: bool = field(default=False, init=False)
    _committed: bool = field(default=False, init=False)

    def prepare(self) -> int:
        """Open the rebuild under a fresh generation and record the watermark."""

        if not self.source.items:
            raise SearchRebuildError(SearchRebuildError.EMPTY_SOURCE)
        self.target_generation = _current_generation(self.repository, self.source.tenant_id) + 1
        started = self.repository.append_audit_event(
            _audit_event(
                tenant_id=self.source.tenant_id,
                actor_id=self.actor_id,
                event_type=REBUILD_STARTED_EVENT,
                payload={
                    "reason": "rebuild_started",
                    "index_generation": self.target_generation,
                    "source_watermark_event_id": str(self.source.watermark_event_id),
                    "source_identities": len(self.source.items),
                },
            )
        )
        self._watermark_event_id = started.id
        self._prepared = True
        return self.target_generation

    def build(self, item: RebuildItem):
        """Reproject one corpus item into the fresh generation."""

        if not self._prepared:
            raise SearchRebuildError(SearchRebuildError.NOT_STARTED)
        if self._committed:
            raise SearchRebuildError(SearchRebuildError.ALREADY_COMMITTED)
        document = SearchableDocument(
            kind=item.kind,  # type: ignore[arg-type]
            tenant_id=self.source.tenant_id,
            source_object_id=item.source_object_id,
            content_revision=item.content_revision,
            source_locator=item.source_locator,
            searchable_text=item.searchable_text,
            language=item.language,
            analyzer_revision=item.analyzer_revision,
            policy_revision_ref=item.policy_revision_ref,
        )
        self._items[item.source_object_id] = item
        return index_document_observation(
            self.repository,
            document=document,
            index_generation=self.target_generation,
            # The corpus snapshot is the authoritative ordering evidence for
            # this identity: it was exported from committed revisions.
            supersedes_current=True,
        )

    def tombstone(self, *, source_object_id: str, content_revision: str):
        """Carry one deletion observation into the fresh generation."""

        if not self._prepared:
            raise SearchRebuildError(SearchRebuildError.NOT_STARTED)
        if self._committed:
            raise SearchRebuildError(SearchRebuildError.ALREADY_COMMITTED)
        self._items.pop(source_object_id, None)
        return tombstone_document(
            self.repository,
            tenant_id=self.source.tenant_id,
            source_object_id=source_object_id,
            content_revision=content_revision,
            index_generation=self.target_generation,
        )

    def commit(self) -> RebuildOutcome:
        """Validate and record the atomic generation switch (same transaction).

        Every prepared identity must now be live at its declared revision and
        every other identity tombstoned; anything else fails closed with a
        fixed code and the caller rolls the whole rebuild back.
        """

        if not self._prepared:
            raise SearchRebuildError(SearchRebuildError.NOT_STARTED)
        if self._committed:
            raise SearchRebuildError(SearchRebuildError.ALREADY_COMMITTED)
        if self._watermark_event_id is None:
            raise SearchRebuildError(SearchRebuildError.SOURCE_WATERMARK_MISSING)

        states = _tenant_index_state(self.repository, self.source.tenant_id)
        for object_id, item in self._items.items():
            state = states.get(object_id)
            if state is None:
                raise SearchRebuildError(SearchRebuildError.IDENTITY_MISMATCH)
            if state.state != "live" or state.content_revision != item.content_revision:
                raise SearchRebuildError(SearchRebuildError.CONTENT_MISMATCH)
        revoked = sorted(
            object_id
            for object_id, state in states.items()
            if object_id not in self._items and state.state == "live"
        )
        if revoked:
            raise SearchRebuildError(SearchRebuildError.REVOKED_SENTINEL)

        tombstoned = sum(1 for state in states.values() if state.state == "tombstoned")
        self.repository.append_audit_event(
            _audit_event(
                tenant_id=self.source.tenant_id,
                actor_id=self.actor_id,
                event_type=REBUILD_GENERATION_SWITCHED_EVENT,
                payload={
                    "reason": "generation_switch_committed",
                    "index_generation": self.target_generation,
                    "source_watermark_event_id": str(self.source.watermark_event_id),
                    "rebuild_started_event_id": str(self._watermark_event_id),
                    "identities": len(self._items),
                    "tombstoned": tombstoned,
                },
            )
        )
        self._committed = True
        return RebuildOutcome(
            decision="switched",
            reason="generation_switch_committed",
            index_generation=self.target_generation,
            identities=len(self._items),
            tombstoned=tombstoned,
        )

    def abort(self, reason: str) -> RebuildOutcome:
        """Record the failed rebuild; the caller rolls back the transaction."""

        self.repository.append_audit_event(
            _audit_event(
                tenant_id=self.source.tenant_id,
                actor_id=self.actor_id,
                event_type=REBUILD_FAILED_EVENT,
                payload={
                    "reason": reason,
                    "index_generation": self.target_generation,
                },
            )
        )
        return RebuildOutcome(
            decision="aborted",
            reason=reason,
            index_generation=self.target_generation,
            identities=0,
            tombstoned=0,
            error_code=reason,
        )


@dataclass(frozen=True)
class _IndexState:
    state: str
    content_revision: str


def _tenant_index_state(
    repository: AxisPersistenceRepository, tenant_id: str
) -> dict[str, _IndexState]:
    """Identity -> (state, revision) for every record, tombstones included."""

    return {
        record.source_object_id: _IndexState(
            state=record.state, content_revision=record.content_revision
        )
        for record in repository.list_search_index_states(tenant_id=tenant_id)
    }


def report_search_rebuild_evidence(
    repository: AxisPersistenceRepository, *, tenant_id: str
) -> dict:
    """Sanitized rebuild evidence from the audit boundary (AC: not-fresh fails).

    ``status`` describes the *rebuild* evidence, never a fabricated index
    health signal. ``ready`` means a generation switch was committed (its
    watermark and identity counts travel with the event); the currently
    supported generation is reported under ``index_generation``. A started
    generation without a switch yet is ``rebuilding`` (or ``unavailable``
    when its last attempt failed) and never reports the pending generation
    as supported; a newer in-flight attempt over an already-switched
    generation is surfaced as ``rebuild_in_progress`` without downgrading
    the supported generation's readiness.
    """

    started_events = repository.list_audit_events(
        tenant_id, event_type=REBUILD_STARTED_EVENT, limit=25
    )
    if not started_events:
        return {"status": "not_applicable", "reason": "no_rebuild_started"}
    started_generations = {
        int((event.payload or {}).get("index_generation", 0)) for event in started_events
    }
    switched: dict[int, dict] = {}
    for event in repository.list_audit_events(
        tenant_id, event_type=REBUILD_GENERATION_SWITCHED_EVENT, limit=25
    ):
        payload = event.payload or {}
        switched[int(payload.get("index_generation", 0))] = payload
    failed = {
        int((event.payload or {}).get("index_generation", 0))
        for event in repository.list_audit_events(
            tenant_id, event_type=REBUILD_FAILED_EVENT, limit=25
        )
    }
    latest_started = max(started_generations)
    if not switched:
        if latest_started in failed:
            return {
                "status": "unavailable",
                "reason": "rebuild_failed",
                "index_generation": latest_started,
            }
        return {
            "status": "rebuilding",
            "reason": "generation_awaiting_switch",
            "index_generation": latest_started,
        }
    supported_generation = max(switched)
    evidence = {
        "status": "ready",
        "reason": "generation_switch_committed",
        "index_generation": supported_generation,
        "source_watermark_event_id": switched[supported_generation].get(
            "source_watermark_event_id"
        ),
        "identities": switched[supported_generation].get("identities"),
    }
    if latest_started > supported_generation and latest_started not in failed:
        evidence["rebuild_in_progress"] = {"index_generation": latest_started}
    return evidence


def _audit_event(tenant_id: str, actor_id: str, event_type: str, payload: dict):
    from axis_api.audit import AuditEventCreate

    return AuditEventCreate(
        tenant_id=tenant_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=payload,
    )
