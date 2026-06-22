"""connector registry reference record

Revision ID: 0023_connector_registry_reference
Revises: 0022_demo_reference_records
Create Date: 2026-06-22
"""

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import uuid4

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0023_connector_registry_reference"
down_revision: str | None = "0022_demo_reference_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CONNECTOR_REGISTRY_PAYLOAD = {
    "tenant_id": "tenant_demo_manufacturing",
    "plant_name": "Ravenna Works",
    "scenario": "Plant Operations Cockpit",
    "registry_status": "watch",
    "metrics": [
        {
            "label": "Connector Manifests",
            "value": "2",
            "detail": "Public-safe connector manifests available for preview",
            "status": "ready",
        },
        {
            "label": "CSV Preview",
            "value": "Ready",
            "detail": "File connector can validate and map local CSV rows",
            "status": "ready",
        },
        {
            "label": "External DB Preview",
            "value": "Metadata Only",
            "detail": "Database connector preview uses profile ids and handles only",
            "status": "ready",
        },
        {
            "label": "Live Sync",
            "value": "Blocked",
            "detail": "No live connector mutation is enabled in this foundation slice",
            "status": "watch",
        },
    ],
    "connectors": [
        {
            "manifest": {
                "connector_id": "file_csv_manufacturing_assets",
                "display_name": "Manufacturing assets CSV",
                "connector_type": "file_csv",
                "version": "2026-06-22",
                "source_type": "file",
                "sync_modes": ["preview", "manual_import"],
                "runtime_boundary": "axis-connector-sandbox",
                "required_permissions": [
                    "connectors:read",
                    "connectors:file_csv:preview",
                ],
                "credential_requirements": {
                    "storage": "none",
                    "required_secret_refs": [],
                    "notes": [
                        "Local CSV preview does not require stored credentials.",
                        "Future connector runs must reference credential handles, not raw values.",
                    ],
                },
                "schema_fields": [
                    {
                        "source_column": "asset_id",
                        "target_field": "node_id",
                        "ontology_target": "manufacturing_asset",
                        "data_type": "string",
                        "required": True,
                        "description": ("Stable asset identifier used as the ontology node id."),
                    },
                    {
                        "source_column": "asset_name",
                        "target_field": "display_name",
                        "ontology_target": "manufacturing_asset",
                        "data_type": "string",
                        "required": True,
                        "description": "Human-readable manufacturing asset name.",
                    },
                    {
                        "source_column": "domain",
                        "target_field": "domain",
                        "ontology_target": "manufacturing_asset",
                        "data_type": "string",
                        "required": True,
                        "description": (
                            "Operational domain such as Operations, Quality or Maintenance."
                        ),
                    },
                    {
                        "source_column": "station",
                        "target_field": "source_system_ref",
                        "ontology_target": "manufacturing_asset",
                        "data_type": "string",
                        "required": True,
                        "description": ("Plant station, line or source-system reference."),
                    },
                    {
                        "source_column": "risk_level",
                        "target_field": "risk_level",
                        "ontology_target": "manufacturing_asset",
                        "data_type": "string",
                        "required": True,
                        "description": (
                            "Public-safe risk posture used for demo governance checks."
                        ),
                    },
                ],
                "mapping_notes": [
                    "CSV preview maps rows to ontology entity proposals only.",
                    "Manual import remains approval-gated and workflow-signaled before execution.",
                    "Raw file content is never returned in API responses.",
                ],
            },
            "runtime_policy": {
                "allowed_operations": [
                    "schema_validate",
                    "preview_mapping",
                    "dry_run_diff",
                ],
                "blocked_operations": [
                    "live_write",
                    "credential_capture",
                    "external_egress",
                ],
                "egress_policy": "no-external-egress",
                "max_file_size_mb": 5,
                "row_limit": 500,
                "payload_policy": "redacted-preview-only",
            },
            "preview_sample": {
                "file_name": "manufacturing-assets-demo.csv",
                "record_count": 3,
                "headers": [
                    "asset_id",
                    "asset_name",
                    "domain",
                    "station",
                    "risk_level",
                ],
                "sample_rows": [
                    {
                        "asset_id": "asset_line_2_packaging",
                        "asset_name": "Line 2 Packaging",
                        "domain": "Operations",
                        "station": "Line 2",
                        "risk_level": "high",
                    },
                    {
                        "asset_id": "asset_press_4",
                        "asset_name": "Press 4",
                        "domain": "Maintenance",
                        "station": "Press 4",
                        "risk_level": "medium",
                    },
                ],
            },
            "connector_status": "watch",
        },
        {
            "manifest": {
                "connector_id": "external_db_operational_mirror",
                "display_name": "Postgres operational mirror",
                "connector_type": "external_db",
                "version": "2026-06-22",
                "source_type": "database",
                "sync_modes": ["schema_preview", "manual_import"],
                "runtime_boundary": "axis-connector-sandbox",
                "required_permissions": [
                    "connectors:read",
                    "connectors:external_db:preview",
                ],
                "credential_requirements": {
                    "storage": "external_reference",
                    "required_secret_refs": ["cred_external_db_readonly"],
                    "notes": [
                        "Database preview uses credential handles and profile ids only.",
                        "Raw DSNs, SQL text and credential values are rejected.",
                    ],
                },
                "schema_fields": [
                    {
                        "source_column": "order_id",
                        "target_field": "node_id",
                        "ontology_target": "production_order",
                        "data_type": "string",
                        "required": True,
                        "description": (
                            "Stable production order identifier from the source table."
                        ),
                    },
                    {
                        "source_column": "asset_id",
                        "target_field": "asset_ref",
                        "ontology_target": "production_order",
                        "data_type": "string",
                        "required": True,
                        "description": (
                            "Manufacturing asset reference linked by policy-aware import."
                        ),
                    },
                    {
                        "source_column": "work_center",
                        "target_field": "source_system_ref",
                        "ontology_target": "production_order",
                        "data_type": "string",
                        "required": True,
                        "description": ("Operational work center or line reference."),
                    },
                    {
                        "source_column": "status",
                        "target_field": "operational_status",
                        "ontology_target": "production_order",
                        "data_type": "string",
                        "required": True,
                        "description": ("Public-safe order status used for preview mapping."),
                    },
                    {
                        "source_column": "risk_level",
                        "target_field": "risk_level",
                        "ontology_target": "production_order",
                        "data_type": "string",
                        "required": True,
                        "description": ("Governance risk posture used for import controls."),
                    },
                ],
                "mapping_notes": [
                    "Database preview inspects declared metadata only; no live SQL is executed.",
                    "Imports remain proposal-only until approval, workflow and policy gates pass.",
                    "Connection details stay outside Axis as credential handles and profiles.",
                ],
            },
            "runtime_policy": {
                "allowed_operations": [
                    "schema_validate",
                    "metadata_preview",
                    "dry_run_diff",
                ],
                "blocked_operations": [
                    "live_query",
                    "live_write",
                    "credential_capture",
                    "external_egress",
                ],
                "egress_policy": "no-external-egress",
                "max_file_size_mb": 5,
                "row_limit": 100,
                "payload_policy": "metadata-only-redacted-preview",
            },
            "preview_sample": {
                "file_name": "profile_postgres_ops_readonly:operations.production_orders",
                "record_count": 2,
                "headers": [
                    "order_id",
                    "asset_id",
                    "work_center",
                    "status",
                    "risk_level",
                ],
                "sample_rows": [
                    {
                        "order_id": "order_po_10045",
                        "asset_id": "asset_line_2_packaging",
                        "work_center": "Line 2",
                        "status": "blocked",
                        "risk_level": "high",
                    },
                    {
                        "order_id": "order_po_10046",
                        "asset_id": "asset_press_4",
                        "work_center": "Press 4",
                        "status": "scheduled",
                        "risk_level": "medium",
                    },
                ],
            },
            "connector_status": "watch",
        },
    ],
    "connector_notes": [
        "Connector manifests are public-safe and preview-only.",
        "The file/CSV connector maps rows to ontology proposals without writing data.",
        "The external DB connector previews declared metadata without live SQL.",
        "Credential retrieval, scheduled sync and production connector runs remain future work.",
    ],
}


def upgrade() -> None:
    reference_table = sa.table(
        "demo_reference_records",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("tenant_id", sa.String(length=80)),
        sa.column("surface", sa.String(length=120)),
        sa.column("reference_id", sa.String(length=180)),
        sa.column("status", sa.String(length=80)),
        sa.column("source", sa.String(length=120)),
        sa.column("version", sa.String(length=80)),
        sa.column("payload", postgresql.JSONB(astext_type=sa.Text())),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
    )
    now = datetime(2026, 6, 22, 0, 0, tzinfo=UTC)
    op.bulk_insert(
        reference_table,
        [
            {
                "id": uuid4(),
                "tenant_id": "tenant_demo_manufacturing",
                "surface": "connectors",
                "reference_id": "manufacturing-connector-registry",
                "status": "active",
                "source": "bootstrap",
                "version": "2026-06-22",
                "payload": CONNECTOR_REGISTRY_PAYLOAD,
                "created_at": now,
                "updated_at": now,
            }
        ],
    )


def downgrade() -> None:
    op.execute(
        sa.text(
            "DELETE FROM demo_reference_records "
            "WHERE tenant_id = 'tenant_demo_manufacturing' "
            "AND surface = 'connectors' "
            "AND reference_id = 'manufacturing-connector-registry'"
        )
    )
