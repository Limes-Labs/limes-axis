"""Contract tests for the #848 Workbook Studio workbook/binding contracts."""

from __future__ import annotations

import json

import pytest
from pydantic import ValidationError

from axis_api.workbook_studio_contracts import (
    BindingMapping,
    DataBinding,
    LocalCellValue,
    ManifestVersion,
    NamedRange,
    WorkbookColumn,
    WorkbookDefinition,
    WorkbookSheet,
    WorkbookStudioError,
    WorkbookTable,
    authorized_projection,
    canonical_workbook_digest,
    parse_workbook_contract,
    reconcile_binding,
)

_TENANT = "tenant-demo"


def _bound_columns() -> tuple[WorkbookColumn, ...]:
    return (
        WorkbookColumn(
            column_id="col-period", header="Period", kind="string", source_field="fields.period"
        ),
        WorkbookColumn(
            column_id="col-oee", header="OEE", kind="number", source_field="fields.oee"
        ),
        WorkbookColumn(column_id="col-note", header="Analyst note", kind="local_only"),
    )


def _analytical_binding(table_id: str = "tbl-oee", status: str = "current") -> DataBinding:
    return DataBinding(
        binding_id="bnd-oee",
        kind="analytical_query",
        resource_prefix=f"{_TENANT}.analytics.query-42",
        table_id=table_id,
        mapping=(
            BindingMapping(
                column_id="col-period",
                source_field="fields.period",
                source_kind="string",
                compatibility=status,  # type: ignore[arg-type]
            ),
            BindingMapping(
                column_id="col-oee",
                source_field="fields.oee",
                source_kind="number",
                compatibility=status,  # type: ignore[arg-type]
            ),
        ),
    )


def _entity_binding() -> DataBinding:
    return DataBinding(
        binding_id="bnd-assets",
        kind="entity_projection",
        resource_prefix=f"{_TENANT}.objects.asset-line",
        table_id="tbl-assets",
        mapping=(
            BindingMapping(
                column_id="col-asset", source_field="fields.asset_id", source_kind="string"
            ),
        ),
    )


def _local_table() -> WorkbookTable:
    return WorkbookTable(
        table_id="tbl-inputs",
        title="Analyst inputs",
        columns=(
            WorkbookColumn(column_id="col-assumption", header="Assumption", kind="local_only"),
        ),
        row_count=2,
        extent="A1:B3",
    )


def _workbook(**overrides: object) -> WorkbookDefinition:
    values: dict[str, object] = {
        "schema_version": ManifestVersion(major=1, minor=0),
        "workbook_id": "wb-oee-review",
        "revision": "1",
        "tenant_scope": _TENANT,
        "title": "OEE weekly review",
        "locale": "en",
        "sheets": (
            WorkbookSheet(
                sheet_id="sh-summary", title="Summary", table_ids=("tbl-oee", "tbl-inputs")
            ),
            WorkbookSheet(
                sheet_id="sh-assets", title="Assets", table_ids=("tbl-assets",), visibility="hidden"
            ),
        ),
        "tables": (
            WorkbookTable(
                table_id="tbl-oee",
                title="OEE trend",
                columns=_bound_columns(),
                row_count=12,
                extent="A1:C13",
            ),
            WorkbookTable(
                table_id="tbl-assets",
                title="Asset registry",
                columns=(
                    WorkbookColumn(
                        column_id="col-asset",
                        header="Asset",
                        kind="string",
                        source_field="fields.asset_id",
                    ),
                ),
                row_count=4,
                extent="A1:A5",
            ),
            _local_table(),
        ),
        "named_ranges": (
            NamedRange(
                range_id="rng-oee", name="OEE_Values", sheet_id="sh-summary", extent="B2:B13"
            ),
        ),
        "bindings": (_analytical_binding(), _entity_binding()),
        "local_values": (
            LocalCellValue(
                table_id="tbl-inputs", row=0, column_id="col-assumption", value="changeover 40min"
            ),
        ),
    }
    values.update(overrides)
    return WorkbookDefinition.model_validate(values)


# --- AC: three-table workbook with stable IDs ---------------------------------


def test_workbook_carries_bound_entity_and_local_tables() -> None:
    workbook = _workbook()
    kinds = {binding.kind for binding in workbook.bindings}
    assert kinds == {"analytical_query", "entity_projection"}
    local_tables = [
        table
        for table in workbook.tables
        if all(column.kind == "local_only" for column in table.columns)
    ]
    assert [table.table_id for table in local_tables] == ["tbl-inputs"]
    assert workbook.tables[0].columns[0].column_id == "col-period"


# --- AC: bound tables never embed source rows ---------------------------------


def test_bound_tables_carry_schema_and_row_count_only() -> None:
    workbook = _workbook()
    raw = json.loads(workbook.model_dump_json())
    oee_table = next(table for table in raw["tables"] if table["table_id"] == "tbl-oee")
    assert oee_table["row_count"] == 12
    assert "rows" not in oee_table and "cells" not in oee_table


# --- AC: viewer-specific authorized projection --------------------------------


def test_projection_resolves_per_viewer_table_access() -> None:
    workbook = _workbook()
    analyst = authorized_projection(
        workbook, viewer="analyst", visible_table_ids=("tbl-oee", "tbl-inputs", "tbl-assets")
    )
    restricted = authorized_projection(workbook, viewer="auditor", visible_table_ids=("tbl-oee",))
    assert {table.table_id for table in analyst.tables} == {"tbl-oee", "tbl-inputs", "tbl-assets"}
    assert {table.table_id for table in restricted.tables} == {"tbl-oee"}
    assert all(binding.table_id == "tbl-oee" for binding in restricted.bindings)
    assert restricted.local_values == ()


# --- AC: local values are distinct from source truth --------------------------


def test_local_values_are_labeled_and_cannot_masquerade_as_source() -> None:
    workbook = _workbook()
    raw = json.loads(workbook.model_dump_json())
    for value in raw["local_values"]:
        table = next(t for t in raw["tables"] if t["table_id"] == value["table_id"])
        column = next(c for c in table["columns"] if c["column_id"] == value["column_id"])
        assert column["kind"] == "local_only"
    with pytest.raises(ValidationError, match="local_override_not_labeled"):
        WorkbookDefinition.model_validate(
            {
                **workbook.model_dump(mode="json"),
                "local_values": (
                    LocalCellValue(table_id="tbl-oee", row=0, column_id="col-oee", value=0.91),
                ),
            }
        )


# --- AC: drift surfaces state, never silent remap -----------------------------


def test_schema_drift_becomes_missing_source_without_remap() -> None:
    workbook = _workbook()
    drifted = reconcile_binding(
        workbook, "bnd-oee", observed_fields=("fields.period",)
    )
    binding = next(b for b in drifted.bindings if b.binding_id == "bnd-oee")
    states = {entry.column_id: entry.compatibility for entry in binding.mapping}
    assert states == {"col-period": "current", "col-oee": "missing_source"}
    # Mapping identity is untouched: column/field pairs are exactly as bound.
    assert [(entry.column_id, entry.source_field) for entry in binding.mapping] == [
        ("col-period", "fields.period"),
        ("col-oee", "fields.oee"),
    ]


def test_reconciliation_preserves_everything_else() -> None:
    workbook = _workbook()
    drifted = reconcile_binding(
        workbook, "bnd-oee", observed_fields=("fields.period", "fields.oee")
    )
    assert drifted.digest() == workbook.digest()


def test_reconcile_unknown_binding_is_rejected() -> None:
    with pytest.raises(WorkbookStudioError) as blocked:
        reconcile_binding(_workbook(), "bnd-ghost", observed_fields=("fields.period",))
    assert blocked.value.code == WorkbookStudioError.DUPLICATE_IDENTITY


# --- AC: shareable export without rows, credentials or cached data ------------


def test_shareable_definition_strips_local_values() -> None:
    workbook = _workbook()
    shared_payload = {
        key: value
        for key, value in workbook.model_dump(mode="json").items()
        if key != "local_values"
    }
    assert canonical_workbook_digest(shared_payload) == workbook.shareable_definition()
    raw = json.loads(workbook.model_dump_json())
    blob = json.dumps(raw)
    assert "credentials" not in blob and "password" not in blob


def test_binding_cannot_carry_query_text_or_credentials() -> None:
    with pytest.raises(ValidationError):
        DataBinding(
            binding_id="bnd-evil",
            kind="analytical_query",
            resource_prefix="SELECT * FROM secrets",
            table_id="tbl-oee",
            mapping=_analytical_binding().mapping,
        )


# --- hidden state is presentation only ----------------------------------------


def test_hidden_sheet_is_metadata_not_protection() -> None:
    workbook = _workbook()
    projection = authorized_projection(
        workbook, viewer="viewer", visible_table_ids=("tbl-oee", "tbl-inputs", "tbl-assets")
    )
    # The hidden sheet's tables remain resolvable to an authorized viewer;
    # visibility never removes or protects data by itself.
    assert any(sheet.visibility == "hidden" for sheet in workbook.sheets)
    assert {table.table_id for table in projection.tables} == {
        "tbl-oee", "tbl-inputs", "tbl-assets",
    }


# --- attack matrix ------------------------------------------------------------


def test_forged_source_ref_outside_tenant_is_cross_tenant() -> None:
    with pytest.raises(ValidationError, match="cross_tenant_workbook_reference"):
        _workbook(
            bindings=(
                DataBinding(
                    binding_id="bnd-evil",
                    kind="data_product",
                    resource_prefix="tenant-other.products.secret-dataset",
                    table_id="tbl-oee",
                    mapping=_analytical_binding().mapping,
                ),
            ),
        )


def test_hidden_field_binding_is_not_representable() -> None:
    with pytest.raises(ValidationError, match="bound columns must declare"):
        WorkbookColumn(column_id="col-ghost", header="Ghost", kind="string")


def test_duplicate_table_and_column_ids_are_rejected() -> None:
    with pytest.raises(ValidationError):
        _workbook(
            tables=(
                _workbook().tables[0],
                WorkbookTable(
                    table_id="tbl-oee",
                    title="Duplicate",
                    columns=_bound_columns(),
                ),
            )
        )
    with pytest.raises(ValidationError):
        WorkbookTable(
            table_id="tbl-x",
            title="Dup columns",
            columns=(
                WorkbookColumn(column_id="col-a", header="A", kind="local_only"),
                WorkbookColumn(column_id="col-a", header="A2", kind="local_only"),
            ),
        )


def test_huge_range_is_rejected_by_pattern() -> None:
    with pytest.raises(ValidationError):
        WorkbookTable(
            table_id="tbl-huge",
            title="Huge",
            columns=(WorkbookColumn(column_id="col-a", header="A", kind="local_only"),),
            extent="A1:ZZZ1048576",
        )


def test_cross_tenant_sheet_reference_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _workbook(
            named_ranges=(
                NamedRange(
                    range_id="rng-ghost", name="Ghost", sheet_id="sh-other", extent="A1:B2"
                ),
            )
        )


def test_local_value_on_unknown_table_or_column_is_rejected() -> None:
    with pytest.raises(ValidationError):
        _workbook(
            local_values=(
                LocalCellValue(table_id="tbl-ghost", row=0, column_id="col-a", value=1),
            )
        )
    with pytest.raises(ValidationError):
        _workbook(
            local_values=(
                LocalCellValue(table_id="tbl-inputs", row=0, column_id="col-ghost", value=1),
            )
        )


# --- round-trip and untrusted parsing -----------------------------------------


def test_round_trip_is_byte_stable_and_deterministic() -> None:
    workbook = _workbook()
    parsed = parse_workbook_contract(json.loads(workbook.model_dump_json()))
    assert parsed == workbook
    assert parsed.digest() == workbook.digest()


def test_digest_is_order_insensitive_and_tamper_evident() -> None:
    workbook = _workbook()
    raw = json.loads(workbook.model_dump_json())
    reordered = dict(reversed(list(raw.items())))
    assert canonical_workbook_digest(raw) == canonical_workbook_digest(reordered)
    tampered = dict(raw)
    tampered["title"] = "Tampered"
    assert canonical_workbook_digest(tampered) != workbook.digest()


def test_parse_rejects_future_major_with_dedicated_code() -> None:
    raw = json.loads(_workbook().model_dump_json())
    raw["schema_version"] = {"major": 2, "minor": 0}
    with pytest.raises(WorkbookStudioError) as blocked:
        parse_workbook_contract(raw)
    assert blocked.value.code == WorkbookStudioError.INCOMPATIBLE_VERSION


def test_parse_reports_malformed_payload_with_safe_code() -> None:
    with pytest.raises(WorkbookStudioError) as blocked:
        parse_workbook_contract("not-a-workbook")
    assert blocked.value.code == WorkbookStudioError.INVALID_WORKBOOK
