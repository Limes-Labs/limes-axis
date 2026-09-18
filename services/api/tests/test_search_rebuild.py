"""Conformance tests for the #875 index generation rebuild in bounded
maintenance mode, on top of the #873 projection and #874 query service.

Each test runs against its own isolated in-memory engine; the dedicated
live-PostgreSQL scenario is separately gated behind AXIS_RUN_SEARCH_POSTGRES=1.
Fixture corpus: 6 identities.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.db import session_scope
from axis_api.models import Base
from axis_api.persistence import AxisPersistenceRepository, TenantCreate
from axis_api.search_index import SearchableDocument
from axis_api.search_indexing import index_document_observation
from axis_api.search_queries import (
    SearcherAuthority,
    SearchQueryError,
    SearchQueryRequest,
    run_repository_search,
)
from axis_api.search_rebuild import (
    REBUILD_GENERATION_SWITCHED_EVENT,
    REBUILD_STARTED_EVENT,
    RebuildContext,
    RebuildItem,
    RebuildSource,
    SearchRebuildError,
    report_search_rebuild_evidence,
)

TENANT = "tenant_rebuild"
POLICY_REVISION = "policy-rev-1"
_CORPUS_SPEC = (
    ("ontology_asset", "asset-1", "promotion://p1", "Pump A quarterly output"),
    ("ontology_asset", "asset-2", "promotion://p2", "Pump B maintenance log"),
    ("ontology_asset", "asset-3", "promotion://p3", "Valve calibration sheet"),
    ("document", "doc-1", "doc://d1", "Shipping schedule overview"),
    ("document", "doc-2", "doc://d2", "Safety incident summary"),
    ("ontology_asset", "asset-revoked", "promotion://pr", "Secret revoked sentinel"),
)
CORPUS = [
    (kind, f"{TENANT}::{object_id}", "rev-1", locator, text)
    for kind, object_id, locator, text in _CORPUS_SPEC
]
SENTINEL = f"{TENANT}::asset-revoked"


def _corpus_items(skip_revoked=False):
    return [
        RebuildItem(
            kind=kind,
            source_object_id=object_id,
            content_revision=revision,
            source_locator=locator,
            searchable_text=text,
            policy_revision_ref=POLICY_REVISION,
        )
        for kind, object_id, revision, locator, text in CORPUS
        if not (skip_revoked and object_id == SENTINEL)
    ]


@pytest.fixture()
def factory():
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    yield sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    engine.dispose()


@pytest.fixture()
def repository(factory):
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        repo.create_tenant(
            TenantCreate(tenant_id=TENANT, display_name="Rebuild", description="", created_by="t")
        )
        yield repo


def _seed_active_generation(repository):
    """Build generation 1 through the real #873 projection procedure."""

    for kind, object_id, revision, locator, text in CORPUS:
        index_document_observation(
            repository,
            document=SearchableDocument(
                kind=kind,
                tenant_id=TENANT,
                source_object_id=object_id,
                content_revision=revision,
                source_locator=locator,
                searchable_text=text,
                language="en",
                analyzer_revision="axis-analyzer-v1",
                policy_revision_ref=POLICY_REVISION,
            ),
            index_generation=1,
        )
    repository.session.commit()  # seed transaction is durable before the rebuild


def _audit_create(event_type, payload):
    from axis_api.audit import AuditEventCreate

    return AuditEventCreate(
        tenant_id=TENANT, actor_id="fixture", event_type=event_type, payload=payload
    )


def _rebuild_source(repository, skip_revoked=False):
    watermark = repository.append_audit_event(
        _audit_create("rebuild.fixture.watermark", {"reason": "fixture"})
    )
    return RebuildSource(
        tenant_id=TENANT, watermark_event_id=watermark.id, items=_corpus_items(skip_revoked)
    )


def _authority(denied=()):
    return SearcherAuthority(
        tenant_id=TENANT,
        denied_identifiers=frozenset(denied),
        policy_revision_ref=POLICY_REVISION,
    )


def _run_full_rebuild(repository, source):
    context = RebuildContext(repository=repository, source=source)
    context.prepare()
    for item in source.items:
        context.build(item)
    return context.commit()


# --- AC 1: deterministic rebuild, no authoritative source mutation ---


def test_rebuild_reproduces_identities_and_revisions(repository, factory):
    _seed_active_generation(repository)
    _, _, generation_before = repository.list_search_index_records(
        tenant_id=TENANT, query_terms=[]
    )
    assert generation_before == 1

    outcome = _run_full_rebuild(repository, _rebuild_source(repository))
    assert outcome.decision == "switched"
    assert outcome.index_generation == 2
    assert outcome.identities == len(CORPUS)

    with session_scope(factory) as session:
        reloaded = AxisPersistenceRepository(session)
        records, next_offset, generation = reloaded.list_search_index_records(
            tenant_id=TENANT, query_terms=[]
        )
        assert generation == 2
        assert next_offset == 0
        assert len(records) == len(CORPUS)
        by_id = {record.source_object_id: record for record in records}
        for _kind, object_id, revision, _locator, text in CORPUS:
            record = by_id[object_id]
            assert record.state == "live"
            assert record.content_revision == revision
            assert record.index_generation == 2
            assert record.searchable_text == text
    # The rebuild emitted only index rows and index audit events: no
    # authoritative promotion or source artifact was touched.
    switch_events = repository.list_audit_events(
        TENANT, event_type=REBUILD_GENERATION_SWITCHED_EVENT
    )
    assert len(switch_events) == 1
    assert switch_events[0].payload["identities"] == len(CORPUS)


# --- AC 2: mid-rebuild update + revoke; switch carries current content only ---


def test_mid_rebuild_update_and_revocation_never_publishes_revoked_sentinel(repository):
    _seed_active_generation(repository)
    context = RebuildContext(repository=repository, source=_rebuild_source(repository))
    context.prepare()
    for item in _corpus_items():
        context.build(item)

    # One identity is updated and one revoked while the rebuild is running.
    index_document_observation(
        repository,
        document=SearchableDocument(
            kind="ontology_asset",
            tenant_id=TENANT,
            source_object_id=f"{TENANT}::asset-1",
            content_revision="rev-2",
            source_locator="promotion://p1",
            searchable_text="Pump A quarterly output revised",
            language="en",
            analyzer_revision="axis-analyzer-v1",
            policy_revision_ref=POLICY_REVISION,
        ),
        index_generation=1,
    )
    context.build(
        RebuildItem(
            kind="ontology_asset",
            source_object_id=f"{TENANT}::asset-1",
            content_revision="rev-2",
            source_locator="promotion://p1",
            searchable_text="Pump A quarterly output revised",
            policy_revision_ref=POLICY_REVISION,
        )
    )
    context.tombstone(source_object_id=SENTINEL, content_revision="rev-t")

    outcome = context.commit()
    assert outcome.decision == "switched"
    assert outcome.tombstoned == 1

    page = run_repository_search(
        repository,
        request=SearchQueryRequest(tenant_id=TENANT, query="pump"),
        authority=_authority(),
        searcher_ref="actor:searcher",
    )
    assert all(hit.source_object_id != SENTINEL for hit in page.hits)
    # The switch carries the current revision, never the pre-rebuild one: the
    # served record is at rev-2 under the fresh generation.
    record = repository.get_search_index_record_for_update(TENANT, f"{TENANT}::asset-1")
    assert record.content_revision == "rev-2"
    assert record.index_generation == 2
    sentinel = repository.get_search_index_record_for_update(TENANT, SENTINEL)
    assert sentinel.state == "tombstoned"


def test_commit_refuses_to_publish_a_still_live_revoked_sentinel(repository):
    _seed_active_generation(repository)
    # The corpus excludes the sentinel and the rebuild never carries its
    # tombstone: at commit time the sentinel is still live -> fail closed.
    source = _rebuild_source(repository, skip_revoked=True)
    context = RebuildContext(repository=repository, source=source)
    context.prepare()
    for item in source.items:
        context.build(item)
    with pytest.raises(SearchRebuildError) as error:
        context.commit()
    assert error.value.code == SearchRebuildError.REVOKED_SENTINEL


# --- AC 3: kill before/after switch; recovery is prior generation or retry ---


def test_kill_before_switch_leaves_active_generation_intact(repository, factory):
    _seed_active_generation(repository)
    context = RebuildContext(repository=repository, source=_rebuild_source(repository))
    context.prepare()
    for item in _corpus_items():
        context.build(item)
    # The rebuilder is killed mid-build: the whole (uncommitted) transaction
    # rolls back.
    repository.session.rollback()

    with session_scope(factory) as session:
        reloaded = AxisPersistenceRepository(session)
        _, _, generation = reloaded.list_search_index_records(tenant_id=TENANT, query_terms=[])
        assert generation == 1  # the valid prior generation keeps serving
        assert reloaded.list_audit_events(tenant_id=TENANT, event_type=REBUILD_STARTED_EVENT) == []


def test_retry_after_kill_yields_fresh_generation(repository, factory):
    _seed_active_generation(repository)
    context = RebuildContext(repository=repository, source=_rebuild_source(repository))
    context.prepare()
    for item in _corpus_items():
        context.build(item)
    repository.session.rollback()

    # Recovery: rerun the rebuild from scratch in a new transaction.
    with session_scope(factory) as session:
        reloaded = AxisPersistenceRepository(session)
        source = _rebuild_source(reloaded)
        context = RebuildContext(repository=reloaded, source=source)
        context.prepare()
        for item in source.items:
            context.build(item)
        outcome = context.commit()
    assert outcome.decision == "switched"
    with session_scope(factory) as session:
        reloaded = AxisPersistenceRepository(session)
        _, _, generation = reloaded.list_search_index_records(tenant_id=TENANT, query_terms=[])
        assert generation == 2


# --- AC 4: old-generation cursors cannot retrieve stale privileged content ---


def test_cursor_bound_to_old_generation_is_rejected_after_switch(repository):
    _seed_active_generation(repository)
    page = run_repository_search(
        repository,
        request=SearchQueryRequest(tenant_id=TENANT, query="pump", page_size=1),
        authority=_authority(),
        searcher_ref="actor:searcher",
    )
    assert page.next_cursor is not None

    _run_full_rebuild(repository, _rebuild_source(repository))

    with pytest.raises(SearchQueryError) as error:
        run_repository_search(
            repository,
            request=SearchQueryRequest(
                tenant_id=TENANT, query="pump", page_size=1, cursor=page.next_cursor
            ),
            authority=_authority(),
            searcher_ref="actor:searcher",
        )
    assert error.value.code == SearchQueryError.CURSOR_EXPIRED


# --- AC 5: failed/stalled rebuild must not look fresh ---


def test_failed_rebuild_reports_unavailable_not_ready(repository):
    _seed_active_generation(repository)
    source = _rebuild_source(repository, skip_revoked=True)
    context = RebuildContext(repository=repository, source=source)
    context.prepare()
    for item in source.items:
        context.build(item)
    with pytest.raises(SearchRebuildError):
        context.commit()
    context.abort(SearchRebuildError.REVOKED_SENTINEL)

    evidence = report_search_rebuild_evidence(repository, tenant_id=TENANT)
    assert evidence["status"] == "unavailable"
    assert evidence["index_generation"] == 2


def test_started_rebuild_without_switch_reports_rebuilding(repository):
    _seed_active_generation(repository)
    context = RebuildContext(repository=repository, source=_rebuild_source(repository))
    context.prepare()
    for item in _corpus_items():
        context.build(item)
    # Still mid-rebuild (no switch): the active generation stays fresh, but
    # the pending rebuild is visible as in-progress rather than hidden.
    evidence = report_search_rebuild_evidence(repository, tenant_id=TENANT)
    assert evidence["status"] == "rebuilding"
    assert evidence["index_generation"] == 2


def test_never_rebuilt_tenant_reports_not_applicable(repository):
    _seed_active_generation(repository)
    evidence = report_search_rebuild_evidence(repository, tenant_id=TENANT)
    assert evidence["status"] == "not_applicable"


def test_committed_rebuild_reports_ready_with_watermark(repository):
    _seed_active_generation(repository)
    source = _rebuild_source(repository)
    _run_full_rebuild(repository, source)

    evidence = report_search_rebuild_evidence(repository, tenant_id=TENANT)
    assert evidence["status"] == "ready"
    assert evidence["index_generation"] == 2
    assert evidence["source_watermark_event_id"] == str(source.watermark_event_id)


def test_pending_newer_rebuild_never_shadows_switched_generation(repository):
    _seed_active_generation(repository)
    _run_full_rebuild(repository, _rebuild_source(repository))

    stalled = RebuildContext(repository=repository, source=_rebuild_source(repository))
    stalled.prepare()
    evidence = report_search_rebuild_evidence(repository, tenant_id=TENANT)
    assert evidence["status"] == "ready"
    assert evidence["index_generation"] == 2


# --- AC 6: source-revocation fixture semantics (query-time denial vs lag) ---


def test_query_time_denial_is_independent_from_index_lag(repository):
    _seed_active_generation(repository)
    page = run_repository_search(
        repository,
        request=SearchQueryRequest(tenant_id=TENANT, query="sentinel"),
        authority=_authority(denied={SENTINEL}),
        searcher_ref="actor:searcher",
    )
    # The index still holds the (stale) text, but the current authority denial
    # keeps it out of the served hits: query-time enforcement over lag.
    assert all(hit.source_object_id != SENTINEL for hit in page.hits)


def test_generation_switch_is_recorded_exactly_once(repository):
    _seed_active_generation(repository)
    context = RebuildContext(repository=repository, source=_rebuild_source(repository))
    context.prepare()
    for item in _corpus_items():
        context.build(item)
    context.commit()
    with pytest.raises(SearchRebuildError):
        context.commit()
    switched = repository.list_audit_events(TENANT, event_type=REBUILD_GENERATION_SWITCHED_EVENT)
    assert len(switched) == 1
