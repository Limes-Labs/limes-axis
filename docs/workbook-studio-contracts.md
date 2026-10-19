# Workbook Studio contract: versioned workbooks and governed bindings

[#848](https://github.com/Limes-Labs/limes-axis/issues/848) (parent #847) is
delivered here as a contract slice:
[`services/api/src/axis_api/workbook_studio_contracts.py`](../services/api/src/axis_api/workbook_studio_contracts.py).
It is pure vocabulary — no grid UI, no source access, no formula evaluation
(#849), no writeback. It separates **workbook structure**, **source
bindings** and **cell data provenance** so a workbook survives UI rewrites
without becoming a hidden database or credential container.

## Versioned envelope

`axis.workbook-studio.workbook`, `schema_version` 1.0, `extra="forbid"`,
strict round-trips. Incompatible major versions get the dedicated
`incompatible_workbook_contract_version` code; everything else degrades to
the single `invalid_workbook_contract` code — raw validation details are
never rendered. `parse_workbook_contract` also takes the caller's
authenticated `tenant_scope` and refuses a payload declaring any other scope
(`cross_tenant_workbook_reference`): the payload's own scope is untrusted, so
the internal prefix check alone cannot stop an imported foreign workbook.

## Structure with stable identities

- `WorkbookDefinition` → `WorkbookSheet`s (visibility is presentation
  metadata) → `WorkbookTable`s → `WorkbookColumn`s, plus `NamedRange`s.
  Every identity (`workbook_id`, `sheet_id`, `table_id`, `column_id`,
  `range_id`, `binding_id`) is workbook-local and grammatically disjoint
  from source private storage IDs.
- Referential integrity is construction-enforced: sheets reference existing
  tables, bindings reference existing tables and cover exactly the bound
  columns, duplicate IDs (sheets/tables/columns/mappings/bindings/named
  ranges/local cells) are rejected with `duplicate_workbook_identity`, and
  dangling references (unknown sheet, column, binding, row beyond the
  table's `row_count`, a sheet listing another sheet's named range) with
  `unknown_workbook_reference`.
- Range extents must be ordered and bounded (at most 10,000 rows and 64
  columns, `workbook_range_too_large`), not just match the A1 grammar.

## Bindings reference, never contain

- `DataBinding` points at a registered resource by opaque prefix
  (`tenant.<scope>.<resource>`) — no URL schemes, no SQL shapes, no
  credentials are representable. `workbook_local` is not a source binding
  kind.
- Bound tables carry schema and a row count, never rows: the contract has no
  field that could hold source rows or cached results, so a viewer's
  authorized projection is resolved by the runtime
  (`authorized_projection` makes the per-viewer table allow-list explicit).

## Provenance is explicit

- `local_only` columns and `LocalCellValue` records are the only places
  workbook-local data may live; putting a local value on a bound column is a
  construction failure (`local_override_not_labeled`), so a manual override
  cannot masquerade as source truth.
- `shareable_definition()` strips local values from the digest — sharing
  carries structure and bindings only, never another principal's
  materialized rows or privileged cached data.

## Drift never silently remaps

Mapping is frozen at bind time (`BindingMapping` pairs column↔source field).
`reconcile_binding` only updates the per-column `compatibility` state from
observed source fields and their kinds: `current`, `missing_source` (field
gone) or `incompatible` (field present with a different kind); unknown fields
are left to the source registry's change feed (#592) and columns never
shift by display name or order.

## Attack matrix (construction-refused)

Forged cross-tenant resource prefixes (`cross_tenant_workbook_reference`),
hidden-field bindings (a bound column without a declared source field is
unrepresentable), duplicate table/column/mapping identities, out-of-grammar
huge ranges, in-grammar ranges over the size bound, foreign tenant scopes at
parse time, local values on unknown tables/columns/rows, and workbook-local
binding kinds are all rejected before a workbook can exist.
