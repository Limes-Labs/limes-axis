# Assurance pack issuance and offline verification

[#885](https://github.com/Limes-Labs/limes-axis/issues/885) (parent #733,
depends on #883, #884) is delivered here as one issuance/verification module:
[`services/api/src/axis_api/assurance_issuance.py`](../services/api/src/axis_api/assurance_issuance.py).
It binds final issue approval to an already-assembled #884 package and
provides a bounded offline verifier. No new PKI, no private key in records
or packages, no delivery/download surface.

## Reused owners (nothing reinvented)

- **#477 key custody** (`audit_signing.py` pattern): a protocol signer plus
  a self-hosted HMAC-SHA256 implementation over canonical JSON. Proofs
  never carry secret material; unsupported custody modes fail closed
  (`unsupported_signing_provider`) instead of introducing an ad-hoc secret
  store.
- **#883 contract**: `check_support_freshness` is reused verbatim as the
  sign-time re-check — a pack whose support drifted since approval cannot
  be issued (`stale_pack_support`).
- **#729 evidence lifecycle**: capture time, `valid_through`, revocation
  status and supersession references live as separate explicit fields in
  `IssuanceLifecycle`, never folded into one boolean.
- **#329 audit integrity**: issuance records are immutable facts; nothing
  re-verifies or rewrites history after the fact.

## Issuance binding

`issue_assurance_pack` records an `IssuanceApproval` — the caller's
authorization fact (approver reference included) — and enforces the gates
it owns:

1. The approval must cover the exact manifest digest, audience, release and
   profile of the assembled package (`approval_does_not_match_package`).
2. The sign-time support re-check must be fully current
   (`stale_pack_support`).
3. The signer must be an approved custody mode (`unsupported_signing_provider`).

The resulting `IssuedAssurancePack` binds `manifest_sha256`, `package_sha256`,
audience and signing profile; the manifest's `valid_through` is copied
verbatim (expiration is an evidence fact, not an issuance decision). A
change after issuance is a new package with a new record; correcting a prior
issue records it explicitly via `supersedes`.

## Bounded offline verification

`verify_assurance_pack_offline` takes every input as an argument: the
issuance record bytes, the package bytes, the manifest and attachment bytes
extracted from the package under test, separately trusted verification
material, and explicit clock facts. No network, no database, no
process-global trust.

The result carries **separate** fields — signature integrity, package
integrity, evidence freshness, revocation status, clock status — and a
`qualified_result` that is the strongest claim the inputs support:

| Inputs | Result |
| --- | --- |
| Trusted material matches, all digests verify, clock certain, revocation current | `verified_current` |
| Package intact but no trusted material supplied | `untrusted_input` (signature `unverifiable`) |
| Valid signature, but evidence expired / stale revocation / uncertain clock | `verified_but_qualified` |
| Wrong signer identity, unsupported algorithm, tampered manifest/package/attachment, missing member | `failed` |

Key properties:

- **An untrusted package's embedded trust anchor cannot authenticate
  itself**: trust material must match the issued signer identity and come
  from a separately trusted channel.
- **Supported-algorithm allowlist** before any signature math; the record's
  claimed algorithm is not self-certifying.
- **Membership before resolution**: a missing required member is a fixed
  verification failure, never a resolver crash.
- **Stale revocation information cannot prove present-day non-revocation**;
  it can only qualify the result. Same for an uncertain clock.
- **Historical results never change**: re-verifying the same bytes with the
  same inputs yields the same integrity verdict, before or after expiry.

## Bounded semantics (AC6)

`OfflineVerificationResult.signature_semantics_note()` returns the exact
wording every UI/CLI/report surface must keep: a signature proves
integrity and provenance of the issued bytes — not regulatory
certification, not freshness beyond the recorded lifecycle facts, and not
the truth of self-attested claims.

## Conformance

`services/api/tests/test_assurance_issuance.py` maps the six acceptance
criteria: isolated verification (AC1), modified
attachment/manifest/record + wrong signer + unsupported algorithm +
missing member all fail (AC2), expiry-after-issuance blocks current reuse
while the historical issue stays verifiable (AC3), explicit supersession
keeps the previous issue independently verifiable (AC4), forged embedded
anchor + stale revocation + uncertain clock cannot produce an unqualified
current/trusted result (AC5), and the bounded wording (AC6). A dedicated
test asserts no custody secret appears in the issuance record or the
package bytes.

## Non-goals

No automatically submitted tender, no remotely erasable package, no custom
cryptographic primitives, no claim of current non-revocation without
current trusted information, and no delivery/download surface.
