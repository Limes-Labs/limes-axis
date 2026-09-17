"""Workbook Studio contract: versioned workbooks and governed data bindings.

Contract slice of [#848](https://github.com/Limes-Labs/limes-axis/issues/848)
(parent #847). This module is pure vocabulary: no grid UI, no source access,
no formula evaluation (owned by #849), no writeback. It defines the durable
shape of workbooks plus the rules producers must satisfy:

* A versioned ``axis.workbook-studio.workbook`` envelope with strict
  round-trips; unknown fields and incompatible major versions are rejected.
* Workbook structure (workbooks, sheets, tables, columns, named ranges,
  local data, bindings) with stable identities separate from source private
  storage IDs.
* A binding references a governed resource by opaque registered prefix; the
  contract structurally cannot carry source credentials, raw queries, cached
  source rows or per-viewer materialized results.
* Every workbook-local value is explicitly labeled local; bound ranges
  declare source ownership without embedding rows, so a viewer's authorized
  projection is resolved by the runtime, never carried in the definition.
* Source schema drift produces an explicit compatibility state; mapping is
  frozen at bind time and never silently remapped by display name or order.
* Hidden sheets/columns are presentation-only metadata and never a security
  boundary.

The digest helper is shared so producers cannot sign non-canonical bytes.
"""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from axis_sdk.connector_authoring.contracts import ContractModel, Digest
from pydantic import Field, ValidationError, model_validator

WORKBOOK_FORMAT = "axis.workbook-studio.workbook"
CONTRACT_MAJOR = 1
CONTRACT_MINOR = 0

#: Supported schema versions for reading; major bumps change semantics.
SUPPORTED_MAJOR_VERSIONS = (CONTRACT_MAJOR,)

_MAX_SHEETS = 32
_MAX_TABLES = 64
_MAX_ROWS = 10_000
_MAX_COLUMNS_PER_TABLE = 64
_MAX_ROWS_PER_TABLE = 5_000
_MAX_TEXT = 500
_MAX_TITLE = 200
_MAX_NAMED_RANGES = 64
_MAX_BINDINGS = 32

_IDENTIFIER = r"^[a-z][a-z0-9-]{2,47}$"
# Opaque registered resource prefixes only: no URL schemes, no SQL shapes,
# no credentials. Colons/whitespace/quotes are outside the grammar.
_RESOURCE_PREFIX = r"^[a-z][a-z0-9._-]{2,63}$"
_RANGE = r"^[A-Z]{1,2}[1-9][0-9]{0,5}:[A-Z]{1,2}[1-9][0-9]{0,5}$"
_TIMESTAMP = r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$"

BindingKind = Literal["analytical_query", "entity_projection", "data_product", "workbook_local"]
BindingStatus = Literal["current", "incompatible", "missing_source", "unauthorized"]
ColumnKind = Literal["string", "number", "boolean", "date", "duration", "reference", "local_only"]
SheetVisibility = Literal["visible", "hidden"]


class WorkbookStudioError(ValueError):
    """Fixed contract codes; raw validation details are never rendered."""

    INCOMPATIBLE_VERSION = "incompatible_workbook_contract_version"
    INVALID_WORKBOOK = "invalid_workbook_contract"
    FORGED_SOURCE_REF = "forged_source_reference"
    HIDDEN_FIELD_BINDING = "hidden_field_binding"
    DUPLICATE_IDENTITY = "duplicate_workbook_identity"
    RANGE_TOO_LARGE = "workbook_range_too_large"
    CROSS_TENANT = "cross_tenant_workbook_reference"
    DRIFT_UNMAPPED = "source_drift_unmapped"
    NOT_LOCAL = "local_override_not_labeled"

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def canonical_workbook_digest(value: object) -> Digest:
    """Deterministic digest over canonical JSON; producers must reuse this."""

    data = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(data.encode("utf-8")).hexdigest()


def _parse_major(value: object) -> int:
    if not isinstance(value, dict):
        raise WorkbookStudioError(WorkbookStudioError.INVALID_WORKBOOK)
    version = value.get("schema_version")
    major = version.get("major") if isinstance(version, dict) else None
    if not isinstance(major, int) or isinstance(major, bool):
        raise WorkbookStudioError(WorkbookStudioError.INVALID_WORKBOOK)
    return major


class ManifestVersion(ContractModel):
    major: int = Field(ge=1, strict=True)
    minor: int = Field(ge=0, strict=True)

    @model_validator(mode="after")
    def bounded_version(self) -> ManifestVersion:
        if self.major != CONTRACT_MAJOR or self.minor != CONTRACT_MINOR:
            raise ValueError(f"Unsupported workbook contract version {self.major}.{self.minor}")
        return self


class NamedRange(ContractModel):
    """A named, bounded cell range scoped to the workbook."""

    range_id: str = Field(pattern=_IDENTIFIER)
    name: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_.]{0,63}$")
    sheet_id: str = Field(pattern=_IDENTIFIER)
    extent: str = Field(pattern=_RANGE)


class WorkbookColumn(ContractModel):
    """One column with a stable identity and a declared value kind."""

    column_id: str = Field(pattern=_IDENTIFIER)
    header: str = Field(min_length=1, max_length=_MAX_TEXT)
    kind: ColumnKind
    source_field: str | None = Field(default=None, pattern=_RESOURCE_PREFIX)
    hidden: bool = False

    @model_validator(mode="after")
    def coherent_column(self) -> WorkbookColumn:
        if self.kind == "local_only" and self.source_field is not None:
            raise ValueError("local_only columns carry no source field")
        if self.kind != "local_only" and self.source_field is None:
            raise ValueError("bound columns must declare their source field")
        return self


class WorkbookTable(ContractModel):
    """A structured table; bound tables carry schema, never source rows."""

    table_id: str = Field(pattern=_IDENTIFIER)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    columns: tuple[WorkbookColumn, ...] = Field(min_length=1, max_length=_MAX_COLUMNS_PER_TABLE)
    row_count: int = Field(default=0, ge=0, strict=True, le=_MAX_ROWS_PER_TABLE)
    extent: str | None = Field(default=None, pattern=_RANGE)

    @model_validator(mode="after")
    def coherent_table(self) -> WorkbookTable:
        column_ids = [column.column_id for column in self.columns]
        if len(set(column_ids)) != len(column_ids):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        headers = [column.header for column in self.columns]
        if len(set(headers)) != len(headers):
            raise ValueError("Column headers must be unique within a table")
        return self


class BindingMapping(ContractModel):
    """Frozen bind-time mapping from a workbook column to a source field."""

    column_id: str = Field(pattern=_IDENTIFIER)
    source_field: str = Field(pattern=_RESOURCE_PREFIX)
    source_kind: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,31}$")
    compatibility: BindingStatus = "current"


class DataBinding(ContractModel):
    """A governed reference to a registered resource; no credentials, no rows."""

    binding_id: str = Field(pattern=_IDENTIFIER)
    kind: BindingKind
    resource_prefix: str = Field(pattern=_RESOURCE_PREFIX)
    table_id: str = Field(pattern=_IDENTIFIER)
    mapping: tuple[BindingMapping, ...] = Field(min_length=1, max_length=_MAX_COLUMNS_PER_TABLE)
    refresh: Literal["manual", "snapshot_on_open"] = "manual"

    @model_validator(mode="after")
    def coherent_binding(self) -> DataBinding:
        if self.kind == "workbook_local":
            raise ValueError("workbook_local is not a source binding kind")
        mapping_columns = [entry.column_id for entry in self.mapping]
        if len(set(mapping_columns)) != len(mapping_columns):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        return self


class LocalCellValue(ContractModel):
    """A workbook-local value, labeled as such; never masquerades as source."""

    table_id: str = Field(pattern=_IDENTIFIER)
    row: int = Field(ge=0, strict=True, le=_MAX_ROWS_PER_TABLE)
    column_id: str = Field(pattern=_IDENTIFIER)
    value: str | int | float | bool | None
    note: str | None = Field(default=None, max_length=_MAX_TEXT)


class WorkbookSheet(ContractModel):
    sheet_id: str = Field(pattern=_IDENTIFIER)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    visibility: SheetVisibility = "visible"
    table_ids: tuple[str, ...] = Field(min_length=1, max_length=_MAX_TABLES)
    named_range_ids: tuple[str, ...] = Field(default=(), max_length=_MAX_NAMED_RANGES)

    @model_validator(mode="after")
    def coherent_sheet(self) -> WorkbookSheet:
        if len(set(self.table_ids)) != len(self.table_ids):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        return self


class WorkbookDefinition(ContractModel):
    """One workbook at one revision; structure only, never source data."""

    format: Literal["axis.workbook-studio.workbook"] = WORKBOOK_FORMAT
    schema_version: ManifestVersion
    workbook_id: str = Field(pattern=_IDENTIFIER)
    revision: str = Field(pattern=r"^\d+$")
    tenant_scope: str = Field(pattern=_RESOURCE_PREFIX)
    title: str = Field(min_length=1, max_length=_MAX_TITLE)
    description: str | None = Field(default=None, max_length=_MAX_TITLE)
    locale: str = Field(pattern=r"^[a-z]{2}(-[A-Z]{2})?$")
    sheets: tuple[WorkbookSheet, ...] = Field(min_length=1, max_length=_MAX_SHEETS)
    tables: tuple[WorkbookTable, ...] = Field(min_length=1, max_length=_MAX_TABLES)
    named_ranges: tuple[NamedRange, ...] = Field(default=(), max_length=_MAX_NAMED_RANGES)
    bindings: tuple[DataBinding, ...] = Field(default=(), max_length=_MAX_BINDINGS)
    local_values: tuple[LocalCellValue, ...] = Field(default=(), max_length=_MAX_ROWS * 4)

    @model_validator(mode="after")
    def coherent_workbook(self) -> WorkbookDefinition:
        sheet_ids = [sheet.sheet_id for sheet in self.sheets]
        if len(set(sheet_ids)) != len(sheet_ids):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        table_ids = [table.table_id for table in self.tables]
        if len(set(table_ids)) != len(table_ids):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        table_index = set(table_ids)
        for sheet in self.sheets:
            if not set(sheet.table_ids) <= table_index:
                raise ValueError("Sheets must reference existing tables")
        for table in self.tables:
            if not any(table.table_id in sheet.table_ids for sheet in self.sheets):
                raise ValueError("Every table must appear on exactly its declared sheets")
        for named_range in self.named_ranges:
            if named_range.sheet_id not in set(sheet_ids):
                raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        binding_tables = [binding.table_id for binding in self.bindings]
        if len(set(binding_tables)) != len(binding_tables):
            raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
        if not set(binding_tables) <= table_index:
            raise ValueError("Bindings must reference existing tables")
        tenant_prefix = f"{self.tenant_scope}."
        for binding in self.bindings:
            if not binding.resource_prefix.startswith(tenant_prefix):
                raise WorkbookStudioError(WorkbookStudioError.CROSS_TENANT)
        for binding in self.bindings:
            table = next(t for t in self.tables if t.table_id == binding.table_id)
            column_ids = {column.column_id for column in table.columns}
            for entry in binding.mapping:
                if entry.column_id not in column_ids:
                    raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
            bound_fields = {
                column.column_id: column.source_field
                for column in table.columns
                if column.source_field is not None
            }
            if set(bound_fields) != {entry.column_id for entry in binding.mapping}:
                raise ValueError("Binding mapping must cover exactly the bound columns")
            for entry in binding.mapping:
                if bound_fields[entry.column_id] != entry.source_field:
                    raise WorkbookStudioError(WorkbookStudioError.DRIFT_UNMAPPED)
        for value in self.local_values:
            table = next((t for t in self.tables if t.table_id == value.table_id), None)
            if table is None:
                raise ValueError("Local values must reference existing tables")
            if value.column_id not in {column.column_id for column in table.columns}:
                raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
            column = next(c for c in table.columns if c.column_id == value.column_id)
            if column.kind != "local_only":
                raise WorkbookStudioError(WorkbookStudioError.NOT_LOCAL)
        return self

    def digest(self) -> Digest:
        return canonical_workbook_digest(self.model_dump(mode="json"))

    def shareable_definition(self) -> Digest:
        """Digest of the definition with local values stripped.

        Sharing/export carries structure and bindings only: never source
        rows, credentials or per-viewer materialized results. The runtime
        resolves each viewer's authorized projection independently.
        """

        payload = {
            key: value
            for key, value in self.model_dump(mode="json").items()
            if key != "local_values"
        }
        return canonical_workbook_digest(payload)


def reconcile_binding(
    workbook: WorkbookDefinition,
    binding_id: str,
    *,
    observed_fields: tuple[str, ...],
) -> WorkbookDefinition:
    """Surface schema drift as explicit compatibility state; never remaps.

    Mapping was frozen at bind time. Columns whose source field disappeared
    become ``missing_source``; unknown observed fields are ignored on the
    workbook side (they belong to the source registry's change feed, #592)
    instead of silently shifting columns.
    """

    binding = next((b for b in workbook.bindings if b.binding_id == binding_id), None)
    if binding is None:
        raise WorkbookStudioError(WorkbookStudioError.DUPLICATE_IDENTITY)
    observed = set(observed_fields)
    updated: list[BindingMapping] = []
    for entry in binding.mapping:
        state = "current" if entry.source_field in observed else "missing_source"
        updated.append(BindingMapping.model_validate(
            {**entry.model_dump(mode="json"), "compatibility": state}
        ))
    replaced = DataBinding.model_validate(
        {**binding.model_dump(mode="json"), "mapping": tuple(updated)}
    )
    bindings = tuple(
        replaced if b.binding_id == binding_id else b for b in workbook.bindings
    )
    return WorkbookDefinition.model_validate(
        {**workbook.model_dump(mode="json"), "bindings": bindings}
    )


def authorized_projection(
    workbook: WorkbookDefinition,
    *,
    viewer: str,
    visible_table_ids: tuple[str, ...],
) -> WorkbookDefinition:
    """A viewer-specific definition whose bound tables are structure only.

    Bound tables never carry rows in the contract; this helper makes the
    per-viewer projection explicit by keeping only tables the viewer is
    authorized to see and stripping local values (they are the authoring
    principal's governed data, not the viewer's).
    """

    del viewer
    allowed = set(visible_table_ids)
    sheets = tuple(
        WorkbookSheet.model_validate(
            {**sheet.model_dump(mode="json"), "table_ids": tuple(
                table_id for table_id in sheet.table_ids if table_id in allowed
            )}
        )
        for sheet in workbook.sheets
        if set(sheet.table_ids) & allowed
    )
    return WorkbookDefinition.model_validate(
        {
            **workbook.model_dump(mode="json"),
            "sheets": sheets,
            "tables": tuple(t for t in workbook.tables if t.table_id in allowed),
            "bindings": tuple(b for b in workbook.bindings if b.table_id in allowed),
            "local_values": (),
        }
    )


def parse_workbook_contract(value: object) -> WorkbookDefinition:
    """Parse an untrusted workbook payload with fixed safe error codes."""

    if isinstance(value, dict):
        major = _parse_major(value)
        if major not in SUPPORTED_MAJOR_VERSIONS:
            raise WorkbookStudioError(WorkbookStudioError.INCOMPATIBLE_VERSION)
    try:
        return WorkbookDefinition.model_validate(value)
    except ValidationError:
        raise WorkbookStudioError(WorkbookStudioError.INVALID_WORKBOOK) from None
