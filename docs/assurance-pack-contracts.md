# Assurance pack manifest: audience-bound evidence selection

[#883](https://github.com/Limes-Labs/limes-axis/issues/883) (parent #733) is
delivered here as a contract slice:
[`services/api/src/axis_api/assurance_pack_contracts.py`](../services/api/src/axis_api/assurance_pack_contracts.py).
It is pure vocabulary — no artifact packaging, no signing, no evidence
store. It freezes **which** existing answers, deployment observations and
evidence revisions may appear in one customer-facing assurance pack, and
keeps gaps visible instead of converting controls into positive claims.

## Versioned envelope

`axis.assurance-pack.manifest`, `schema_version` 1.0, `extra="forbid"`,
strict round-trips. Incompatible major versions get the dedicated
`incompatible_assurance_pack_version` code; everything else degrades to the
single `invalid_assurance_pack_manifest` code.

## One pack = one engagement, audience, snapshot

- `PackContext` binds the pack to one engagement reference, one audience,
  one purpose and a disclosure class. Evidence from one customer/profile can
  never be presented as a generic product claim; the context is part of the
  digest, so re-audienceing a pack is a new candidate that must be reviewed
  again.
- `ReleaseSnapshot` freezes the release version, profile and the exact
  deployment-posture observation (reference + revision + digest) the whole
  pack speaks about — from #730; this contract creates no new registry.

## Entries cite exact revisions

`AnswerSelection` pins each entry to an exact answer revision + digest
(#731) and optional evidence references (#729). Support is a closed state
machine — `current`, `partial`, `planned`, `customer_responsibility`,
`not_evidenced`, `cannot_disclose` — and `partial`/`planned`/`not_evidenced`
entries **must** state their exact limitation: gaps ship as structured data,
never as silent optimism.

- `included_artifact` entries carry the artifact digest and cannot be
  `internal_only`; `reference_only` entries carry no artifact bytes —
  mapping to a control never authorizes shipping its underlying artifact.
- `customer_responsibility` support cannot claim Axis ownership.
- Free text is bounded prose; markup and template delimiters are
  construction-refused (`unsafe_pack_text`).

## Freshness is re-verified, never assumed

`check_support_freshness` compares every entry against operator-supplied
observed state (`current`, `expired_certificate`, `wrong_release_profile`,
`superseded_answer`, …). An expired certificate, a wrong release/profile or
a superseded answer cannot pass as current support; stale entries are named
`entry:reason` against the manifest's digest, so the stale pack is
detectably different from its approved form and preflight must run again.

## Preflight gating

`pack_readiness` blocks issuance when a pack contains no `current` support
or when structured states lack their limitations (already
construction-enforced — the check exists for parsed candidates). Missing
required support never silently degrades to a positive answer.

## Scope note for #871 / #879 citations

`reference_scope_note()` fixes the wording producers must keep: isolation
(#871) and portability (#879) reports may be cited **reference-only for
their actually tested scope and revision**; configuration flags are not
evidence of independent certification.
