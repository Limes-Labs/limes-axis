# Google Drive corpus discovery: endpoint support by credential mode

[#866](https://github.com/Limes-Labs/limes-axis/issues/866) delivers one
Google-specific discovery adapter on top of the #863 document observation
contract:
[`connector_gdrive_discovery.py`](../services/api/src/axis_api/connector_gdrive_discovery.py).
It enumerates one explicitly configured My Drive root or shared drive over
Drive API v3 and normalizes the permission evidence of each observed item. It
performs no content download, no changes-cursor persistence and no
directory-wide crawl, and it registers no source merely by importing the
module: activation, credential leases, egress policies and trust-layer
authorization stay with their existing owners.

The endpoint-by-credential-mode table below is the support contract the issue
requires, together with the mock-versus-live evidence column. **Production
support is unclaimed** until a real authorized workspace is tested (see the
limitations at the end): every behavior here is pinned by the fake Drive
provider tests in
[`test_connector_gdrive_discovery.py`](../services/api/tests/test_connector_gdrive_discovery.py),
not by a live tenant.

## Scope model

The operator selects one provider account (service account or user identity),
a drive kind (`my_drive` or `shared_drive`), the concrete drive ID and one
explicit root item ID — never the `root` alias, which only resolves against
the credentialed user's My Drive and would silently enumerate the wrong
corpus if copied into another drive. Nothing is discovered from source data:
no drive listing, no `sharedWithMe` corpus, no directory crawl.

Every request is pinned to the egress-approved origin and built by the
adapter itself. Drive pagination carries opaque page tokens, not request
URLs, so source metadata cannot point this adapter at another origin, drive
or API surface; a token-shaped-URL or path-traversal item ID is rejected as a
fixed `resource_mismatch` before any follow-up request is built.

Credentials are never handled by the adapter: the host resolves them
server-side through an executed credential lease and passes lease-scoped
bearer material plus a fail-closed `GDriveSourceAuthority` evidence pair
(lease status, lease reference, no-returned-secret evidence, expiry,
approved private-endpoint egress mode with a SHA-256 origin binding). Expired
lease evidence, secret-material-reported evidence, non-private egress modes
and mismatched origin bindings are rejected at construction, before any I/O.

## Endpoint support by credential mode

Drive API v3 endpoints, as documented by Google in the
[Drive API reference](https://developers.google.com/workspace/drive/api/reference/rest/v3)
(reviewed 2026-09-14). The adapter supports exactly two credential modes and
claims nothing it cannot demonstrate through the fake provider:

| Endpoint (Drive API v3) | Purpose | `selected_resource_grant` | `application_consent` | Not claimed |
| --- | --- | --- | --- | --- |
| `GET /drive/v3/files` with `q='<root>' in parents`, `corpora=drive&driveId=` for shared drives | Enumerate the selected root (first page) | Supported | Supported | — |
| Same endpoint with `pageToken` | Continue bounded enumeration | Supported | Supported | — |
| `GET /drive/v3/files/{item-id}/permissions` | Observe per-item permission evidence | Supported | Supported | — |
| `GET /drive/v3/drives`, `files.list` over `sharedWithMe` or `allDrives` corpora | Drive discovery from source data | Not supported | Not supported | Never requested; the selection is explicit |
| `GET /drive/v3/files/{id}` on shortcut targets | Resolve shortcuts by fetching | Not supported | Not supported | Never requested: targets are preserved as metadata only and observed by the enumeration itself when in scope |
| `/export`, `/download`, `/content` streams | Content download | Not supported | Not supported | Later Google slices |
| `changes.list`, `startPageToken` | Change tracking | Not supported | Not supported | Slice #867 |
| Gmail, Calendar, People endpoints | Non-Drive ingestion | Not supported | Not supported | Explicitly out of scope for #866 |
| `Files.Read.Selected` user-delegated scopes against arbitrary folders | Narrower delegated mode | Not supported | Not supported | Never requested: the adapter does not silently ask for broader scopes when a narrower mode is unsupported |

Enumeration requests a bounded field projection
(`id,name,mimeType,parentReference,version,shortcutDetails`) with `pageSize`
capped at 200 per page; shared-drive selections additionally send
`corpora=drive&driveId=<registered drive>` so the walk is pinned to the
registered drive identity. Permission observations request
`id,type,emailAddress,domain` with `pageSize` capped at 100 (the Drive
maximum). Both surfaces honor the operator caps (`max_items`, `max_pages`)
and report explicit truncation when a cap stops the walk while a
`nextPageToken` is still pending — a truncated enumeration is never
presented as complete, and truncation never implies deletion: the outcome
carries no tombstones.

## Setup states

Setup outcomes are fixed safe states, never raw Drive errors:

| Situation | Reported state |
| --- | --- |
| Enumeration and permission observation succeeded | `setup_ready` (with explicit `truncated` when capped) |
| Bearer token rejected on the enumeration surface (HTTP 401) | `setup_token_rejected` |
| 403 with the `consentRequired` reason, or 403 under `application_consent` | `setup_insufficient_consent` |
| 403 under `selected_resource_grant` (the selected scope is not on this lease) | `setup_missing_selected_resource_grant` |
| HTTP 404 on the enumeration surface (the configured root or drive is gone) | `setup_selected_resource_not_found` |
| Permission surface rejects the request shape (400/405/501) | `setup_unsupported_permission_mode` |
| Transport failure, non-2xx with no mapped reason, TLS or DNS failure | `setup_source_unreachable` |

Unsupported credential modes (any mode outside `selected_resource_grant` /
`application_consent`) are rejected at selection or authority construction
before any I/O. None of these states escalates anything: no broader scope is
requested, no re-consent flow is triggered, and the host decides the next
operator step.

A 403/404 on a single item's permission surface is *not* a setup failure:
the item stays observable with `completeness="unavailable"` evidence, so a
file deleted or locked mid-enumeration cannot abort the walk of the
remaining corpus.

## Permission normalization

Drive permissions are effective (including inherited) grants. The adapter
normalizes only the shapes it can pin, and every observation keeps
`mapping_ref` unset — the trust layer, not this adapter, decides what any
principal may read:

| Drive permission `type` | Normalized #863 principal | Readable evidence alone? |
| --- | --- | --- |
| `user` (with bounded e-mail address) | `user` grant on the provider account namespace | No — mapping required |
| `group` (with bounded e-mail address) | `group` grant; membership is never resolved here | No — mapping required |
| `domain` | `domain` grant | Never (contract-ineligible) |
| `anyone`, `anyoneWithLink` | `link` grant | Never (contract-ineligible) |
| Any unrecognized shape | No grant; observation marked `partial` | Never |

Shortcut items are observed as pointers: the target ID is preserved in
`handling_refs` (`gdrive-shortcut:<targetId>`) but is never fetched. An
in-scope target is observed by the enumeration itself; an out-of-scope
target stays exactly what Drive reported — an unobserved identifier. The
shortcut and its target are never merged into one identity.

## Evidence matrix

| Behavior | Mock evidence | Authorized live-provider evidence |
| --- | --- | --- |
| Bounded root enumeration with explicit truncation | Fake Drive provider tests | Not yet |
| Shared-drive `corpora=drive&driveId` pinning | Fake Drive provider tests | Not yet |
| My Drive vs shared drive identity separation | Fake Drive provider tests | Not yet |
| User/group permission normalization | Fake Drive provider tests | Not yet |
| Domain/link non-authorizing evidence | Fake Drive provider tests | Not yet |
| Shortcut pointer semantics (no target fetch) | Fake Drive provider tests | Not yet |
| Setup-state mapping (401/403/404/400/503) | Fake Drive provider tests | Not yet |
| Real workspace consent flow and real e-mail principals | Not applicable | Not yet |

## Limitations

* No live-tenant rehearsal has been performed; the adapter is not
  production-ready and this slice alone does not make the Google source
  production-ready.
* Group membership resolution, directory/SCIM integration and
  changes-cursor persistence are deliberately absent (#867 and later slices).
* Permission pages beyond the operator page cap mark evidence `partial`
  rather than extending the walk.
