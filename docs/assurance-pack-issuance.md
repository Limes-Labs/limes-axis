# Assurance pack issuance and offline verification

[#885](https://github.com/Limes-Labs/limes-axis/issues/885) (parent #733,
depends on #883, #884) is delivered here as one issuance/verification module:
[`services/api/src/axis_api/assurance_issuance.py`](../services/api/src/axis_api/assurance_issuance.py).
It binds final issue approval to an already-assembled #884 package and
provides a bounded offline verifier. No new PKI or key store, no private key
in records, packages or verification material, no persistence, no
delivery/download surface and no CLI yet: the verifier is a library function.

## Signing scheme and key custody

- Issuance accepts exactly one signing profile: **Ed25519**
  (`ed25519` / `self_hosted_ed25519`) from the existing `cryptography`
  dependency, over the canonical JSON (`sort_keys`, tight separators) of the
  issuance statement. Any other algorithm or custody mode fails closed
  (`unsupported_signing_provider`).
- The #477 audit-ledger signer (`audit_signing.py`) is HMAC-SHA256 with a
  shared secret. That suits an operator verifying its own ledger, but an
  external reviewer would need the secret to verify — and could then forge
  records. Assurance packs therefore reuse only the #477 **pattern** (a
  protocol signer that holds its key and returns a proof without secret
  material), not the HMAC mode.
- `Ed25519PackSigner` holds a caller-supplied private key object and only
  exposes `verification_material()` — key id, algorithm, mode and the raw
  public key — for distribution through a separately trusted channel. Key
  generation, storage, rotation and any KMS/HSM adapter remain with the
  key-custody owner (#477); such an adapter implements the same
  `PackageSigner` protocol.

## Issuance binding

`issue_assurance_pack` records the caller's `IssuanceApproval` (approver
reference included) and enforces the gates it owns:

1. The assembled package is self-consistent: its bytes hash to its
   `package_sha256` (`issuance_requires_assembled_package`).
2. The approval covers the exact manifest digest, package digest, audience,
   release and profile (`approval_does_not_match_package`).
3. The #883 preflight passes (`pack_not_ready`) and the sign-time support
   re-check via `check_support_freshness` is fully current
   (`stale_pack_support`).
4. The signer is the approved profile and its proof matches the signed
   payload (`unsupported_signing_provider`); invalid lifecycle input such as
   an unparseable capture time is `invalid_issuance_input`.

The frozen `IssuedAssurancePack` takes pack id, audience, purpose, release
and profile from the manifest itself and binds them to `manifest_sha256`,
`package_sha256`, the approver and the signing profile. The manifest's
`valid_through` is copied verbatim (expiration is an evidence fact, not an
issuance decision). A change after issuance is a new package with a new
record; a correction lists the prior record's `issuance_digest` in
`lifecycle.supersedes`, and the prior record stays independently verifiable.

## Bounded offline verification

`verify_assurance_pack_offline` takes the issuance record bytes, the package
bytes, separately trusted verification material and explicit clock /
revocation facts. It opens no network connection, database or global key.

1. Bounds: record ≤ 64 KiB, package ≤ 16 MiB, ≤ 128 members, each member
   stored (uncompressed) and ≤ 2 MiB; unreadable archives fail.
2. The record parses strictly — unknown fields, such as an embedded trust
   anchor, are rejected.
3. Structure before trust: the package digest, the canonical packaged
   `manifest.json` and its digest, the record's description of that
   manifest, the exact member list, the index (re-rendered from the
   manifest) and every included attachment digest are all checked against
   the package itself.
4. Without trust material the result is `untrusted_input`; the package is
   only `consistent_unauthenticated`.
5. The signing profile must be on the allowlist and agree with the proof
   before any signature math; the trust material must name the same key id,
   algorithm and mode; then the Ed25519 signature and the signed-payload
   digest are verified.

The result carries **separate** fields — signature integrity, package
integrity, evidence freshness, revocation status, clock status — and a
`qualified_result` that is the strongest claim the inputs support:

| Inputs | Result |
| --- | --- |
| Trusted key verifies, all digests match, clock certain, current revocation information says not revoked | `verified_current` |
| Package consistent but no trusted material supplied | `untrusted_input` (signature `unverifiable`) |
| Valid signature, but evidence expired, revocation information missing/stale/revoked-for-future-use, or clock uncertain | `verified_but_qualified` |
| Wrong signer identity or key, unsupported algorithm, tampered record/manifest/index/attachment, missing or extra member, malformed or oversized input | `failed` |

`VerificationClock.revocation_state` is what the revocation information
observed at `revocation_observed_at` says. Stale information (older than
`max_revocation_age_days`, default 7) cannot prove present-day
non-revocation; it can only qualify the result. Re-verifying the same bytes
with the same inputs yields the same verdict, before or after expiry.

## Bounded semantics (AC6)

`SIGNATURE_SEMANTICS_NOTE` (also returned by
`OfflineVerificationResult.signature_semantics_note()` and included in the
result notes) is the wording every UI/CLI/report surface must keep: a
signature proves integrity and provenance of the issued bytes — not
regulatory certification, not freshness beyond the recorded lifecycle facts,
and not the truth of self-attested claims.

## Conformance

`services/api/tests/test_assurance_issuance.py` maps the six acceptance
criteria with local fixtures: verification with sockets disabled (AC1);
modified attachment/manifest/index/record, extra and missing members, wrong
signer id or key, unsupported algorithm and malformed input all fail (AC2);
expiry after issuance blocks current reuse while the historical result stays
verified (AC3); explicit supersession keeps the previous issue verifiable
(AC4); an embedded anchor field, an attacker re-signature, stale, missing or
future-dated revocation information and an uncertain clock cannot produce
`verified_current` (AC5); and the bounded wording (AC6). A dedicated test
asserts no private key bytes appear in the record, the package or the
verification material. A run on a physically disconnected host is NOT RUN.

## Non-goals

No automatically submitted tender, no remotely erasable package, no custom
cryptographic primitives, no revocation infrastructure, no claim of current
non-revocation without current trusted information, and no delivery/download
surface.
