from pathlib import Path


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
