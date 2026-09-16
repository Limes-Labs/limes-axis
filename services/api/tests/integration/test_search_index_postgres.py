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
