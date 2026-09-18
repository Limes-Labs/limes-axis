"""Hooking committed revisions into the search index projection (#873).

``search_index.py`` owns the vocabulary and the monotonic classifier; this
module owns the *procedure*: taking a committed ontology promotion or a
normalized document observation, deriving the bounded searchable text, and
applying the classified decision to the projection inside the caller's
transaction. The caller (API layer or worker) binds authorization and owns
the commit — this module performs no permission evaluation, no commit and no
external calls.

Fail-closed rules encoded here:

* Only committed promotion events whose graph mutation was actually applied
  (``type_db_mutation_applied``) yield text; deferred/failed/unavailable
  mutations yield nothing (AC: rollback or unapproved staged extraction
  yields no projection).
* Text is derived from the operator-approved field summary, bounded at
  construction; unsupported languages are reported with a fixed code.
* Ordering evidence must be bound by the caller for live-over-live updates;
  without it the update is superseded (fail-closed), never guessed.
* Audit evidence is metadata-only: digests, decisions and IDs — never text.
"""

from __future__ import annotations

from axis_api.audit import AuditEventCreate
from axis_api.persistence import (
    AxisPersistenceRepository,
    SearchIndexProjectionUpdate,
    SearchIndexRecordCreate,
)
from axis_api.search_index import (
    SEARCH_INDEX_ADAPTER,
    IndexProjection,
    SearchableDocument,
    SearchIndexError,
    classify_index_update,
    project_searchable_document,
)

# Only a promotion whose graph mutation verifiably landed may project text.
COMMITTED_MUTATION_STATUS = "type_db_mutation_applied"
INDEX_AUDIT_EVENT_TYPE = "search.index.record_projected"
TOMBSTONE_AUDIT_EVENT_TYPE = "search.index.record_tombstoned"


def searchable_text_from_field_summary(field_summary: dict) -> str:
    """Build bounded text from the approved promotion field summary.

    The field summary is already the operator-approved projection of the
    proposal (what promotion policy validated); joining its values in a
    stable order keeps the text deterministic for a given revision.
    """

    return ". ".join(
        f"{key}: {field_summary[key]}"
        for key in sorted(field_summary)
        if field_summary[key]
    )


def index_ontology_promotion(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    promotion_id: str,
    proposal_id: str,
    node_id: str,
    ontology_type: str,
    graph_mutation_status: str,
    ontology_mutation_ref: str | None,
    field_summary: dict,
    content_revision: str,
    policy_revision_ref: str,
    language: str = "en",
    analyzer_revision: str = "axis-analyzer-v1",
    index_generation: int = 1,
    supersedes_current: bool = False,
    audit_event_id=None,
) -> IndexProjection:
    """Project one committed ontology promotion; unapplied mutations yield none.

    Returns the monotonic projection decision. ``superseded`` outcomes leave
    the index untouched; ``applied`` outcomes write inside the caller's
    transaction.
    """

    if graph_mutation_status != COMMITTED_MUTATION_STATUS:
        # Deferred/failed/unavailable mutations are not authoritative facts;
        # projecting them would leak unapproved or unverified content.
        repository.append_audit_event(
            _audit_event_create(
                tenant_id=tenant_id,
                event_type=TOMBSTONE_AUDIT_EVENT_TYPE,
                payload={
                    "reason": "uncommitted_graph_mutation",
                    "promotion_id": promotion_id,
                    "graph_mutation_status": graph_mutation_status,
                },
            )
        )
        return IndexProjection(
            decision="superseded",
            reason="missing_ordering_evidence",
            next_state="live",
            next_content_revision=content_revision,
            next_generation=index_generation,
        )

    try:
        document = SearchableDocument(
            kind="ontology_asset",
            tenant_id=tenant_id,
            source_object_id=node_id,
            content_revision=content_revision,
            source_locator=ontology_mutation_ref or f"promotion://{promotion_id}",
            searchable_text=searchable_text_from_field_summary(field_summary),
            language=language,
            analyzer_revision=analyzer_revision,
            policy_revision_ref=policy_revision_ref,
        )
        if not document.searchable_text.strip():
            raise SearchIndexError(SearchIndexError.INVALID_RECORD)
        projection_data = project_searchable_document(document)
    except SearchIndexError as error:
        repository.append_audit_event(
            _audit_event_create(
                tenant_id=tenant_id,
                event_type=TOMBSTONE_AUDIT_EVENT_TYPE,
                payload={
                    "reason": "unsupported_projection_input",
                    "error_code": error.code,
                    "promotion_id": promotion_id,
                },
            )
        )
        return IndexProjection(
            decision="superseded",
            reason="missing_ordering_evidence",
            next_state="live",
            next_content_revision=content_revision,
            next_generation=index_generation,
        )

    return _apply_projection(
        repository,
        document=document,
        projection_data=projection_data,
        index_generation=index_generation,
        supersedes_current=supersedes_current,
        audit_event_id=audit_event_id,
        event_type=INDEX_AUDIT_EVENT_TYPE,
    )


def index_document_observation(
    repository: AxisPersistenceRepository,
    *,
    document: SearchableDocument,
    index_generation: int = 1,
    supersedes_current: bool = False,
    audit_event_id=None,
) -> IndexProjection:
    """Project one normalized, already-authorized document observation."""

    try:
        projection_data = project_searchable_document(document)
    except SearchIndexError as error:
        repository.append_audit_event(
            _audit_event_create(
                tenant_id=document.tenant_id,
                event_type=TOMBSTONE_AUDIT_EVENT_TYPE,
                payload={
                    "reason": "unsupported_projection_input",
                    "error_code": error.code,
                    "source_object_id": document.source_object_id,
                },
            )
        )
        return IndexProjection(
            decision="superseded",
            reason="missing_ordering_evidence",
            next_state="live",
            next_content_revision=document.content_revision,
            next_generation=index_generation,
        )

    return _apply_projection(
        repository,
        document=document,
        projection_data=projection_data,
        index_generation=index_generation,
        supersedes_current=supersedes_current,
        audit_event_id=audit_event_id,
        event_type=INDEX_AUDIT_EVENT_TYPE,
    )


def tombstone_document(
    repository: AxisPersistenceRepository,
    *,
    tenant_id: str,
    source_object_id: str,
    content_revision: str,
    index_generation: int = 1,
    audit_event_id=None,
) -> IndexProjection:
    """Apply an explicit deletion observation; tombstones are monotone.

    Deletions carry their own revision and need no ordering evidence: the
    classifier applies them over any current state, and only bound ordering
    evidence can ever replace them afterwards.
    """

    current = repository.get_search_index_record_for_update(tenant_id, source_object_id)
    projection = classify_index_update(
        current_state=current.state if current is not None else None,
        current_content_revision=current.content_revision if current is not None else None,
        current_generation=current.index_generation if current is not None else 1,
        incoming_state="tombstoned",
        incoming_content_revision=content_revision,
        incoming_generation=index_generation,
        supersedes_current=False,
    )
    audit = repository.append_audit_event(
        _audit_event_create(
            tenant_id=tenant_id,
            event_type=TOMBSTONE_AUDIT_EVENT_TYPE,
            payload={
                "adapter": SEARCH_INDEX_ADAPTER,
                "source_object_id": source_object_id,
                "decision": projection.decision,
                "reason": projection.reason,
                "index_generation": projection.next_generation,
            },
        )
    )
    if projection.decision == "superseded" or current is None:
        # A tombstone for an unknown object needs no row: nothing readable
        # ever existed in the index for that identity.
        return projection
    repository.apply_search_index_projection(
        current,
        SearchIndexProjectionUpdate(
            next_state=projection.next_state,
            next_content_revision=projection.next_content_revision,
            next_generation=projection.next_generation,
            searchable_text=None,
            text_digest=None,
            indexed_event_type=TOMBSTONE_AUDIT_EVENT_TYPE,
            indexed_audit_event_id=audit.id,
        ),
    )
    return projection


def _apply_projection(
    repository: AxisPersistenceRepository,
    *,
    document: SearchableDocument,
    projection_data,
    index_generation: int,
    supersedes_current: bool,
    audit_event_id,
    event_type: str,
) -> IndexProjection:
    current = repository.get_search_index_record_for_update(
        document.tenant_id, document.source_object_id
    )
    projection = classify_index_update(
        current_state=current.state if current is not None else None,
        current_content_revision=current.content_revision if current is not None else None,
        current_generation=current.index_generation if current is not None else 1,
        incoming_state="live",
        incoming_content_revision=document.content_revision,
        incoming_generation=index_generation,
        supersedes_current=supersedes_current,
    )
    audit = repository.append_audit_event(
        _audit_event_create(
            tenant_id=document.tenant_id,
            event_type=event_type,
            payload={
                "adapter": SEARCH_INDEX_ADAPTER,
                "source_object_id": document.source_object_id,
                "decision": projection.decision,
                "reason": projection.reason,
                "index_generation": projection.next_generation,
                "text_digest": projection_data.text_digest,
                "searchable_chars": projection_data.searchable_chars,
                "language": projection_data.language,
            },
        )
    )
    if projection.decision == "superseded":
        return projection
    if current is None:
        repository.create_search_index_record(
            SearchIndexRecordCreate(
                tenant_id=document.tenant_id,
                kind=document.kind,
                source_object_id=document.source_object_id,
                content_revision=document.content_revision,
                source_locator=document.source_locator,
                state="live",
                searchable_text=projection_data.searchable_text,
                text_digest=projection_data.text_digest,
                language=projection_data.language,
                analyzer_revision=projection_data.analyzer_revision,
                policy_revision_ref=document.policy_revision_ref,
                index_generation=projection.next_generation,
                indexed_event_type=event_type,
                indexed_audit_event_id=audit.id,
            )
        )
    else:
        repository.apply_search_index_projection(
            current,
            SearchIndexProjectionUpdate(
                next_state=projection.next_state,
                next_content_revision=projection.next_content_revision,
                next_generation=projection.next_generation,
                searchable_text=projection_data.searchable_text,
                text_digest=projection_data.text_digest,
                language=projection_data.language,
                analyzer_revision=projection_data.analyzer_revision,
                policy_revision_ref=document.policy_revision_ref,
                indexed_event_type=event_type,
                indexed_audit_event_id=audit.id,
            ),
        )
    return projection


def _audit_event_create(tenant_id: str, event_type: str, payload: dict) -> AuditEventCreate:
    return AuditEventCreate(
        tenant_id=tenant_id,
        actor_id="axis-search-indexing",
        event_type=event_type,
        payload=payload,
    )
