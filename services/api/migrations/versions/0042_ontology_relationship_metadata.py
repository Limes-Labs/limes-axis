"""ontology relationship metadata

Revision ID: 0042_ontology_relationship_metadata
Revises: 0041_platform_notification_acknowledgements
Create Date: 2026-06-30
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0042_ontology_relationship_metadata"
down_revision: str | None = "0041_platform_notification_acknowledgements"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _relationship_owner_role(permission_scope: str) -> str:
    owner_by_scope = {
        "agents": "Agent Operations Steward",
        "approvals": "Approval Steward",
        "audit": "Audit Steward",
        "maintenance": "Maintenance Steward",
        "operations": "Operations Steward",
        "quality": "Quality Steward",
        "security": "Security Steward",
        "supply": "Supply Steward",
    }
    return owner_by_scope.get(permission_scope.split(":", maxsplit=1)[0], "Ontology Steward")


def _relationship_metadata(relationship_id: str, permission_scope: str) -> dict:
    return {
        "owner_role": _relationship_owner_role(permission_scope),
        "source_adapter": "axis-reference-ontology",
        "confidence": 0.9,
        "evidence_refs": [f"ontology:{relationship_id}"],
        "valid_from": "2026-06-21T16:30:00+02:00",
        "valid_to": None,
        "last_verified_at": "2026-06-21T16:30:00+02:00",
        "verification_status": "reference_verified",
    }


def _ontology_reference_payload() -> dict | None:
    row = op.get_bind().execute(
        sa.text(
            "SELECT payload FROM demo_reference_records "
            "WHERE tenant_id = 'tenant_demo_manufacturing' "
            "AND surface = 'ontology' "
            "AND reference_id = 'manufacturing-ontology'"
        )
    ).mappings().first()
    if row is None:
        return None
    return dict(row["payload"])


def _write_ontology_reference_payload(payload: dict) -> None:
    statement = sa.text(
        "UPDATE demo_reference_records "
        "SET payload = :payload "
        "WHERE tenant_id = 'tenant_demo_manufacturing' "
        "AND surface = 'ontology' "
        "AND reference_id = 'manufacturing-ontology'"
    ).bindparams(sa.bindparam("payload", type_=postgresql.JSONB))
    op.get_bind().execute(statement, {"payload": payload})


def upgrade() -> None:
    payload = _ontology_reference_payload()
    if payload is None:
        return

    for relationship in payload.get("relationships", []):
        relationship.setdefault(
            "metadata",
            _relationship_metadata(
                relationship["relationship_id"],
                relationship["permission_scope"],
            ),
        )

    _write_ontology_reference_payload(payload)


def downgrade() -> None:
    payload = _ontology_reference_payload()
    if payload is None:
        return

    for relationship in payload.get("relationships", []):
        relationship.pop("metadata", None)

    _write_ontology_reference_payload(payload)
