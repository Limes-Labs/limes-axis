# Assurance pack assembly: released-only deterministic packaging

[#884](https://github.com/Limes-Labs/limes-axis/issues/884) (parent #733,
depends on #883) is delivered here as one domain service:
[`services/api/src/axis_api/assurance_packaging.py`](../services/api/src/axis_api/assurance_packaging.py).
It assembles the bounded package for an approved #883 `PackManifest` — a
canonical JSON manifest, a sanitized local Markdown index, and permitted
bounded attachments. No signing, no issuance, no download delivery, no new
artifact store, no document rendering (#885 and #834 own those).

## Caller-owned boundaries

The builder performs no I/O and holds no registry. Two small protocols
carry the policy:

- `ArtifactSource.resolve(entry, manifest)` performs the **current** release
  authorization (revoked audience → `pack_release_not_current`), applies the
  outbound disclosure boundary, reads the object store (missing evidence →
  `pack_artifact_unavailable`) and refuses superseded revisions
  (`pack_artifact_revision_mismatch`). #729 remains the evidence owner;
  support-state freshness stays with the #883 preflight helpers.
- `PackScanner.scan(data, fmt)` inspects the **final output** — manifest
  JSON, index text, every member filename and every packaged attachment's
  bytes — for formats `json` / `text` / `filename`. A scanner that cannot
  judge a format raises `pack_scan_format_unsupported`: unsupported scan
  formats block the build, they never silently pass.

## Deterministic, bounded, atomic

- Members ship in fixed order (`manifest.json`, `index.md`,
  `attachments/<entry_id>.bin`) with pinned archive metadata (epoch
  timestamp, `create_system`, mode), so identical inputs produce identical
  bytes and `package_sha256` is reproducible across machines.
- Bounds: ≤ 32 attachments, ≤ 2 MiB per attachment, ≤ 128 members, ≤ 16 MiB
  package. Any breach aborts with `pack_bounds_exceeded`.
- Partial failure leaves nothing: the package exists only after release
  authorization, digest verification (`pack_artifact_digest_mismatch`
  otherwise) and all scans have passed. There is no cached privileged
  package to reuse — every generation re-resolves the current release
  state, so revocation, a changed revision or unavailable evidence
  invalidates generation instead.

## Reference-only citations stay byte-free

A `reference_only` entry produces a `ReferenceOnlyCitation` (id, title,
evidence refs, scope note) in the index — never a copy of restricted
bytes, a URL or a bearer link. The #871/#879 scope wording is the #883
contract's own (`reference_scope_note`); the builder cannot reword it, and
the sanitized local index contains no remote fonts, images or scripts.

## Claims are preserved verbatim

Support states, responsibilities, limitations and certificate scope ship
exactly as approved. The builder adds no compliant/certified wording and
never converts a gap into a positive claim; the manifest JSON inside the
package is canonical (`sort_keys`, tight separators) so
`manifest.digest()` can be re-verified by any consumer.

## Ordinary audit

Callers emit only safe facts — digests, counts, reason codes (`pack_id`,
`manifest_digest`, `package_sha256`, member/attachment/citation counts).
Evidence content and scan findings never enter ordinary audit.
