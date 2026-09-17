"""Authorized full-text search over the #873 index projection (issue #874).

One query service in front of ``search_index_records``. The index stores
*index-time* authorization evidence; this module re-evaluates **current**
effective access at read time — index-time ACL references are optimization
and audit evidence, never perpetual read authority. A record indexed under
a policy revision that is no longer current can only be served as a
metadata-only hit until it is re-indexed under the current revision.

Core invariants:

* **No leak paths**: a record whose current effective access cannot be
  evaluated is omitted or served as a metadata-only hit, never as text.
  Restrictive metadata only ever narrows visibility — it never renders as
  text, a snippet, a label, a count, a facet or an error detail.
* **Authorization before representation**: tenant binding, resource kinds,
  filters and ACL re-evaluation all run *before* any user-visible
  representation is produced; totals and facets are computed over the
  already-authorized page subset only — never global counts with rows
  hidden afterwards.
* **Bounded by construction**: query length, page size and filter widths
  are capped at the request boundary with fixed public-safe codes.
* **Continuations are re-authorized**: the opaque cursor binds the query
  and filter digest, the searcher identity, index generation and a bounded
  expiry. Every continuation re-checks the caller's current authorization;
  another principal's cursor is not a valid credential, and an index
  rebuild under the cursor invalidates it instead of shifting results.
* **Freshness is explicit**: a result page reports the index generation
  and the policy revision it was served under; it never falls back to an
  unrestricted source query when the index is empty or stale.
* **No result cache**: cross-principal cache identity is the hard part of
  search; until there is a designed invalidation story there is no cache.

Output text is the stored plain bounded text (never raw marked-up source);
snippets return exact authorized spans without markup reconstruction.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import time
from collections.abc import Callable
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Identifier
from pydantic import Field, model_validator

from axis_api.identity import OidcPrincipal
from axis_api.models import SearchIndexRecord
from axis_api.persistence import AxisPersistenceRepository

SEARCH_QUERY_ADAPTER = "axis-postgres-full-text-query"
SEARCH_QUERY_SCHEMA_VERSION = "1.0"

#: Bounded query: long enough for phrases, useless beyond this.
MAX_QUERY_CHARS = 240

#: Bounded page: the largest authorized result page.
MAX_PAGE_SIZE = 25

#: Continuation cursors expire; a fresh query is always safe.
MAX_CURSOR_AGE_SECONDS = 15 * 60

#: Cursor HMAC key material is deployment-owned; the in-repo default keeps
#: the format testable. The security argument is the binding property, not
#: key secrecy: cursors are never credentials — they are re-authorized
#: against the presenting principal on every continuation.
CURSOR_SECRET = "axis-search-cursor-v1"

#: Deployment default for the *current* search ACL policy revision. Records
#: indexed under a different revision stay metadata-only until re-indexed.
DEFAULT_SEARCH_POLICY_REVISION = "search-policy:current"

_ALLOWED_KINDS: tuple[str, ...] = ("ontology_asset", "document")

#: The kinds a search request may target; unknown kinds are request errors.
SearchIndexKind = Literal["ontology_asset", "document"]

_SNIPPET_SPAN = 80

_WHITESPACE = re.compile(r"\s+")


class SearchQueryError(ValueError):
    """Fixed public-safe codes; query text and details are never attached."""

    EMPTY_QUERY = "search_query_empty"
    QUERY_TOO_LARGE = "search_query_too_large"
    INVALID_CURSOR = "search_cursor_invalid"
    CURSOR_EXPIRED = "search_cursor_expired"
    PAGE_TOO_LARGE = "search_page_too_large"
    FILTER_TOO_NARROW = "search_filter_too_narrow"
    FILTER_TOO_BROAD = "search_filter_too_broad"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _canonical_json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def _normalize_query(query: str) -> str:
    return _WHITESPACE.sub(" ", query).strip()


class SearchQueryRequest(ContractModel):
    """A typed, bounded search request. No DSL, no raw engine passthrough.

    ``kinds`` restricts the search to approved resource kinds; empty or
    unknown kinds are a request error, not an implicit allow-all.
    ``source_locator_contains`` narrows candidates by an opaque locator
    substring the searcher already knows; it never widens visibility.
    """

    tenant_id: Identifier
    query: str = Field(min_length=0, max_length=MAX_QUERY_CHARS + 1)
    kinds: tuple[SearchIndexKind, ...] | None = None
    source_locator_contains: str | None = Field(default=None, max_length=121)
    page_size: int = Field(default=10, ge=1, le=MAX_PAGE_SIZE + 1, strict=True)
    cursor: str | None = Field(default=None, max_length=600)

    @model_validator(mode="after")
    def bounded_request(self) -> SearchQueryRequest:
        normalized = _normalize_query(self.query)
        if not normalized:
            raise SearchQueryError(SearchQueryError.EMPTY_QUERY)
        if len(normalized) > MAX_QUERY_CHARS:
            raise SearchQueryError(SearchQueryError.QUERY_TOO_LARGE)
        if self.page_size > MAX_PAGE_SIZE:
            raise SearchQueryError(SearchQueryError.PAGE_TOO_LARGE)
        locator = self.source_locator_contains
        if locator is not None:
            if not locator.strip():
                raise SearchQueryError(SearchQueryError.FILTER_TOO_NARROW)
            if len(locator.strip()) > 120:
                raise SearchQueryError(SearchQueryError.FILTER_TOO_BROAD)
        if self.kinds is not None and len(self.kinds) == 0:
            raise SearchQueryError(SearchQueryError.FILTER_TOO_NARROW)
        object.__setattr__(self, "query", normalized)
        return self

    def query_terms(self) -> list[str]:
        """ANDed containment terms; the bounded subset of full-text needs."""

        return [term for term in self.query.split(" ") if term]

    def query_digest(self) -> str:
        """Digest of everything a continuation cursor must stay bound to."""

        return hashlib.sha256(
            _canonical_json(
                {
                    "kinds": sorted(self.kinds) if self.kinds is not None else None,
                    "locator": (
                        self.source_locator_contains.strip()
                        if self.source_locator_contains is not None
                        else None
                    ),
                    "query": self.query,
                }
            ).encode("utf-8")
        ).hexdigest()


class SearcherAuthority(ContractModel):
    """Current effective-access vocabulary the query service re-evaluates.

    ``tenant_id`` must equal the requested tenant (the caller's admission
    binding). ``resource_kinds`` names the kinds the searcher may currently
    read; a record of another kind is invisible. ``denied_identifiers`` and
    ``denied_locator_fragments`` carry *current* per-object denials; locator
    fragments are applied as case-insensitive containment on the stored
    locator and never rendered back to the searcher. Records whose captured
    ``policy_revision_ref`` differs from ``policy_revision_ref`` cannot be
    re-evaluated and are only ever served metadata-only.
    """

    tenant_id: Identifier
    resource_kinds: frozenset[str] = frozenset(_ALLOWED_KINDS)
    denied_identifiers: frozenset[str] = frozenset()
    denied_locator_fragments: frozenset[str] = frozenset()
    policy_revision_ref: Identifier

    def forbids(self, kind: str, source_object_id: str, source_locator: str) -> bool:
        lowered = source_locator.casefold()
        return (
            kind not in self.resource_kinds
            or source_object_id in self.denied_identifiers
            or any(fragment.casefold() in lowered for fragment in self.denied_locator_fragments)
        )


class IndexRecordView(ContractModel):
    """The minimal projection the service may see per candidate row.

    ``acl_permitted`` is the *current* evaluation outcome: ``True`` only
    when the record's captured policy revision is still current, ``False``
    on an explicit current denial, ``None`` when access cannot currently be
    evaluated. Only ``True`` rows may ever render text.
    """

    kind: SearchIndexKind
    tenant_id: Identifier
    source_object_id: Identifier
    source_locator: str
    searchable_text: str | None
    text_digest: str | None
    state: Literal["live", "tombstoned"]
    index_generation: int = Field(ge=0, strict=True)
    acl_permitted: bool | None = None


class SearchCandidatePage(ContractModel):
    """Raw rows fetched by the repository, plus the generation they came from."""

    records: list[IndexRecordView]
    index_generation: int = Field(ge=0, strict=True)
    has_more: bool


class SearchHit(ContractModel):
    """One user-visible hit; restricted records are metadata-only."""

    kind: SearchIndexKind
    source_object_id: Identifier
    source_locator: str
    snippet: str | None = None
    text_digest: str | None = None
    withheld_reason: Literal["access_not_evaluable", "not_textually_searchable"] | None = None

    @property
    def metadata_only(self) -> bool:
        return self.withheld_reason is not None


class SearchPageMetadata(ContractModel):
    """Counts/facets over the authorized page subset only; no global counts."""

    returned: int = Field(ge=0, strict=True)
    withheld: int = Field(ge=0, strict=True)
    facets: dict[str, int] = Field(default_factory=dict)


class SearchResultPage(ContractModel):
    """A bounded, authorized result page with explicit freshness."""

    hits: list[SearchHit]
    metadata: SearchPageMetadata
    next_cursor: str | None = None
    served_under_policy_revision: Identifier
    index_generation: int = Field(ge=0, strict=True)
    index_stale: bool = False


class SearchQueryResponse(SearchResultPage):
    """Public API response: the authorized page plus tenant binding."""

    tenant_id: Identifier


def _cursor_mac(payload: dict) -> str:
    return hmac.new(
        CURSOR_SECRET.encode("utf-8"),
        _canonical_json(payload).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def encode_search_cursor(
    *,
    tenant_id: str,
    searcher_ref: str,
    query_digest: str,
    index_generation: int,
    issued_at: int,
    offset: int,
) -> str:
    """Opaque, self-verifying continuation token.

    ``searcher_ref`` is an opaque caller identity string; the service never
    trusts it alone — every continuation re-runs authorization against the
    presenting principal and rejects the cursor on mismatch.
    """

    payload = {
        "generation": index_generation,
        "issued_at": issued_at,
        "offset": offset,
        "query": query_digest,
        "searcher": searcher_ref,
        "tenant": tenant_id,
    }
    return _canonical_json({"mac": _cursor_mac(payload), "payload": payload})


class SearchCursorBinding(ContractModel):
    """What a decoded cursor binds, plus the resume offset."""

    offset: int = Field(ge=0, strict=True)
    index_generation: int = Field(ge=0, strict=True)


def decode_search_cursor(
    cursor: str,
    *,
    tenant_id: str,
    searcher_ref: str,
    query_digest: str,
    now: int | None = None,
) -> SearchCursorBinding:
    """Return the bound offset and generation or raise a fixed-code error.

    Tenant, presenting searcher and query/filter digest must match exactly;
    expired cursors are rejected so revocation propagates without unbounded
    replay windows.
    """

    try:
        blob = json.loads(cursor)
        payload = blob["payload"]
        mac = blob["mac"]
        offset = payload["offset"]
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("offset")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR) from exc
    if not hmac.compare_digest(_cursor_mac(payload), str(mac)):
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR)
    if (
        payload.get("tenant") != tenant_id
        or payload.get("searcher") != searcher_ref
        or payload.get("query") != query_digest
    ):
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR)
    issued_at = payload.get("issued_at")
    current = int(time.time()) if now is None else now
    if (
        not isinstance(issued_at, int)
        or current - issued_at > MAX_CURSOR_AGE_SECONDS
        or issued_at > current + 60
    ):
        raise SearchQueryError(SearchQueryError.CURSOR_EXPIRED)
    generation = payload.get("generation")
    if not isinstance(generation, int) or isinstance(generation, bool) or generation < 0:
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR)
    return SearchCursorBinding(offset=offset, index_generation=generation)


def _snippet_for(text: str, query: str) -> str:
    """Exact authorized span around the first match; plain text only."""

    first = next((token for token in query.split(" ") if token), query)
    position = text.casefold().find(first.casefold())
    if position < 0:
        return text[:_SNIPPET_SPAN]
    start = max(0, position - _SNIPPET_SPAN // 2)
    end = min(len(text), position + len(first) + _SNIPPET_SPAN // 2)
    prefix = "…" if start > 0 else ""
    suffix = "…" if end < len(text) else ""
    return f"{prefix}{text[start:end]}{suffix}"


class SearchAuthorizationDenied(PermissionError):
    """Raised before any representation is produced; carries no details."""

    def __init__(self, code: str = "search_not_authorized") -> None:
        self.code = code
        super().__init__(code)


def run_authorized_search(
    request: SearchQueryRequest,
    *,
    authority: SearcherAuthority,
    fetch_page: Callable[[int, int], SearchCandidatePage],
    searcher_ref: str,
    now: int | None = None,
) -> SearchResultPage:
    """Execute one bounded, authorized search page.

    ``fetch_page`` is the host-supplied candidate provider
    ``(offset, limit) -> SearchCandidatePage`` — the repository stays the
    storage owner and this service owns authorization, representation and
    continuation. The service requests ``page_size + 1`` candidates per
    window, drops every candidate the current authority forbids, and emits
    at most ``page_size`` hits: metadata over the emitted subset only, and
    a continuation cursor only when a further candidate window exists.

    A live record whose current access cannot be evaluated
    (``acl_permitted`` not ``True``) is withheld as metadata-only; a record
    under an explicit current denial is invisible — no label, no facet, no
    hit. A tombstoned record is metadata-only so recent deletions stay
    legible without resurrecting text. A continuation cursor bound to an
    older index generation is expired, not silently shifted. Authorization
    failures raise before any representation exists.
    """

    if authority.tenant_id != request.tenant_id:
        raise SearchAuthorizationDenied()
    binding: SearchCursorBinding | None = None
    if request.cursor is not None:
        binding = decode_search_cursor(
            request.cursor,
            tenant_id=request.tenant_id,
            searcher_ref=searcher_ref,
            query_digest=request.query_digest(),
            now=now,
        )
    offset = binding.offset if binding is not None else 0
    candidates = fetch_page(offset, request.page_size + 1)
    if binding is not None and binding.index_generation != candidates.index_generation:
        raise SearchQueryError(SearchQueryError.CURSOR_EXPIRED)

    hits: list[SearchHit] = []
    withheld = 0
    facets: dict[str, int] = {}

    for record in candidates.records:
        if len(hits) == request.page_size:
            break
        if authority.forbids(record.kind, record.source_object_id, record.source_locator):
            continue
        if record.state == "tombstoned":
            hits.append(
                SearchHit(
                    kind=record.kind,
                    source_object_id=record.source_object_id,
                    source_locator=record.source_locator,
                    withheld_reason="not_textually_searchable",
                )
            )
            withheld += 1
            facets[record.kind] = facets.get(record.kind, 0) + 1
            continue
        if record.acl_permitted is False:
            # A current denial is invisible: no label, no facet, no hit.
            continue
        if record.acl_permitted is not True:
            # Access cannot currently be evaluated: text is never served,
            # even when the index happens to hold it.
            hits.append(
                SearchHit(
                    kind=record.kind,
                    source_object_id=record.source_object_id,
                    source_locator=record.source_locator,
                    withheld_reason="access_not_evaluable",
                )
            )
            withheld += 1
            facets[record.kind] = facets.get(record.kind, 0) + 1
            continue
        if record.searchable_text is None:
            hits.append(
                SearchHit(
                    kind=record.kind,
                    source_object_id=record.source_object_id,
                    source_locator=record.source_locator,
                    withheld_reason="not_textually_searchable",
                )
            )
            withheld += 1
            facets[record.kind] = facets.get(record.kind, 0) + 1
            continue
        hits.append(
            SearchHit(
                kind=record.kind,
                source_object_id=record.source_object_id,
                source_locator=record.source_locator,
                snippet=_snippet_for(record.searchable_text, request.query),
                text_digest=record.text_digest,
            )
        )
        facets[record.kind] = facets.get(record.kind, 0) + 1

    page_full = len(hits) == request.page_size
    more_candidates = candidates.has_more or len(candidates.records) > len(hits)
    next_cursor = None
    if page_full and more_candidates:
        next_cursor = encode_search_cursor(
            tenant_id=request.tenant_id,
            searcher_ref=searcher_ref,
            query_digest=request.query_digest(),
            index_generation=candidates.index_generation,
            issued_at=int(time.time()) if now is None else now,
            # Advance by the hits actually emitted: unemitted candidates in
            # this window are re-fetched next time — a denial consumes its
            # candidate silently, but no matching row is ever skipped.
            offset=offset + len(hits),
        )
    return SearchResultPage(
        hits=hits,
        metadata=SearchPageMetadata(
            returned=len(hits) - withheld, withheld=withheld, facets=facets
        ),
        next_cursor=next_cursor,
        served_under_policy_revision=authority.policy_revision_ref,
        index_generation=candidates.index_generation,
        index_stale=candidates.index_generation == 0,
    )


def index_record_view(
    record: SearchIndexRecord,
    *,
    current_policy_revision: str,
) -> IndexRecordView:
    """Project one persisted #873 row into the service's candidate view.

    The current-ACL evaluation available from persisted rows alone is the
    revision comparison: a record captured under the still-current policy
    revision is evaluable; any other revision cannot be re-evaluated here
    and is passed as ``None`` (metadata-only, never text). Explicit current
    denials belong to the caller's authority, not to this projection.
    """

    return IndexRecordView(
        kind=record.kind,
        tenant_id=record.tenant_id,
        source_object_id=record.source_object_id,
        source_locator=record.source_locator,
        searchable_text=record.searchable_text,
        text_digest=record.text_digest,
        state=record.state,
        index_generation=record.index_generation,
        acl_permitted=(
            True if record.policy_revision_ref == current_policy_revision else None
        ),
    )


def run_repository_search(
    repository: AxisPersistenceRepository,
    *,
    request: SearchQueryRequest,
    authority: SearcherAuthority,
    searcher_ref: str,
    now: int | None = None,
) -> SearchResultPage:
    """Repository-backed variant over the #873 storage methods.

    Same authorization contract as ``run_authorized_search``; the candidate
    provider is the persistence repository's bounded LIKE-projection page.
    ``searcher_ref`` (e.g. ``actor:<id>``) binds continuation cursors to the
    presenting principal, so another user's cursor is rejected before any
    fetch happens.
    """

    if authority.tenant_id != request.tenant_id:
        raise SearchAuthorizationDenied()

    def fetch(offset: int, limit: int) -> SearchCandidatePage:
        rows, next_offset, generation = repository.list_search_index_records(
            tenant_id=request.tenant_id,
            query_terms=request.query_terms(),
            kinds=(
                list(request.kinds)
                if request.kinds is not None
                else None
            ),
            locator_contains=(
                request.source_locator_contains.strip()
                if request.source_locator_contains is not None
                else None
            ),
            offset=offset,
            limit=limit,
        )
        views = [
            index_record_view(
                row,
                current_policy_revision=authority.policy_revision_ref,
            )
            for row in rows
        ]
        return SearchCandidatePage(
            records=views,
            index_generation=generation,
            has_more=next_offset > 0,
        )

    return run_authorized_search(
        request,
        authority=authority,
        fetch_page=fetch,
        searcher_ref=searcher_ref,
        now=now,
    )


def search_authority_for_principal(
    principal: OidcPrincipal,
    *,
    policy_revision_ref: str = DEFAULT_SEARCH_POLICY_REVISION,
) -> SearcherAuthority:
    """Build the route-level authority for an authenticated principal.

    Tenant binding comes from the verified principal. Per-object denials
    start empty: the deployed evaluation surface is the policy-revision
    comparison, and fail-closed withholding covers everything it cannot
    evaluate. Hosts with a live per-object ACL authority pass a richer
    authority instead.
    """

    return SearcherAuthority(
        tenant_id=principal.tenant_id,
        resource_kinds=frozenset(_ALLOWED_KINDS),
        denied_identifiers=frozenset(),
        denied_locator_fragments=frozenset(),
        policy_revision_ref=policy_revision_ref,
    )
