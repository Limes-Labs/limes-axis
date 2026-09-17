"""Contract tests for the #874 authorized search query service (#873 base)."""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from axis_api.config import Settings
from axis_api.db import session_scope
from axis_api.identity import OidcPrincipal
from axis_api.main import create_app
from axis_api.models import Base
from axis_api.persistence import (
    AxisPersistenceRepository,
    SearchIndexRecordCreate,
    TenantCreate,
)
from axis_api.search_queries import (
    MAX_CURSOR_AGE_SECONDS,
    MAX_PAGE_SIZE,
    MAX_QUERY_CHARS,
    IndexRecordView,
    SearchAuthorizationDenied,
    SearchCandidatePage,
    SearcherAuthority,
    SearchQueryError,
    SearchQueryRequest,
    decode_search_cursor,
    encode_search_cursor,
    run_authorized_search,
    run_repository_search,
    search_authority_for_principal,
)

TENANT_A = "tenant_search_alpha"
TENANT_B = "tenant_search_beta"
SENTINEL = "SENTINEL-must-never-leak-42"
CURRENT_REVISION = "search-policy:current"
OLD_REVISION = "search-policy:revoked-001"
DIGEST = "a" * 64


def _record(
    tenant_id: str,
    object_id: str,
    *,
    text: str | None,
    revision: str = CURRENT_REVISION,
    state: str = "live",
) -> SearchIndexRecordCreate:
    return SearchIndexRecordCreate(
        tenant_id=tenant_id,
        kind="document",
        source_object_id=object_id,
        content_revision="rev-1",
        source_locator=f"doc/{object_id}",
        state=state,
        searchable_text=text,
        text_digest=DIGEST if text is not None else None,
        language="en",
        analyzer_revision="analyzer-1",
        policy_revision_ref=revision,
        index_generation=1,
        indexed_event_type="search.index.record_projected",
        indexed_audit_event_id=None,
    )


def _view_record(object_id: str, text: str | None, revision: str) -> IndexRecordView:
    return IndexRecordView(
        kind="document",
        tenant_id=TENANT_A,
        source_object_id=object_id,
        source_locator=f"doc/{object_id}",
        searchable_text=text,
        text_digest=DIGEST if text is not None else None,
        state="live",
        index_generation=1,
        acl_permitted=True if revision == CURRENT_REVISION else None,
    )


def _seed(repository: AxisPersistenceRepository) -> None:
    repository.create_tenant(
        TenantCreate(tenant_id=TENANT_A, display_name="Alpha", description="", created_by="t")
    )
    repository.create_tenant(
        TenantCreate(tenant_id=TENANT_B, display_name="Beta", description="", created_by="t")
    )
    # Alpha corpus: one visible hit, one restricted (stale policy revision),
    # one explicit denial, one tombstone — all matching the same query.
    repository.create_search_index_record(
        _record(TENANT_A, "alpha_visible", text="quality hold on batch 42 line two")
    )
    repository.create_search_index_record(
        _record(
            TENANT_A,
            "alpha_restricted",
            text=f"quality hold restricted value {SENTINEL}",
            revision=OLD_REVISION,
        )
    )
    repository.create_search_index_record(
        _record(TENANT_A, "alpha_denied", text="quality hold denied record body")
    )
    repository.create_search_index_record(
        _record(TENANT_A, "alpha_tombstoned", text=None, state="tombstoned")
    )
    # Beta corpus holds the sentinel payload: no other tenant may see it.
    repository.create_search_index_record(
        _record(TENANT_B, "beta_sentinel", text=f"beta only payload {SENTINEL}")
    )


def _authority(
    principal: OidcPrincipal, denied: frozenset[str] = frozenset()
) -> SearcherAuthority:
    base = search_authority_for_principal(principal)
    return base.model_copy(update={"denied_identifiers": denied})


def _empty_page() -> SearchCandidatePage:
    return SearchCandidatePage(records=[], index_generation=1, has_more=False)


@pytest.fixture
def session_factory() -> sessionmaker:
    engine = create_engine(
        "sqlite+pysqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    with session_scope(factory) as session:
        _seed(AxisPersistenceRepository(session))
    yield factory
    engine.dispose()


# --- Request bounds: bounded predictable responses --------------------------


def test_request_rejects_empty_whitespace_and_oversized_queries() -> None:
    # Request-bound violations surface through the shared model validator
    # (pydantic wraps the fixed domain code) — same convention as #896.
    with pytest.raises(ValidationError) as empty:
        SearchQueryRequest(tenant_id=TENANT_A, query="   ")
    assert SearchQueryError.EMPTY_QUERY in str(empty.value)
    with pytest.raises(ValidationError) as large:
        SearchQueryRequest(tenant_id=TENANT_A, query="x" * (MAX_QUERY_CHARS + 1))
    assert SearchQueryError.QUERY_TOO_LARGE in str(large.value)


def test_request_rejects_huge_pages_and_degenerate_filters() -> None:
    with pytest.raises(ValidationError) as page:
        SearchQueryRequest(tenant_id=TENANT_A, query="quality", page_size=MAX_PAGE_SIZE + 1)
    assert SearchQueryError.PAGE_TOO_LARGE in str(page.value)
    with pytest.raises(ValidationError) as narrow:
        SearchQueryRequest(tenant_id=TENANT_A, query="quality", kinds=())
    assert SearchQueryError.FILTER_TOO_NARROW in str(narrow.value)
    with pytest.raises(ValidationError) as blank_locator:
        SearchQueryRequest(tenant_id=TENANT_A, query="quality", source_locator_contains="   ")
    assert SearchQueryError.FILTER_TOO_NARROW in str(blank_locator.value)
    with pytest.raises(ValidationError) as broad_locator:
        SearchQueryRequest(
            tenant_id=TENANT_A, query="quality", source_locator_contains="x" * 121
        )
    assert SearchQueryError.FILTER_TOO_BROAD in str(broad_locator.value)


def test_request_normalizes_whitespace_and_query_digest_is_stable() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="  quality   hold ")
    assert request.query == "quality hold"
    twin = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold")
    assert request.query_digest() == twin.query_digest()
    locator_request = SearchQueryRequest(
        tenant_id=TENANT_A, query="quality", source_locator_contains=" doc/1 "
    )
    locator_twin = SearchQueryRequest(
        tenant_id=TENANT_A, query="quality", source_locator_contains="doc/1"
    )
    assert locator_request.query_digest() == locator_twin.query_digest()


# --- Cursor binding: identity, query digest, generation, expiry --------------


def _cursor(
    request: SearchQueryRequest,
    *,
    searcher: str = "actor:alice",
    generation: int = 1,
    issued_at: int = 1_000,
    offset: int = 10,
) -> str:
    return encode_search_cursor(
        tenant_id=TENANT_A,
        searcher_ref=searcher,
        query_digest=request.query_digest(),
        index_generation=generation,
        issued_at=issued_at,
        offset=offset,
    )


def test_cursor_roundtrip_binds_searcher_query_and_generation() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold")
    binding = decode_search_cursor(
        _cursor(request, generation=3),
        tenant_id=TENANT_A,
        searcher_ref="actor:alice",
        query_digest=request.query_digest(),
        now=1_000 + MAX_CURSOR_AGE_SECONDS,
    )
    assert binding.offset == 10
    assert binding.index_generation == 3


def test_cursor_rejects_other_searcher_other_query_and_tampering() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold")
    cursor = _cursor(request)
    with pytest.raises(SearchQueryError) as wrong_user:
        decode_search_cursor(
            cursor,
            tenant_id=TENANT_A,
            searcher_ref="actor:mallory",
            query_digest=request.query_digest(),
            now=1_001,
        )
    assert wrong_user.value.code == SearchQueryError.INVALID_CURSOR
    other_query = SearchQueryRequest(tenant_id=TENANT_A, query="different query")
    with pytest.raises(SearchQueryError):
        decode_search_cursor(
            cursor,
            tenant_id=TENANT_A,
            searcher_ref="actor:alice",
            query_digest=other_query.query_digest(),
            now=1_001,
        )
    blob = json.loads(cursor)
    blob["payload"]["offset"] = 999
    with pytest.raises(SearchQueryError):
        decode_search_cursor(
            json.dumps(blob),
            tenant_id=TENANT_A,
            searcher_ref="actor:alice",
            query_digest=request.query_digest(),
            now=1_001,
        )


def test_cursor_expires_and_rejects_generation_changes() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold")
    cursor = _cursor(request, offset=0)
    with pytest.raises(SearchQueryError) as expired:
        decode_search_cursor(
            cursor,
            tenant_id=TENANT_A,
            searcher_ref="actor:alice",
            query_digest=request.query_digest(),
            now=1_000 + MAX_CURSOR_AGE_SECONDS + 1,
        )
    assert expired.value.code == SearchQueryError.CURSOR_EXPIRED
    authority = _authority(OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=[]))
    rebuilt = SearchCandidatePage(records=[], index_generation=2, has_more=False)
    with pytest.raises(SearchQueryError) as rebuild:
        run_authorized_search(
            request.model_copy(update={"cursor": cursor}),
            authority=authority,
            fetch_page=lambda offset, limit: rebuilt,
            searcher_ref="actor:alice",
            now=1_001,
        )
    assert rebuild.value.code == SearchQueryError.CURSOR_EXPIRED


# --- Service authorization: no leak paths ------------------------------------


def test_tenant_mismatch_raises_before_any_representation() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality")
    beta_authority = SearcherAuthority(
        tenant_id=TENANT_B, policy_revision_ref=CURRENT_REVISION
    )
    with pytest.raises(SearchAuthorizationDenied):
        run_authorized_search(
            request,
            authority=beta_authority,
            fetch_page=lambda offset, limit: _empty_page(),
            searcher_ref="actor:beta",
        )


def test_restricted_is_metadata_only_and_denied_is_invisible() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold", page_size=10)
    authority = _authority(
        OidcPrincipal(actor_id="bob", tenant_id=TENANT_A, scopes=[]),
        denied=frozenset({"alpha_denied"}),
    )
    page = run_authorized_search(
        request,
        authority=authority,
        fetch_page=lambda offset, limit: SearchCandidatePage(
            records=[
                _view_record(
                    "alpha_visible", "quality hold on batch 42 line two", CURRENT_REVISION
                ),
                _view_record(
                    "alpha_restricted", f"quality hold restricted value {SENTINEL}", OLD_REVISION
                ),
                _view_record("alpha_denied", "quality hold denied record body", CURRENT_REVISION),
            ],
            index_generation=1,
            has_more=False,
        ),
        searcher_ref="actor:bob",
    )
    by_id = {hit.source_object_id: hit for hit in page.hits}
    assert by_id["alpha_visible"].snippet is not None
    assert by_id["alpha_restricted"].withheld_reason == "access_not_evaluable"
    assert by_id["alpha_restricted"].snippet is None
    assert "alpha_denied" not in by_id
    assert page.metadata.returned == 1
    assert page.metadata.withheld == 1
    rendered = json.dumps(page.model_dump(mode="json"))
    assert SENTINEL not in rendered
    assert "alpha_denied" not in rendered


def test_tombstoned_record_is_metadata_only_without_text_resurrection() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold", page_size=10)
    record = IndexRecordView(
        kind="document",
        tenant_id=TENANT_A,
        source_object_id="alpha_tombstoned",
        source_locator="doc/alpha_tombstoned",
        searchable_text=None,
        text_digest=None,
        state="tombstoned",
        index_generation=1,
        acl_permitted=True,
    )
    page = run_authorized_search(
        request,
        authority=_authority(OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=[])),
        fetch_page=lambda offset, limit: SearchCandidatePage(
            records=[record], index_generation=1, has_more=False
        ),
        searcher_ref="actor:alice",
    )
    assert len(page.hits) == 1
    assert page.hits[0].withheld_reason == "not_textually_searchable"
    assert page.hits[0].snippet is None


def test_continuation_advances_by_emitted_hits_and_never_skips_rows() -> None:
    """A denial inside a window must not silently skip a matching row."""

    records = [
        _view_record(f"doc_{index}", f"quality hold item {index}", CURRENT_REVISION)
        for index in range(4)
    ]

    def fetch(offset: int, limit: int) -> SearchCandidatePage:
        window = records[offset : offset + limit]
        return SearchCandidatePage(
            records=window, index_generation=1, has_more=offset + limit < len(records)
        )

    authority = _authority(
        OidcPrincipal(actor_id="bob", tenant_id=TENANT_A, scopes=[]),
        denied=frozenset({"doc_2"}),
    )
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold", page_size=2)
    page_one = run_authorized_search(
        request, authority=authority, fetch_page=fetch, searcher_ref="actor:bob"
    )
    assert [hit.source_object_id for hit in page_one.hits] == ["doc_0", "doc_1"]
    page_two = run_authorized_search(
        request.model_copy(update={"cursor": page_one.next_cursor}),
        authority=authority,
        fetch_page=fetch,
        searcher_ref="actor:bob",
    )
    # doc_2 was denied inside window one's fetch and is re-fetched in
    # window two, where the denial keeps it invisible without skipping
    # doc_3 — no matching row silently disappears.
    assert [hit.source_object_id for hit in page_two.hits] == ["doc_3"]
    assert page_two.next_cursor is None


def test_query_digest_change_requires_fresh_cursor() -> None:
    request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold")
    cursor = _cursor(request, offset=2)
    narrowed = SearchQueryRequest(
        tenant_id=TENANT_A, query="quality hold", source_locator_contains="doc/1"
    )
    authority = _authority(OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=[]))
    with pytest.raises(SearchQueryError) as mismatch:
        run_authorized_search(
            narrowed.model_copy(update={"cursor": cursor}),
            authority=authority,
            fetch_page=lambda offset, limit: _empty_page(),
            searcher_ref="actor:alice",
        )
    assert mismatch.value.code == SearchQueryError.INVALID_CURSOR


# --- Repository-backed search -------------------------------------------------


def test_repo_search_withholds_stale_revision_and_explicit_denials(
    session_factory: sessionmaker,
) -> None:
    principal = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=[])
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        request = SearchQueryRequest(tenant_id=TENANT_A, query="quality hold", page_size=10)
        page = run_repository_search(
            repository,
            request=request,
            authority=_authority(principal, denied=frozenset({"alpha_denied"})),
            searcher_ref=f"actor:{principal.actor_id}",
        )
        by_id = {hit.source_object_id: hit for hit in page.hits}
        assert "alpha_visible" in by_id
        assert by_id["alpha_restricted"].withheld_reason == "access_not_evaluable"
        assert "alpha_denied" not in by_id
        assert page.index_generation == 1
        assert page.index_stale is False


def test_repo_search_never_crosses_tenant_boundary(session_factory: sessionmaker) -> None:
    principal = OidcPrincipal(actor_id="beta-user", tenant_id=TENANT_B, scopes=[])
    with session_scope(session_factory) as session:
        repository = AxisPersistenceRepository(session)
        request = SearchQueryRequest(tenant_id=TENANT_B, query=SENTINEL[:8], page_size=10)
        page = run_repository_search(
            repository,
            request=request,
            authority=_authority(principal),
            searcher_ref=f"actor:{principal.actor_id}",
        )
        assert [hit.source_object_id for hit in page.hits] == ["beta_sentinel"]
        # The Alpha searcher cannot aim the query service at Beta.
        alpha = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=[])
        with pytest.raises(SearchAuthorizationDenied):
            run_repository_search(
                repository,
                request=SearchQueryRequest(tenant_id=TENANT_B, query="beta only"),
                authority=_authority(alpha),
                searcher_ref=f"actor:{alpha.actor_id}",
            )


# --- Route: end-to-end through the API ---------------------------------------


class StaticIdentityVerifier:
    def __init__(self, principal: OidcPrincipal) -> None:
        self.principal = principal

    def verify_authorization_header(self, authorization: str | None) -> OidcPrincipal:
        assert authorization == "Bearer valid-token"
        return self.principal


def _build_app(session_factory: sessionmaker, principal: OidcPrincipal) -> FastAPI:
    app = create_app(Settings(postgres_dsn="sqlite+pysqlite://", oidc_auth_required=True))
    app.state.session_factory = session_factory
    app.state.identity_verifier = StaticIdentityVerifier(principal)
    return app


def _search(client: TestClient, principal: OidcPrincipal, params: dict) -> TestClient:
    return client.get(  # type: ignore[return-value]
        "/operations/search",
        headers={"Authorization": "Bearer valid-token"},
        params=params,
    )


def test_route_serves_authorized_pages_and_facets_over_subset(
    session_factory: sessionmaker,
) -> None:
    principal = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=["search:read"])
    client = TestClient(_build_app(session_factory, principal))
    response = _search(
        client, principal, {"tenant_id": TENANT_A, "q": "quality hold", "page_size": 2}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["tenant_id"] == TENANT_A
    # Tombstones never leave the repository (state = live only); the
    # stale-revision record is withheld as metadata-only.
    assert [hit["source_object_id"] for hit in body["hits"]] == [
        "alpha_visible",
        "alpha_restricted",
    ]
    assert body["hits"][0]["snippet"] == "quality hold on batch 42 line two"
    assert body["hits"][1]["snippet"] is None
    assert body["hits"][1]["withheld_reason"] == "access_not_evaluable"
    assert body["metadata"] == {"returned": 1, "withheld": 1, "facets": {"document": 2}}
    assert body["next_cursor"] is not None
    assert body["served_under_policy_revision"] == CURRENT_REVISION
    assert body["index_generation"] == 1
    assert body["index_stale"] is False


def test_route_pagination_continues_for_same_searcher_only(
    session_factory: sessionmaker,
) -> None:
    alice = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=["search:read"])
    client = TestClient(_build_app(session_factory, alice))
    params = {"tenant_id": TENANT_A, "q": "quality hold", "page_size": 2}
    first = _search(client, alice, params)
    cursor = first.json()["next_cursor"]
    second = _search(client, alice, {**params, "cursor": cursor})
    assert second.status_code == 200
    assert second.json()["next_cursor"] is None
    assert [hit["source_object_id"] for hit in second.json()["hits"]] == ["alpha_denied"]
    # The same cursor presented by another searcher is not a credential.
    mallory = OidcPrincipal(actor_id="mallory", tenant_id=TENANT_A, scopes=["search:read"])
    mallory_response = _search(
        TestClient(_build_app(session_factory, mallory)), mallory, {**params, "cursor": cursor}
    )
    assert mallory_response.status_code == 422
    assert mallory_response.json()["detail"]["reason"] == SearchQueryError.INVALID_CURSOR


def test_route_denies_cross_tenant_and_unauthenticated_callers(
    session_factory: sessionmaker,
) -> None:
    alice = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=["search:read"])
    client = TestClient(_build_app(session_factory, alice))
    headers = {"Authorization": "Bearer valid-token"}
    cross_tenant = client.get(
        "/operations/search", headers=headers, params={"tenant_id": TENANT_B, "q": "quality"}
    )
    assert cross_tenant.status_code == 403
    anonymous = client.get("/operations/search", params={"tenant_id": TENANT_A, "q": "quality"})
    assert anonymous.status_code == 401


def test_route_bound_error_matrix(session_factory: sessionmaker) -> None:
    alice = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=["search:read"])
    client = TestClient(_build_app(session_factory, alice))
    headers = {"Authorization": "Bearer valid-token"}
    base = {"tenant_id": TENANT_A, "q": "quality"}
    blank = client.get("/operations/search", headers=headers, params={**base, "q": "  "})
    assert blank.status_code == 422
    assert blank.json()["detail"]["reason"] == SearchQueryError.EMPTY_QUERY
    huge_page = client.get(
        "/operations/search", headers=headers, params={**base, "page_size": MAX_PAGE_SIZE + 1}
    )
    assert huge_page.status_code == 422
    bad_kind = client.get(
        "/operations/search", headers=headers, params={**base, "kind": "s3_bucket"}
    )
    assert bad_kind.status_code == 422
    garbage_cursor = client.get(
        "/operations/search", headers=headers, params={**base, "cursor": "garbage"}
    )
    assert garbage_cursor.status_code == 422
    assert garbage_cursor.json()["detail"]["reason"] == SearchQueryError.INVALID_CURSOR
    expired_cursor = _cursor(
        SearchQueryRequest(tenant_id=TENANT_A, query="quality"),
        generation=1,
        issued_at=1,
        offset=0,
    )
    expired = client.get(
        "/operations/search", headers=headers, params={**base, "cursor": expired_cursor}
    )
    assert expired.status_code == 422
    assert expired.json()["detail"]["reason"] == SearchQueryError.CURSOR_EXPIRED


def test_route_never_leaks_sentinel_across_any_surface(
    session_factory: sessionmaker,
) -> None:
    alice = OidcPrincipal(actor_id="alice", tenant_id=TENANT_A, scopes=["search:read"])
    client = TestClient(_build_app(session_factory, alice))
    responses = [
        _search(
            client,
            alice,
            {"tenant_id": TENANT_A, "q": "quality hold", "page_size": MAX_PAGE_SIZE},
        ),
        _search(
            client, alice, {"tenant_id": TENANT_A, "q": "quality", "kind": "ontology_asset"}
        ),
        _search(client, alice, {"tenant_id": TENANT_A, "q": SENTINEL}),
        _search(
            client,
            alice,
            {"tenant_id": TENANT_A, "q": "quality", "source_locator_contains": "beta"},
        ),
    ]
    for response in responses:
        assert SENTINEL not in response.text


# --- Static safety: the service has no source or network path ----------------


def test_search_queries_module_has_no_source_or_network_surface() -> None:
    module_path = (
        Path(__file__).resolve().parents[1] / "src" / "axis_api" / "search_queries.py"
    )
    tree = ast.parse(module_path.read_text())
    imported: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.append(node.module)
    forbidden = ("httpx", "requests", "socket", "subprocess", "urllib", "os")
    assert not any(name in forbidden for name in imported)
    assert not any(
        isinstance(node, ast.Call) and getattr(node.func, "id", None) == "open"
        for node in ast.walk(tree)
    )
