"""model endpoints and invocations

Revision ID: 0050_model_endpoints_and_invocations
Revises: 0049_tenant_usage_records
Create Date: 2026-07-10
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0050_model_endpoints_and_invocations"
down_revision: str | None = "0049_tenant_usage_records"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "model_endpoints",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("endpoint_id", sa.String(length=160), nullable=False),
        sa.Column("display_name", sa.String(length=200), nullable=False),
        sa.Column("provider_type", sa.String(length=80), nullable=False),
        sa.Column("hosting_boundary", sa.String(length=80), nullable=False),
        sa.Column("base_url", sa.String(length=500), nullable=False),
        sa.Column("default_model", sa.String(length=160), nullable=False),
        sa.Column("task_types", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("status", sa.String(length=40), nullable=False),
        sa.Column("credential_handle_id", sa.String(length=160), nullable=True),
        sa.Column("egress_policy_id", sa.String(length=180), nullable=True),
        sa.Column(
            "cost_input_per_1k",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "cost_output_per_1k",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("created_by", sa.String(length=160), nullable=False),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=False),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "endpoint_id",
            name="uq_model_endpoints_tenant_endpoint",
        ),
    )
    for column_name in (
        "tenant_id",
        "endpoint_id",
        "provider_type",
        "hosting_boundary",
        "status",
        "credential_handle_id",
        "egress_policy_id",
        "created_by",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_model_endpoints_{column_name}",
            "model_endpoints",
            [column_name],
        )

    op.create_table(
        "model_invocations",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("tenant_id", sa.String(length=80), nullable=False),
        sa.Column("idempotency_key", sa.String(length=200), nullable=False),
        sa.Column("status", sa.String(length=60), nullable=False),
        sa.Column("task_type", sa.String(length=120), nullable=False),
        sa.Column("endpoint_id", sa.String(length=160), nullable=True),
        sa.Column("provider_type", sa.String(length=80), nullable=True),
        sa.Column("hosting_boundary", sa.String(length=80), nullable=True),
        sa.Column("model_id", sa.String(length=160), nullable=True),
        sa.Column("requested_by", sa.String(length=160), nullable=False),
        sa.Column("route_decision", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column(
            "permission_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
        ),
        sa.Column(
            "platform_policy_decision",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=True,
        ),
        sa.Column("egress_decision", sa.String(length=80), nullable=False),
        sa.Column("prompt_sha256", sa.String(length=64), nullable=False),
        sa.Column("response_sha256", sa.String(length=64), nullable=True),
        sa.Column("prompt_excerpt", sa.Text(), nullable=True),
        sa.Column("response_excerpt", sa.Text(), nullable=True),
        sa.Column("input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("output_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("latency_ms", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "estimated_cost_eur",
            sa.Numeric(precision=12, scale=6),
            nullable=False,
            server_default="0",
        ),
        sa.Column("provider_request_ref", sa.String(length=240), nullable=True),
        sa.Column("error_code", sa.String(length=120), nullable=True),
        sa.Column("audit_event_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("audit_event_type", sa.String(length=120), nullable=True),
        sa.Column("notes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id",
            "idempotency_key",
            name="uq_model_invocations_tenant_idempotency",
        ),
    )
    for column_name in (
        "tenant_id",
        "idempotency_key",
        "status",
        "task_type",
        "endpoint_id",
        "hosting_boundary",
        "model_id",
        "requested_by",
        "egress_decision",
        "prompt_sha256",
        "response_sha256",
        "error_code",
        "audit_event_type",
    ):
        op.create_index(
            f"ix_model_invocations_{column_name}",
            "model_invocations",
            [column_name],
        )
    # Composite index backing the newest-first tenant listing keyset.
    op.create_index(
        "ix_model_invocations_tenant_created_at",
        "model_invocations",
        ["tenant_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_model_invocations_tenant_created_at",
        table_name="model_invocations",
    )
    for column_name in (
        "audit_event_type",
        "error_code",
        "response_sha256",
        "prompt_sha256",
        "egress_decision",
        "requested_by",
        "model_id",
        "hosting_boundary",
        "endpoint_id",
        "task_type",
        "status",
        "idempotency_key",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_model_invocations_{column_name}",
            table_name="model_invocations",
        )
    op.drop_table("model_invocations")
    for column_name in (
        "audit_event_type",
        "created_by",
        "egress_policy_id",
        "credential_handle_id",
        "status",
        "hosting_boundary",
        "provider_type",
        "endpoint_id",
        "tenant_id",
    ):
        op.drop_index(
            f"ix_model_endpoints_{column_name}",
            table_name="model_endpoints",
        )
    op.drop_table("model_endpoints")
