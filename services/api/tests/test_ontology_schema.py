from pathlib import Path

from axis_api.ontology.mutations import OntologyMutationRequest


def test_meta_ontology_schema_contains_required_primitives() -> None:
    schema = Path("src/axis_api/ontology/schema.tql").read_text()
    for primitive in [
        "axis_actor",
        "axis_organization",
        "axis_asset",
        "axis_process",
        "axis_workflow",
        "axis_operation",
        "axis_event",
        "axis_decision",
        "axis_risk",
        "axis_policy",
        "axis_document",
        "axis_data_source",
        "axis_system",
        "axis_permission_scope",
        "axis_approval",
        "axis_audit_event",
    ]:
        assert f"entity {primitive}" in schema


def test_connector_proposal_promotion_typeql_is_public_safe() -> None:
    request = OntologyMutationRequest(
        tenant_id="tenant_demo_manufacturing",
        connector_id="file_csv_manufacturing_assets",
        promotion_id="promote_asset_line_2_packaging_20260622",
        proposal_id="proposal_asset_line_2_packaging",
        manual_import_id="import_assets_manual_20260622",
        actor_id="plant-operations-owner-role",
        node_id="asset_line_2_packaging",
        node_type="asset",
        ontology_type="manufacturing_asset",
        field_summary={
            "asset_name": 'Line 2 "Packaging"',
            "domain": "Operations",
            "station": "Line 2",
            "risk_level": "high",
        },
        evidence_refs=["manufacturing-assets-demo.csv"],
    )

    assert request.typeql.startswith("insert")
    assert 'has display_name "Line 2 \\"Packaging\\""' in request.typeql
    assert 'has source_system_ref "Line 2"' in request.typeql
    assert "axis_asset" in request.typeql
    assert "csv_content" not in request.typeql.lower()
    assert request.audit_payload["field_summary_keys"] == [
        "asset_name",
        "domain",
        "risk_level",
        "station",
    ]
