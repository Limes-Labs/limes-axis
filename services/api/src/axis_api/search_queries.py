"""Authorized full-text search over the #873 index projection (issue #874).

One query service in front of ``search_index_records``. The index stores
*index-time* authorization evidence; this module re-evaluates **current**
effective access at read time — index-time ACL references are optimization
and audit evidence, never perpetual read authority. A record indexed under
a policy revision that is no longer current is omitted until it is
re-indexed under the current revision.

Core invariants:

* **No leak paths**: a record whose current effective access is denied or
  cannot be evaluated is omitted — no text, snippet, identity, label,
  count, facet or error detail. (Even a metadata-only hit would prove that
  the restricted text matched the query.)
* **Authorization before representation**: tenant binding, resource kinds,
  filters and ACL re-evaluation all run *before* any user-visible
  representation is produced; totals and facets are computed over the
  already-authorized page subset only — never global counts with rows
  hidden afterwards.
* **Bounded by construction**: query length, page size and filter widths
  are capped at the request boundary with fixed public-safe codes.
* **Continuations are re-authorized**: the cursor binds the query and
  filter digest, the searcher identity, the effective policy revision, the
  index generation and a bounded expiry. Every continuation re-checks the
  caller's current authorization; another principal's cursor is not a valid
  credential, and a policy change or index rebuild under the cursor
  invalidates it instead of shifting results.
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

#: Candidate windows (each ``page_size + 1`` rows) scanned per request before
#: a partial page is returned with a continuation: bounded work when many
#: candidates are invisible to the searcher.
MAX_CANDIDATE_WINDOWS = 4

#: Upper bound on a continuation's skip count; larger values are rejected as
#: invalid instead of reaching the database as an OFFSET.
MAX_CURSOR_OFFSET = 1_000_000

#: Cursor MAC key. It is a published constant, not a secret: the MAC detects
#: accidental corruption only and the cursor is **not** an authority. Every
#: bound field that matters (tenant, searcher, query digest, policy revision,
#: generation) is compared against the presenting request on every
#: continuation, the skip is bounded, and authorization re-runs per
#: candidate, so a hand-crafted cursor can only choose where an already
#: authorized scan resumes. The cursor is readable by its holder, so it
#: carries no position that counts invisible candidates (see
#: ``run_authorized_search``).
CURSOR_SECRET = "axis-search-cursor-v2"

#: Deployment default for the *current* search ACL policy revision. Records
#: indexed under a different revision are omitted until re-indexed.
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
    re-evaluated and are omitted.
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
    evaluated. Only ``True`` rows produce any representation at all.
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
    """One user-visible hit; permitted records without text are metadata-only."""

    kind: SearchIndexKind
    source_object_id: Identifier
    source_locator: str
    snippet: str | None = None
    text_digest: str | None = None
    withheld_reason: Literal["not_textually_searchable"] | None = None

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


def _digest(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _cursor_binding_digest(*, tenant_id: str, searcher_ref: str, query_digest: str) -> str:
    return _digest({"query": query_digest, "searcher": searcher_ref, "tenant": tenant_id})


def encode_search_cursor(
    *,
    tenant_id: str,
    searcher_ref: str,
    query_digest: str,
    index_generation: int,
    issued_at: int,
    after: str | None = None,
    skip: int = 0,
    policy_revision_ref: str | None = None,
) -> str:
    """Opaque, self-verifying continuation token.

    ``searcher_ref`` is an opaque caller identity string; the service never
    trusts it alone — every continuation re-runs authorization against the
    presenting principal and rejects the cursor on mismatch. Tenant, searcher
    and query travel as one digest and the policy revision as another, so the
    token stays inside the published length bound.

    ``after`` is the identity of the last hit already emitted to this
    searcher (never an invisible candidate) and ``skip`` the number of
    candidates after it to pass over; ``skip`` is only ever a whole number of
    scan budgets, so it does not count individual invisible records.
    """

    payload = {
        "after": after,
        "bind": _cursor_binding_digest(
            tenant_id=tenant_id, searcher_ref=searcher_ref, query_digest=query_digest
        ),
        "generation": index_generation,
        "issued_at": issued_at,
        "policy": _digest(policy_revision_ref),
        "skip": skip,
    }
    return _canonical_json({"mac": _cursor_mac(payload), "payload": payload})


class SearchCursorBinding(ContractModel):
    """What a decoded cursor binds, plus the resume position."""

    after: str | None = None
    skip: int = Field(default=0, ge=0, strict=True)
    index_generation: int = Field(ge=0, strict=True)


def decode_search_cursor(
    cursor: str,
    *,
    tenant_id: str,
    searcher_ref: str,
    query_digest: str,
    policy_revision_ref: str | None = None,
    now: int | None = None,
) -> SearchCursorBinding:
    """Return the bound resume position and generation or a fixed-code error.

    Tenant, presenting searcher and query/filter digest must match exactly
    (``search_cursor_invalid``); a cursor minted under another effective
    policy revision or past its age is ``search_cursor_expired``.
    """

    try:
        blob = json.loads(cursor)
        payload = blob["payload"]
        mac = blob["mac"]
        skip = payload["skip"]
        after = payload["after"]
        if (
            not isinstance(skip, int)
            or isinstance(skip, bool)
            or skip < 0
            or skip > MAX_CURSOR_OFFSET
        ):
            raise ValueError("skip")
        if after is not None and (not isinstance(after, str) or not 0 < len(after) <= 200):
            raise ValueError("after")
    except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR) from exc
    if not hmac.compare_digest(_cursor_mac(payload), str(mac)):
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR)
    if payload.get("bind") != _cursor_binding_digest(
        tenant_id=tenant_id, searcher_ref=searcher_ref, query_digest=query_digest
    ):
        raise SearchQueryError(SearchQueryError.INVALID_CURSOR)
    if payload.get("policy") != _digest(policy_revision_ref):
        # The effective policy changed since the cursor was minted (for
        # example a revocation): continue only from a fresh query.
        raise SearchQueryError(SearchQueryError.CURSOR_EXPIRED)
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
    return SearchCursorBinding(after=after, skip=skip, index_generation=generation)


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


def _authorized_hit(
    record: IndexRecordView,
    *,
    authority: SearcherAuthority,
    query: str,
) -> SearchHit | None:
    """Current-authority projection of one candidate; ``None`` is invisible.

    Authorization runs before any representation exists. A forbidden kind,
    identity or locator, an explicit current denial (``acl_permitted`` is
    ``False``) and a record whose current access cannot be evaluated
    (``acl_permitted`` is ``None``) all produce no hit, no facet and no
    count: a metadata-only hit for a text match would itself prove that the
    restricted text contains the query terms. Only evaluable, permitted
    records reach representation; a permitted record without text is a
    metadata-only ``not_textually_searchable`` hit.
    """

    if authority.forbids(record.kind, record.source_object_id, record.source_locator):
        return None
    if record.acl_permitted is not True:
        return None
    if record.state == "tombstoned" or record.searchable_text is None:
        return SearchHit(
            kind=record.kind,
            source_object_id=record.source_object_id,
            source_locator=record.source_locator,
            withheld_reason="not_textually_searchable",
        )
    return SearchHit(
        kind=record.kind,
        source_object_id=record.source_object_id,
        source_locator=record.source_locator,
        snippet=_snippet_for(record.searchable_text, query),
        text_digest=record.text_digest,
    )


def run_authorized_search(
    request: SearchQueryRequest,
    *,
    authority: SearcherAuthority,
    fetch_page: Callable[[str | None, int, int], SearchCandidatePage],
    searcher_ref: str,
    now: int | None = None,
) -> SearchResultPage:
    """Execute one bounded, authorized search page.

    ``fetch_page`` is the host-supplied candidate provider
    ``(after, skip, limit) -> SearchCandidatePage``: up to ``limit``
    candidates strictly after the identity ``after`` (``None`` is the start)
    in the provider's stable identity order, passing over the first ``skip``.
    The repository stays the storage owner and this service owns
    authorization, representation and continuation. Candidate order is
    authorization-independent (the repository orders and filters by tenant,
    state and query only).

    The cursor is readable by its holder, so it never records a position
    that counts invisible candidates; the gap between two emitted hits
    would otherwise say how many restricted records match the query:

    * when one more visible hit is seen after the page filled, the cursor
      resumes after the last *emitted* hit, an identity the searcher already
      holds; the continuation re-examines (and again omits) any invisible
      candidates between it and the next visible hit;
    * invisible candidates do not shorten a page: further windows of
      ``page_size + 1`` candidates are scanned, up to
      ``MAX_CANDIDATE_WINDOWS`` per request;
    * when that scan budget runs out with candidates remaining, the page is
      a bounded partial page. If it emitted hits, the cursor resumes after
      the last one; if it emitted none, the cursor keeps its resume identity
      and adds one whole scan budget to ``skip``, so every request makes
      progress and ``skip`` only ever counts whole budgets.

    Metadata covers the emitted subset only. A continuation cursor bound to
    an older index generation or a different policy revision is expired, not
    silently shifted. Authorization failures raise before any representation
    exists.
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
            policy_revision_ref=authority.policy_revision_ref,
            now=now,
        )
    resume_after = binding.after if binding is not None else None
    resume_skip = binding.skip if binding is not None else 0
    scan_after, scan_skip = resume_after, resume_skip
    window_size = request.page_size + 1

    hits: list[SearchHit] = []
    withheld = 0
    facets: dict[str, int] = {}
    generation: int | None = None
    last_emitted: str | None = None
    examined = 0
    look_ahead = False
    exhausted = False

    for _ in range(MAX_CANDIDATE_WINDOWS):
        candidates = fetch_page(scan_after, scan_skip, window_size)
        if generation is None:
            generation = candidates.index_generation
            if binding is not None and binding.index_generation != generation:
                raise SearchQueryError(SearchQueryError.CURSOR_EXPIRED)
        elif candidates.index_generation != generation:
            # The index switched generation between windows of one request.
            raise SearchQueryError(SearchQueryError.CURSOR_EXPIRED)
        for record in candidates.records:
            hit = _authorized_hit(record, authority=authority, query=request.query)
            if hit is not None and len(hits) == request.page_size:
                # Look-ahead: a further visible hit exists.
                look_ahead = True
                break
            examined += 1
            if hit is None:
                continue
            hits.append(hit)
            last_emitted = record.source_object_id
            if hit.metadata_only:
                withheld += 1
            facets[hit.kind] = facets.get(hit.kind, 0) + 1
        if look_ahead:
            break
        if not candidates.has_more or not candidates.records:
            exhausted = True
            break
        # Internal progress only: never exposed in a cursor.
        scan_after, scan_skip = candidates.records[-1].source_object_id, 0

    next_cursor = None
    if look_ahead or not exhausted:
        if last_emitted is not None:
            cursor_after, cursor_skip = last_emitted, 0
        else:
            # Scan budget spent on invisible candidates only.
            cursor_after, cursor_skip = resume_after, resume_skip + examined
        next_cursor = encode_search_cursor(
            tenant_id=request.tenant_id,
            searcher_ref=searcher_ref,
            query_digest=request.query_digest(),
            index_generation=generation or 0,
            policy_revision_ref=authority.policy_revision_ref,
            issued_at=int(time.time()) if now is None else now,
            after=cursor_after,
            skip=cursor_skip,
        )
    return SearchResultPage(
        hits=hits,
        metadata=SearchPageMetadata(
            returned=len(hits) - withheld, withheld=withheld, facets=facets
        ),
        next_cursor=next_cursor,
        served_under_policy_revision=authority.policy_revision_ref,
        index_generation=generation or 0,
        index_stale=(generation or 0) == 0,
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
    and is passed as ``None`` (omitted, never text). Explicit current
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

    def fetch(after: str | None, skip: int, limit: int) -> SearchCandidatePage:
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
            after_source_object_id=after,
            offset=skip,
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
