"""Search index projection against a real, migrated PostgreSQL database (#873).

Opt-in: requires the local Docker runtime with PostgreSQL on :5432 and
``AXIS_RUN_SEARCH_POSTGRES=1``. Creates a disposable database, runs the
alembic migration chain against it, and exercises concurrent-writer fencing
through the real row locks. Skipped otherwise (labeled: integration).
"""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from axis_api.db import session_scope
from axis_api.persistence import AxisPersistenceRepository, TenantCreate
from axis_api.search_indexing import (
    COMMITTED_MUTATION_STATUS,
    index_ontology_promotion,
)
from axis_api.search_queries import (
    SearchAuthorizationDenied,
    SearcherAuthority,
    SearchQueryRequest,
    run_repository_search,
)

pytestmark = [
    pytest.mark.integration,
    pytest.mark.skipif(
        os.environ.get("AXIS_RUN_SEARCH_POSTGRES") != "1",
        reason="isolated PostgreSQL opt-in",
    ),
]


@pytest.fixture(scope="module")
def migrated_postgres_engine():
    from sqlalchemy.engine import make_url

    database_url = make_url(os.environ["AXIS_SEARCH_POSTGRES_DSN"])
    assert database_url.get_backend_name() == "postgresql"
    database_name = f"axis_search_index_{uuid4().hex}"
    admin = create_engine(
        database_url.set(database="postgres"), isolation_level="AUTOCOMMIT", poolclass=NullPool
    )
    engine = None
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{database_name}"'))
        temporary_url = database_url.set(database=database_name).render_as_string(
            hide_password=False
        )
        engine = create_engine(temporary_url, poolclass=NullPool)
        os.environ["AXIS_POSTGRES_DSN"] = temporary_url
        from alembic import command
        from alembic.config import Config

        config = Config("alembic.ini")
        command.upgrade(config, "head")
        yield engine
    finally:
        os.environ.pop("AXIS_POSTGRES_DSN", None)
        if engine is not None:
            engine.dispose()
        with admin.connect() as connection:
            connection.execute(text(f'DROP DATABASE IF EXISTS "{database_name}"'))
        admin.dispose()


def _seed_tenant(engine, tenant_id):
    factory = sessionmaker(engine, autoflush=False, expire_on_commit=False)
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        if repo.get_tenant(tenant_id) is None:
            repo.create_tenant(
                TenantCreate(
                    tenant_id=tenant_id,
                    display_name=tenant_id,
                    description="Search index integration fixture",
                    created_by="test",
                )
            )
    return factory


def _index_once(factory, tenant_id, node, revision, text_value, *, supersedes):
    with session_scope(factory) as session:
        return index_ontology_promotion(
            AxisPersistenceRepository(session),
            tenant_id=tenant_id,
            promotion_id=f"promo-{revision}",
            proposal_id=f"proposal-{revision}",
            node_id=node,
            ontology_type="axis_asset",
            graph_mutation_status=COMMITTED_MUTATION_STATUS,
            ontology_mutation_ref=f"typedb://axis/{node}",
            field_summary={"asset_name": text_value},
            content_revision=revision,
            policy_revision_ref="policy-rev-1",
            supersedes_current=supersedes,
        )


def test_projection_on_real_postgres_survives_replay_and_tombstone(migrated_postgres_engine):
    engine = migrated_postgres_engine
    tenant_id = "tenant-search-pg"
    factory = _seed_tenant(engine, tenant_id)
    node = f"{tenant_id}::asset-1"

    first = _index_once(factory, tenant_id, node, "rev-1", "Old text", supersedes=False)
    assert (first.decision, first.reason) == ("applied", "new_record")

    replay = _index_once(factory, tenant_id, node, "rev-1", "Old text", supersedes=True)
    assert (replay.decision, replay.reason) == ("superseded", "idempotent_replay")

    newer = _index_once(factory, tenant_id, node, "rev-2", "New text", supersedes=True)
    assert (newer.decision, newer.reason) == ("applied", "newer_revision")

    with session_scope(factory) as session:
        record = AxisPersistenceRepository(session).get_search_index_record_for_update(
            tenant_id, node
        )
        assert record.state == "live"
        assert "New text" in record.searchable_text
        assert record.content_revision == "rev-2"


def test_concurrent_indexers_produce_exactly_one_winner(migrated_postgres_engine):
    engine = migrated_postgres_engine
    tenant_id = "tenant-search-pg-race"
    factory = _seed_tenant(engine, tenant_id)
    node = f"{tenant_id}::asset-race"

    def contender(index: int):
        with session_scope(factory) as session:
            return index_ontology_promotion(
                AxisPersistenceRepository(session),
                tenant_id=tenant_id,
                promotion_id=f"promo-race-{index}",
                proposal_id=f"proposal-race-{index}",
                node_id=node,
                ontology_type="axis_asset",
                graph_mutation_status=COMMITTED_MUTATION_STATUS,
                ontology_mutation_ref=f"typedb://axis/{node}",
                field_summary={"asset_name": f"Contender {index}"},
                content_revision=f"rev-{index}",
                policy_revision_ref="policy-rev-1",
                supersedes_current=False,
            )

    with ThreadPoolExecutor(max_workers=4) as pool:
        outcomes = list(pool.map(contender, range(4)))

    assert sum(1 for outcome in outcomes if outcome.decision == "applied") == 1
    assert all(outcome.decision in {"applied", "superseded"} for outcome in outcomes)


def test_authorized_search_on_real_postgres(migrated_postgres_engine):
    engine = migrated_postgres_engine
    tenant_id = "tenant-search-pg-query"
    factory = _seed_tenant(engine, tenant_id)
    node = f"{tenant_id}::asset-query"

    indexed = _index_once(
        factory,
        tenant_id,
        node,
        "rev-1",
        "Quality hold escalation pending for line two motors",
        supersedes=False,
    )
    assert indexed.decision == "applied"

    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        request = SearchQueryRequest(tenant_id=tenant_id, query="quality hold")
        authority = SearcherAuthority(
            tenant_id=tenant_id,
            policy_revision_ref="policy-rev-1",
        )
        page = run_repository_search(
            repository,
            request=request,
            authority=authority,
            searcher_ref="actor:pg-operator",
        )
        assert len(page.hits) == 1
        assert page.hits[0].source_object_id == node
        assert "Quality hold escalation" in page.hits[0].snippet
        # A wildcard-bearing query term must not bypass the LIKE escape.
        wildcard = run_repository_search(
            repository,
            request=SearchQueryRequest(tenant_id=tenant_id, query="quality hold %")
            .model_copy(),
            authority=authority,
            searcher_ref="actor:pg-operator",
        )
        assert wildcard.hits == []


def test_authorized_search_isolation_on_real_postgres(migrated_postgres_engine):
    engine = migrated_postgres_engine
    tenant_id = "tenant-search-pg-isolation"
    factory = _seed_tenant(engine, tenant_id)
    node = f"{tenant_id}::asset-private"

    indexed = _index_once(
        factory,
        tenant_id,
        node,
        "rev-1",
        "Isolation sentinel payload for tenant private data",
        supersedes=False,
    )
    assert indexed.decision == "applied"

    # A searcher bound to another tenant cannot aim the service at this
    # tenant, and the storage filter itself never returns foreign rows.
    with session_scope(factory) as session:
        repository = AxisPersistenceRepository(session)
        outsider = SearcherAuthority(
            tenant_id="tenant-search-pg-other",
            policy_revision_ref="policy-rev-1",
        )
        with pytest.raises(SearchAuthorizationDenied):
            run_repository_search(
                repository,
                request=SearchQueryRequest(tenant_id=tenant_id, query="isolation sentinel"),
                authority=outsider,
                searcher_ref="actor:outsider",
            )
        rows, _, _ = repository.list_search_index_records(
            tenant_id=tenant_id,
            query_terms=["isolation"],
            offset=0,
            limit=5,
        )
        assert rows == []


def test_generation_rebuild_on_real_postgres_rejects_old_cursors(
    migrated_postgres_engine,
):
    """#875 AC6: full rebuild over PostgreSQL; old cursors fail closed."""

    from axis_api.audit import AuditEventCreate
    from axis_api.search_queries import (
        SearcherAuthority,
        SearchQueryError,
        SearchQueryRequest,
        run_repository_search,
    )
    from axis_api.search_rebuild import RebuildContext, RebuildItem, RebuildSource

    engine = migrated_postgres_engine
    tenant_id = "tenant-search-pg-rebuild"
    factory = _seed_tenant(engine, tenant_id)
    node_a = f"{tenant_id}::asset-a"
    node_b = f"{tenant_id}::asset-b"
    _index_once(factory, tenant_id, node_a, "rev-1", "Pump alpha calibration", supersedes=False)
    _index_once(factory, tenant_id, node_b, "rev-1", "Pump beta pressure records", supersedes=False)

    # A pre-rebuild page mints a continuation cursor bound to generation 1.
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        authority = SearcherAuthority(tenant_id=tenant_id, policy_revision_ref="policy-rev-1")
        page = run_repository_search(
            repo,
            request=SearchQueryRequest(tenant_id=tenant_id, query="pump", page_size=1),
            authority=authority,
            searcher_ref="actor:rebuild",
        )
        assert page.index_generation == 1
        assert page.next_cursor is not None
    old_cursor = page.next_cursor

    # The rebuild reprojects both identities onto generation 2 and switches.
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        watermark = repo.append_audit_event(
            AuditEventCreate(
                tenant_id=tenant_id,
                actor_id="rebuild-test",
                event_type="rebuild.source.watermark",
                payload={"reason": "fixture"},
            )
        )
        source = RebuildSource(
            tenant_id=tenant_id,
            watermark_event_id=watermark.id,
            items=[
                RebuildItem(
                    kind="ontology_asset",
                    source_object_id=node_a,
                    content_revision="rev-1",
                    source_locator=f"typedb://axis/{node_a}",
                    searchable_text="Pump alpha calibration data",
                    policy_revision_ref="policy-rev-1",
                ),
                RebuildItem(
                    kind="ontology_asset",
                    source_object_id=node_b,
                    content_revision="rev-1",
                    source_locator=f"typedb://axis/{node_b}",
                    searchable_text="Pump beta pressure records",
                    policy_revision_ref="policy-rev-1",
                ),
            ],
        )
        context = RebuildContext(repository=repo, source=source)
        context.prepare()
        for item in source.items:
            context.build(item)
        outcome = context.commit()
    assert outcome.decision == "switched"
    assert outcome.index_generation == 2

    # The fresh generation serves the same authorized content...
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        authority = SearcherAuthority(tenant_id=tenant_id, policy_revision_ref="policy-rev-1")
        served = run_repository_search(
            repo,
            request=SearchQueryRequest(tenant_id=tenant_id, query="pump"),
            authority=authority,
            searcher_ref="actor:rebuild",
        )
        assert served.index_generation == 2
        assert {hit.source_object_id for hit in served.hits} == {node_a, node_b}
        # ...while the pre-rebuild cursor is rejected, never stale-paged.
        with pytest.raises(SearchQueryError) as error:
            run_repository_search(
                repo,
                request=SearchQueryRequest(
                    tenant_id=tenant_id, query="pump", page_size=1, cursor=old_cursor
                ),
                authority=authority,
                searcher_ref="actor:rebuild",
            )
        assert error.value.code == SearchQueryError.CURSOR_EXPIRED
