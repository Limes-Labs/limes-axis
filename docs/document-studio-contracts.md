# Document Studio contract: versioned documents and reusable templates

[#829](https://github.com/Limes-Labs/limes-axis/issues/829) (parent #828) is
delivered here as a contract slice:
[`services/api/src/axis_api/document_studio_contracts.py`](../services/api/src/axis_api/document_studio_contracts.py).
It is pure vocabulary — no storage, no editor runtime, no rendering, no
governed embed resolution (owned by #830). It defines what a document
pipeline must emit and what a consumer must verify before rendering or
packaging a document or template.

## Versioned envelopes

- `axis.document-studio.document` and `axis.document-studio.template`, both
  `schema_version` 1.0. Unknown fields are rejected (`extra="forbid"`);
  incompatible major versions get the dedicated
  `incompatible_document_contract_version` code, everything else degrades to
  the single `invalid_document_contract` / `invalid_template_contract` code —
  raw validation details are never rendered.

## Document and block model

- `DocumentRevision`: identity + revision, title/description/locale,
  lifecycle state (`draft`/`published`), `PageLayout`, `ThemeTokens`,
  ordered `DocumentSection`s, optional `TemplateProvenance` and typed
  `parameter_values`, `issued_at`.
- `DocumentSection`: stable `section_id`, title, 1–256 `DocumentBlock`s.
- `DocumentBlock`: stable `block_id`, one of ten baseline kinds — heading,
  text, media, divider, callout, metadata, table, toc, page_break,
  `embed_placeholder` (typed `EmbedSlot`; resolution owned by #830).
  Kind-specific coherence is construction-enforced (headings carry level and
  text, media requires a bounded reference and alt text, tables declare a
  column count that every row matches).
- Deterministic canonical-JSON digests (`canonical_document_digest`);
  ordering-insensitive and tamper-evident.

## Templates, regions and provenance

- `DocumentTemplate`: typed `TemplateParameter`s (string/number/boolean/
  date/governed_ref, with format-checked defaults), `TemplateRegion`s
  (`fixed` / `editable` / `required`) that must reference real block IDs,
  and the same section/block vocabulary.
- `instantiate_template` works only on **published** templates, requires
  every required parameter (format-validated), cannot override `fixed`
  region content, cannot accept content outside a region, and stamps
  `TemplateProvenance` with the exact template revision **content digest**.
- Publication/deletion change only lifecycle fields, so
  `DocumentTemplate.content_digest()` excludes them — deleting a template
  never invalidates documents instantiated from the revision
  (`verify_template_lineage` works for deleted templates on purpose).
  Publishing template N+1 does not move documents bound to N; migration is
  an explicit new instantiation.

## Immutability discipline

- Published revisions cannot be edited (`edit_document` refuses) or
  re-published; `revise_document` starts a new draft revision and never
  rewrites issued bytes. Lifecycle fields (`state`, `revision`, `issued_at`)
  and identity/lineage fields (`document_id`, `template_provenance`,
  `parameter_values`) cannot be smuggled through `edit_document`.
- `edit_document` requires the `base_digest` of the draft the editor started
  from; a draft already moved by a concurrent edit is refused with
  `stale_document_draft` instead of being silently overwritten.
- Region policy is enforced at instantiation only: documents do not carry
  the template's region map, so later draft edits are not checked against
  `fixed` regions by this contract. A later editor slice must re-check edits
  against the provenance revision if fixed content must stay fixed.
- Template deletion keeps historical lineage; re-instantiation from a
  deleted template is refused (`template_deleted`), instantiation from a
  draft is refused (`template_not_published`).

## Content safety

- Authored text (titles, blocks, alt text, table cells, captions, headers,
  footers, metadata values) is structured plain text: script/iframe markup,
  script URLs, template delimiters (`{{ }}`, `${ }`) and prototype-pollution
  shapes are rejected with the fixed `unsafe_document_content` code.
- Theme values are bounded design tokens; arbitrary CSS/JS is
  unrepresentable. Media references reject traversal payloads.
- Template parameter values are bounded plain data, re-validated against
  their declared kind at instantiation (exact-match number/boolean/date/
  governed-ref grammars) and rejected when they carry markup, template
  delimiters or URL schemes. Free-text `string` values are never interpreted
  as queries by this contract; whether a consumer treats them as data is a
  binding concern (#830).

## Accessibility as contract data

`document_accessibility_outline` returns the ordered reading outline —
heading levels, alt text, table shapes, embed kinds — straight from the
serialized contract, so heading structure, reading order and alt-text slots
survive round-trips instead of living only in the renderer.

## Round-trips at untrusted boundaries

`parse_document_contract` / `parse_template_contract` accept canonical JSON
with the strict error-code policy above; digests recomputed from the parsed
model match the producer's digest exactly (byte-stable round-trip).
