# Public dataset release manifest: contract for immutable publications

[#838](https://github.com/Limes-Labs/limes-axis/issues/838) (parent #837) is
delivered here as a contract slice:
[`services/api/src/axis_api/public_release_manifest.py`](../services/api/src/axis_api/public_release_manifest.py).
It is pure vocabulary — no storage, no distribution packaging, no anonymous
API, no rendering. It defines what a publication pipeline must emit and what a
consumer must verify before any distribution or API slice (#840/#841) can
resolve back to a release whose source, schema and disclosure decision cannot
drift underneath public consumers.

## Envelope and versioning

* `format` is the fixed literal `axis.public-dataset-release`;
  `schema_version` is `1.0` (major 1, minor 0). Reading is bounded:
  `parse_public_release_manifest` rejects incompatible majors with the fixed
  safe code `incompatible_release_manifest_version`, and unknown fields are
  refused (`extra="forbid"`) with `invalid_public_release_manifest`. There is
  no implicit major fallback and no all-version compatibility promise.
* Canonical digest: `canonical_release_digest` (SHA-256 over sorted-key,
  separator-normalized JSON). The manifest's own `digest()` uses the same
  helper, so producers cannot sign non-canonical bytes. Digests are
  deterministic across key order and stable for tamper detection.

## Sealed release identity

| Invariant | Enforcement |
| --- | --- |
| One manifest freezes exactly one release revision | `identity` (opaque public id, api name, title, publisher) + `release_version` + lifecycle `state` |
| Public IDs cannot be transformed into internal resource IDs | `ds-` prefix + lowercase base32-ish body pattern is disjoint from UUID/numeric internal shapes; `public_release_uri_path` validates before composing `/public/datasets/{id}/releases/{version}` |
| A release is created from a frozen source, never a live query | `SourceBinding.mode` is a closed literal set (`governed_snapshot`, `materialized_view`, `frozen_publication`, `external_artifact`); no live mode exists in the vocabulary |
| Issued release binds published bytes | sealed states (`issued`, `superseded`, `deprecated`, `withdrawn`, `archived`) require `issued_at` **and** `population.content_digest`; issuing without the digest is a construction failure, not a silent success |
| Authorization cannot predate the data | every decided review's `decided_at` must be at or after `source.captured_at`, else the manifest is rejected as stale authorization |
| Public schema is bounded and typed | 1–256 uniquely-named fields with closed dtype vocabulary and per-field descriptions |

## Public evidence versus internal lineage

The public manifest structurally cannot carry internal source references:
it has no such field and unknown fields are refused. Exact lineage lives in
`InternalSourceLedger` (data-product/snapshot/materialization/query-revision
refs with digests), bound to the public manifest by `manifest_digest` and
public id through `bind_internal_ledger`. Ledger fields are `repr=False` so
internal references do not leak into logs or tracebacks. The companion ledger
is produced and stored where internal lineage is already governed (#752/#790
ownership); this slice only defines the binding contract.

## Disclosure and license authorization

`release_readiness` classifies whether a manifest may be issued — it never
issues anything:

| Condition | Verdict |
| --- | --- |
| Disclosure review approved | required; otherwise `disclosure_review_missing` / `disclosure_review_not_approved` |
| License review approved | required; otherwise `license_review_missing` / `license_review_not_approved` |
| Population digest present | required for issuance; otherwise `population_digest_missing` |
| Sensitivity review | optional `ReviewEvidence`; when present it must be internally coherent |

Review evidence that is decided must name an authority and a decision
timestamp; pending evidence cannot carry a decision timestamp. Approval is
never inferred from possession of a data-product id or from any configuration
flag — a missing review is a deterministic block, and the issue's rule that
mere control mapping does not authorize inclusion of the underlying artifact
is enforced by requiring explicit review records per kind.

## Lifecycle, withdrawal and supersession

* Lifecycle states: `draft`, `disclosure_review`, `approved`, `issued`,
  `superseded`, `deprecated`, `withdrawn`, `archived`. Only sealed states
  carry `issued_at`; non-sealed states cannot claim issuance.
* `SupersedesRecord` binds a new version to the exact prior manifest digest
  and must reference the same public dataset id.
* `WithdrawalRecord` pins `issued_manifest_digest` — the digest of the
  manifest exactly as issued. The validator reconstructs that issuance
  (`state="issued"`, no withdrawal record) and re-digests it, so tampered or
  misbound withdrawal evidence is rejected. The record carries the fixed
  literal `external_copies_note = "external_copies_not_retracted"`: withdrawal
  stops future delivery, it does not and cannot retract downloaded copies,
  and the vocabulary makes overclaiming unrepresentable.

## Deterministic release notes

`diff_releases(previous, candidate)` produces stable vN→vN+1 notes:
field additions/removals/retypes (sorted, deterministic), source refresh,
coverage extension, license change and deprecation. It refuses cross-dataset
diffs (`cross_dataset_diff`) and non-monotonic versions
(`non_monotonic_release_version`). Notes derive only from public manifest
data, so internal-only lineage never enters release notes.

## Support matrix: what this slice does and does not do

| Capability | Status here | Owner |
| --- | --- | --- |
| Release/manifest schema, digest, lifecycle, withdrawal/supersession evidence | Delivered | this module (#838) |
| Public ID/URI grammar | Delivered (grammar + path helper) | #841 owns actual API resolution |
| Bulk distributions, checksums, download artifacts | Not in this slice | #840 |
| Disclosure/license review workflow execution | Evidence consumed only; approval happens upstream | #839 / #720 |
| Exact internal lineage storage | Binding contract only; ledger produced by owning pipelines | #752 / #790 |
| Snapshot/materialization semantics | Source modes referenced by contract | #790 / #831 |
| DCAT-AP metadata mapping | Not in this slice | #758 |

## Production readiness

Not claimed. The contract is exercised with synthetic fixtures; no live
publication pipeline, tenant data or public endpoint is touched. Wiring into
catalog identity (#752), review gates (#839) and distributions (#840) are
follow-up slices that must adopt this manifest as the sealed version boundary.
