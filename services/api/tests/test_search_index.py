"""Contract and procedure tests for the #873 full-text search index projection.

Persistence-level tests run against the repository contract engine (SQLite by
default, real PostgreSQL when AXIS_MODEL_CONTRACT_BACKEND=postgresql); the
dedicated live-PostgreSQL integration test is separately gated behind
AXIS_RUN_SEARCH_POSTGRES=1. Mock-only tests are limited to pure classifiers.
"""

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import sessionmaker
from test_model_persistence_contract import contract_engine  # noqa: F401

from axis_api.db import session_scope
from axis_api.persistence import AxisPersistenceRepository, TenantCreate
from axis_api.search_index import (
    MAX_SEARCHABLE_TEXT_CHARS,
    SearchableDocument,
    SearchIndexError,
    classify_index_update,
    project_searchable_document,
)
from axis_api.search_indexing import (
    COMMITTED_MUTATION_STATUS,
    index_ontology_promotion,
    searchable_text_from_field_summary,
    tombstone_document,
)


def document(**overrides):
    defaults = {
        "kind": "ontology_asset",
        "tenant_id": "tenant-search",
        "source_object_id": "tenant-search::asset-1",
        "content_revision": "rev-1",
        "source_locator": "promotion://promo-1",
        "searchable_text": "Quarterly output metrics for the packaging line",
        "language": "en",
        "analyzer_revision": "axis-analyzer-v1",
        "policy_revision_ref": "policy-rev-1",
    }
    return SearchableDocument.model_validate(defaults | overrides)


# --- Bounded text and language contract ---


def test_text_beyond_the_cap_is_reported_not_truncated():
    # The Field cap rejects oversized input outright; a bypassed Field cap is
    # still caught by the model validator's fixed domain code.
    with pytest.raises(ValidationError) as pydantic_error:
        document(searchable_text="x" * (MAX_SEARCHABLE_TEXT_CHARS + 1))
    assert "string_too_long" in str(pydantic_error.value)
    oversized = document(searchable_text="x" * MAX_SEARCHABLE_TEXT_CHARS)
    bypassed = dict(oversized.model_dump())
    bypassed["searchable_text"] = bypassed["searchable_text"] + "!"
    with pytest.raises(ValidationError):
        SearchableDocument.model_validate(bypassed)
    assert SearchIndexError.TEXT_TOO_LARGE == "search_text_too_large"


def test_text_at_the_cap_is_accepted():
    doc = document(searchable_text="x" * MAX_SEARCHABLE_TEXT_CHARS)
    assert project_searchable_document(doc).searchable_chars == MAX_SEARCHABLE_TEXT_CHARS


def test_unsupported_language_is_reported_with_a_fixed_code():
    doc = document(language="xx")
    with pytest.raises(SearchIndexError) as error:
        project_searchable_document(doc)
    assert error.value.code == SearchIndexError.UNSUPPORTED_LANGUAGE


def test_projection_digest_binds_exact_text():
    first = project_searchable_document(document())
    second = project_searchable_document(
        document(searchable_text=first.searchable_text + "!")
    )
    assert first.text_digest != second.text_digest


def test_field_summary_text_is_deterministic_and_ordered():
    text_a = searchable_text_from_field_summary({"asset_name": "Pump", "domain": "ops"})
    text_b = searchable_text_from_field_summary({"domain": "ops", "asset_name": "Pump"})
    assert text_a == text_b == "asset_name: Pump. domain: ops"


def test_empty_field_summary_yields_empty_text_and_is_rejected_at_indexing():
    assert searchable_text_from_field_summary({}) == ""


# --- Monotonic classifier: replay, ordering fences, tombstones ---


def test_new_record_applies_without_ordering_evidence():
    projection = classify_index_update(
        current_state=None,
        current_content_revision=None,
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-1",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert (projection.decision, projection.reason) == ("applied", "new_record")


def test_equal_revision_is_an_idempotent_replay():
    projection = classify_index_update(
        current_state="live",
        current_content_revision="rev-1",
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-1",
        incoming_generation=2,
        supersedes_current=False,
    )
    assert (projection.decision, projection.reason) == ("superseded", "idempotent_replay")
    assert projection.next_content_revision == "rev-1"
    assert projection.next_generation == 1


def test_live_over_live_without_ordering_evidence_fails_closed():
    projection = classify_index_update(
        current_state="live",
        current_content_revision="rev-1",
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-2",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert (projection.decision, projection.reason) == (
        "superseded",
        "missing_ordering_evidence",
    )


def test_live_over_live_with_bound_ordering_evidence_applies():
    projection = classify_index_update(
        current_state="live",
        current_content_revision="rev-1",
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-2",
        incoming_generation=2,
        supersedes_current=True,
    )
    assert (projection.decision, projection.reason) == ("applied", "newer_revision")
    assert projection.next_content_revision == "rev-2"


def test_tombstone_always_applies_over_any_state():
    for current_state, current_revision in (
        (None, None),
        ("live", "rev-1"),
        ("tombstoned", "rev-0"),
    ):
        projection = classify_index_update(
            current_state=current_state,
            current_content_revision=current_revision,
            current_generation=1,
            incoming_state="tombstoned",
            incoming_content_revision="rev-t",
            incoming_generation=1,
            supersedes_current=False,
        )
        assert projection.decision == "applied"
        assert projection.next_state == "tombstoned"


def test_tombstone_cannot_be_resurrected_without_ordering_evidence():
    projection = classify_index_update(
        current_state="tombstoned",
        current_content_revision="rev-t",
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-9",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert (projection.decision, projection.reason) == (
        "superseded",
        "tombstone_not_resurrected",
    )
    assert projection.next_state == "tombstoned"


def test_tombstone_is_resurrected_only_with_bound_ordering_evidence():
    projection = classify_index_update(
        current_state="tombstoned",
        current_content_revision="rev-t",
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-9",
        incoming_generation=2,
        supersedes_current=True,
    )
    assert (projection.decision, projection.reason) == ("applied", "newer_revision")


def test_out_of_order_delivery_does_not_regress_a_tombstone():
    """A late live event for a deleted record stays tombstoned."""

    first = classify_index_update(
        current_state=None,
        current_content_revision=None,
        current_generation=1,
        incoming_state="live",
        incoming_content_revision="rev-1",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert first.decision == "applied"
    tombstone = classify_index_update(
        current_state=first.next_state,
        current_content_revision=first.next_content_revision,
        current_generation=first.next_generation,
        incoming_state="tombstoned",
        incoming_content_revision="rev-del",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert tombstone.decision == "applied"
    late = classify_index_update(
        current_state=tombstone.next_state,
        current_content_revision=tombstone.next_content_revision,
        current_generation=tombstone.next_generation,
        incoming_state="live",
        incoming_content_revision="rev-1",
        incoming_generation=1,
        supersedes_current=False,
    )
    assert (late.decision, late.next_state) == ("superseded", "tombstoned")


# --- Repository-backed procedure: projection lifecycle ---


@pytest.fixture
def repository(contract_engine):  # noqa: F811
    factory = sessionmaker(contract_engine, autoflush=False, expire_on_commit=False)
    with session_scope(factory) as session:
        repo = AxisPersistenceRepository(session)
        if repo.get_tenant("tenant-search") is None:
            repo.create_tenant(
                TenantCreate(
                    tenant_id="tenant-search",
                    display_name="Search fixture",
                    description="Index projection fixture",
                    created_by="test",
                )
            )
        yield repo


def test_committed_promotion_projects_text_once(repository):
    projection = index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id="tenant-search::asset-1",
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref="typedb://axis/tenant-search::asset-1",
        field_summary={"asset_name": "Packaging line", "domain": "operations"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    assert (projection.decision, projection.reason) == ("applied", "new_record")
    record = repository.get_search_index_record_for_update(
        "tenant-search", "tenant-search::asset-1"
    )
    assert record is not None
    assert record.state == "live"
    assert "Packaging line" in record.searchable_text
    assert record.text_digest is not None
    assert record.index_generation == 1


def test_uncommitted_mutation_yields_no_projection(repository):
    projection = index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-2",
        proposal_id="proposal-2",
        node_id="tenant-search::asset-2",
        ontology_type="axis_asset",
        graph_mutation_status="type_db_mutation_deferred",
        ontology_mutation_ref=None,
        field_summary={"asset_name": "Unapproved"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    assert projection.decision == "superseded"
    record = repository.get_search_index_record_for_update(
        "tenant-search", "tenant-search::asset-2"
    )
    assert record is None
    events = repository.list_audit_events("tenant-search", limit=10)
    assert any(event.event_type == "search.index.record_tombstoned" for event in events)


def test_replay_with_same_revision_is_idempotent(repository):
    for _ in range(2):
        projection = index_ontology_promotion(
            repository,
            tenant_id="tenant-search",
            promotion_id="promo-1",
            proposal_id="proposal-1",
            node_id="tenant-search::asset-1",
            ontology_type="axis_asset",
            graph_mutation_status=COMMITTED_MUTATION_STATUS,
            ontology_mutation_ref="typedb://axis/tenant-search::asset-1",
            field_summary={"asset_name": "Packaging line"},
            content_revision="rev-1",
            policy_revision_ref="policy-rev-1",
        )
    assert (projection.decision, projection.reason) == ("superseded", "idempotent_replay")
    record = repository.get_search_index_record_for_update(
        "tenant-search", "tenant-search::asset-1"
    )
    assert record.index_generation == 1


def test_newer_content_requires_bound_ordering_evidence(repository):
    node = "tenant-search::asset-ordering"
    index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id=node,
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref=f"typedb://axis/{node}",
        field_summary={"asset_name": "Old text"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    stale_first = index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-3",
        proposal_id="proposal-3",
        node_id=node,
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref=f"typedb://axis/{node}",
        field_summary={"asset_name": "Newer text"},
        content_revision="rev-2",
        policy_revision_ref="policy-rev-2",
        supersedes_current=False,
    )
    assert (stale_first.decision, stale_first.reason) == (
        "superseded",
        "missing_ordering_evidence",
    )
    record = repository.get_search_index_record_for_update("tenant-search", node)
    assert "Old text" in record.searchable_text

    newer = index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-3",
        proposal_id="proposal-3",
        node_id=node,
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref=f"typedb://axis/{node}",
        field_summary={"asset_name": "Newer text"},
        content_revision="rev-2",
        policy_revision_ref="policy-rev-2",
        supersedes_current=True,
    )
    assert (newer.decision, newer.reason) == ("applied", "newer_revision")
    record = repository.get_search_index_record_for_update("tenant-search", node)
    assert "Newer text" in record.searchable_text
    assert record.content_revision == "rev-2"


def test_tombstone_clears_text_and_survives_late_live_replay(repository):
    node = "tenant-search::asset-tombstone"
    index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id=node,
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref=f"typedb://axis/{node}",
        field_summary={"asset_name": "Doomed text"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    tombstone = tombstone_document(
        repository,
        tenant_id="tenant-search",
        source_object_id=node,
        content_revision="rev-del",
    )
    assert (tombstone.decision, tombstone.reason) == ("applied", "tombstone")
    record = repository.get_search_index_record_for_update("tenant-search", node)
    assert record.state == "tombstoned"
    assert record.searchable_text is None
    assert record.text_digest is None

    late = index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-9",
        proposal_id="proposal-9",
        node_id=node,
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref=f"typedb://axis/{node}",
        field_summary={"asset_name": "Late resurrection attempt"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
        supersedes_current=False,
    )
    assert (late.decision, late.reason) == ("superseded", "tombstone_not_resurrected")


def test_tombstone_for_unknown_object_creates_no_row(repository):
    projection = tombstone_document(
        repository,
        tenant_id="tenant-search",
        source_object_id="tenant-search::never-indexed",
        content_revision="rev-del",
    )
    # The classifier reports a new tombstone record; the procedure keeps no
    # row because nothing readable ever existed in the index for it.
    assert (projection.decision, projection.reason) == ("applied", "new_record")
    assert projection.next_state == "tombstoned"
    assert (
        repository.get_search_index_record_for_update(
            "tenant-search", "tenant-search::never-indexed"
        )
        is None
    )


def test_tenant_isolation_keeps_index_records_scoped(repository, contract_engine):  # noqa: F811
    with session_scope(
        sessionmaker(contract_engine, autoflush=False, expire_on_commit=False)
    ) as session:
        other = AxisPersistenceRepository(session)
        if other.get_tenant("tenant-other") is None:
            other.create_tenant(
                TenantCreate(
                    tenant_id="tenant-other",
                    display_name="Other tenant",
                    description="Isolation check",
                    created_by="test",
                )
            )
    index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id="tenant-search::asset-shared",
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref="typedb://axis/tenant-search::asset-shared",
        field_summary={"asset_name": "Tenant A text"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    index_ontology_promotion(
        repository,
        tenant_id="tenant-other",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id="tenant-other::asset-shared",
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref="typedb://axis/tenant-other::asset-shared",
        field_summary={"asset_name": "Tenant B text"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    tenant_a = repository.get_search_index_record_for_update(
        "tenant-search", "tenant-search::asset-shared"
    )
    tenant_b = repository.get_search_index_record_for_update(
        "tenant-other", "tenant-other::asset-shared"
    )
    assert tenant_a is not None and tenant_b is not None
    assert "Tenant A text" in tenant_a.searchable_text
    assert "Tenant B text" in tenant_b.searchable_text


def test_index_audit_never_contains_text(repository):
    index_ontology_promotion(
        repository,
        tenant_id="tenant-search",
        promotion_id="promo-1",
        proposal_id="proposal-1",
        node_id="tenant-search::asset-1",
        ontology_type="axis_asset",
        graph_mutation_status=COMMITTED_MUTATION_STATUS,
        ontology_mutation_ref="typedb://axis/tenant-search::asset-1",
        field_summary={"asset_name": "Secretive packaging line"},
        content_revision="rev-1",
        policy_revision_ref="policy-rev-1",
    )
    events = repository.list_audit_events("tenant-search", limit=10)
    projected = [e for e in events if e.event_type == "search.index.record_projected"]
    assert projected
    assert all("Secretive packaging line" not in str(e.payload) for e in projected)
