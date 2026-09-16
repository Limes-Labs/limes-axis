# Microsoft 365 library discovery: endpoint support by permission mode

[#864](https://github.com/Limes-Labs/limes-axis/issues/864) delivers one
Microsoft-specific discovery adapter on top of the #863 document observation
contract:
[`connector_m365_discovery.py`](../services/api/src/axis_api/connector_m365_discovery.py).
It enumerates one explicitly configured SharePoint/OneDrive for Business library
over Microsoft Graph v1.0 and normalizes the permission evidence of each observed
item. It performs no content download, no delta persistence and no directory-wide
crawl, and it registers no source merely by importing the module: activation,
credential leases, egress policies and trust-layer authorization stay with their
existing owners.

The endpoint-by-permission-mode table below is the support contract the issue
requires. **Production support is unclaimed** until a real authorized tenant is
tested (see the limitations at the end): every behavior here is pinned by the
fake Graph provider tests in
[`test_connector_m365_discovery.py`](../services/api/tests/test_connector_m365_discovery.py),
not by a live tenant.

## Scope model

The operator selects one organizational tenant (Entra tenant ID), site and drive
— optionally narrowed to one folder — as an explicit
`M365LibrarySelection`. Nothing is discovered from source data: no site search,
no directory crawl, no drive listing. Every request is pinned to the
egress-approved origin, and every continuation link must stay inside the selected
drive before it is dialed; a scope-escaping link is a hard `resource_mismatch`
error, never a fetch.

Credentials are never handled by the adapter: the host resolves them server-side
through an executed credential lease and passes lease-scoped bearer material plus
a fail-closed `M365SourceAuthority` evidence pair (lease status, lease reference,
no-returned-secret evidence, expiry, approved private-endpoint egress mode with a
SHA-256 origin binding). Expired lease evidence, secret-material-reported
evidence, non-private egress modes and mismatched origin bindings are rejected at
construction, before any I/O.

## Endpoint support by permission mode

Graph permission modes are documented by Microsoft in the
[selected-scope overview](https://learn.microsoft.com/en-us/graph/permissions-selected-overview)
(reviewed 2026-09-14). The adapter supports exactly two modes and claims nothing
it cannot demonstrate through the fake provider:

| Endpoint (Graph v1.0) | Purpose | `selected_resource_grant` | `application_consent` | Not claimed |
| --- | --- | --- | --- | --- |
| `GET /drives/{drive-id}/root/children` | Enumerate the selected library root | Supported | Supported | — |
| `GET /drives/{drive-id}/items/{folder-id}/children` | Enumerate a selected subfolder | Supported | Supported | — |
| `GET /drives/{drive-id}/items/{item-id}/permissions` | Observe per-item permission evidence | Supported | Supported | — |
| Site search (`/sites?search=`), site collection enumeration, `/sites/{id}/drives` | Library discovery from source data | Not supported | Not supported | Never requested; the selection is explicit |
| `/delta` endpoints, `/content` streams | Change tracking, content download | Not supported | Not supported | Later Microsoft slices |
| `mail`, `teams`, calendar endpoints | Mail/Teams ingestion | Not supported | Not supported | Explicitly out of scope for #864 |
| User-delegated per-site delegated scopes (`Files.Read.Selected` family against arbitrary sites) | Narrower delegated mode | Not supported | Not supported | Never requested: the adapter does not silently ask for broader scopes when a narrower mode is unsupported |

Enumeration requests a bounded `$select` projection
(`id,name,folder,file,parentReference,eTag,cTag`) with `$top` capped at 200 per
page. Permission observations request the bounded
`grantedToV2,grantedToIdentitiesV2,link,roles,inheritedFrom,shareId` projection.
Both surfaces honor the operator caps (`max_items`, `max_pages`) and report
explicit truncation when a cap stops the walk while a `@odata.nextLink` is still
pending — a truncated enumeration is never presented as complete.

## Setup states

Setup outcomes are fixed safe states, never raw Graph errors:

| Situation | Reported state |
| --- | --- |
| Enumeration and permission observation succeeded | `setup_ready` (with explicit `truncated` when capped) |
| The token was rejected (401) | `setup_token_rejected` |
| 403 on enumeration with the `consentRequired` Graph code, or any 403 while in `application_consent` mode | `setup_insufficient_consent` |
| 403 on enumeration in `selected_resource_grant` mode without a consent code | `setup_missing_selected_resource_grant` |
| The selected drive/folder no longer exists (404 on enumeration) | `setup_selected_resource_not_found` |
| The item permission surface rejects the request shape (400/405/501) | `setup_unsupported_permission_mode` |
| Transport failure, timeout, non-JSON payload, or any other status | `setup_source_unreachable` |

None of these states escalates anything: no scope is requested, no grant is
acquired and no state machine advances. Unreachable states keep the outcome
empty.

## Permission evidence normalization

Each observed item yields a #863 `DocumentACLObservation`:

* Direct `grantedToV2` user/group principals and `grantedToIdentitiesV2`
  membership lists become `user`/`group` grants in the source account namespace,
  with `inheritedFrom` preserved as the inheritance origin.
* Application principals record the connection service identity's own access and
  leave the observation `partial`: a Graph application's access is never an
  end-user entitlement.
* Organizational sharing links become `domain` grants and other links become
  `link` grants. Both are preserved as evidence and remain ineligible for
  baseline read authorization under the #863 contract — no organizational
  account is treated as universally authorized.
* Unresolvable permission shapes leave the observation `partial`.
* A permission surface blocked for the selected mode (403) or an item that
  vanished mid-enumeration (404) leaves the observation `unavailable` while the
  item itself stays observable with its metadata.
* Every observation produced by this adapter satisfies
  `ready_for_authorization(now) is False`: discovery never creates read
  authority. Mappings and trust-layer decisions remain with the existing
  permission owners.

Item display names stay inside snapshots for the host to persist; the
adapter's `evidence()` projection is metadata-only (counts, completeness
tallies, setup state, lease and policy IDs). Graph error messages, bearer
tokens, item names and principal IDs never enter evidence.

## Verification status

* PASS — `uv run pytest tests/test_connector_m365_discovery.py -q` (services/api):
  27 tests cover bounded enumeration with explicit truncation, zero-I/O gate
  failures, scope-pinned continuation links, per-mode setup states, grant
  normalization, gzip/non-JSON payload bounds, and evidence/redaction.
* Production support remains unclaimed until a real authorized tenant is tested
  against a private endpoint; the fake provider cannot demonstrate tenant
  consent behavior, real scope semantics or Graph API version drift.

## Existing owners and exclusions

Source activation (`connector_source_activation.py`), credential leases
(`connector_credential_leases.py`), secret resolution
(`connector_secret_resolution.py`) and egress policy enforcement
(`connector_egress_policies.py`) remain the authority for everything the adapter
receives as evidence. Identity lifecycle stays under #330/#727; content
ingestion belongs to the next Microsoft slice; parsing/OCR to #493/#494;
query-time enforcement to #343.
