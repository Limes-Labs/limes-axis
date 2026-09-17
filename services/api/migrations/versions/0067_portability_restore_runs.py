"""Portability restore run/step lifecycle tables.

Revision ID: 0067_portability_restore_runs
Revises: 0066_s3_source_checkpoint
"""

import sqlalchemy as sa
from alembic import op

revision = "0067_portability_restore_runs"
down_revision = "0066_s3_source_checkpoint"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "portability_restore_runs",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("target_tenant_id", sa.String(80), nullable=False),
        sa.Column("bundle_digest", sa.String(64), nullable=False),
        sa.Column("plan_digest", sa.String(64), nullable=False),
        sa.Column("generation", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("acknowledged_by", sa.String(160), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("authorized_by", sa.String(160), nullable=False),
        sa.Column("authorized_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("current_step", sa.String(120), nullable=True),
        sa.Column("steps_completed", sa.JSON(), nullable=False),
        sa.Column("steps_failed", sa.JSON(), nullable=False),
        sa.Column("fenced", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'running', 'suspended_quarantined', 'completed', 'aborted')",
            name="ck_portability_restore_runs_state",
        ),
        sa.UniqueConstraint(
            "target_tenant_id",
            "bundle_digest",
            "plan_digest",
            "generation",
            name="uq_portability_restore_runs_target_bundle_plan_generation",
        ),
    )
    op.create_index(
        "ix_portability_restore_runs_target_state",
        "portability_restore_runs",
        ["target_tenant_id", "state"],
    )
    op.create_table(
        "portability_restore_steps",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Uuid(),
            sa.ForeignKey("portability_restore_runs.id"),
            nullable=False,
        ),
        sa.Column("component_id", sa.String(120), nullable=False),
        sa.Column("sequence", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(24), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("evidence_digest", sa.String(64), nullable=True),
        sa.Column("failure_code", sa.String(80), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "state IN ('pending', 'in_progress', 'completed', 'failed', 'blocked')",
            name="ck_portability_restore_steps_state",
        ),
        sa.UniqueConstraint(
            "run_id",
            "component_id",
            name="uq_portability_restore_steps_run_component",
        ),
        sa.UniqueConstraint(
            "run_id",
            "sequence",
            name="uq_portability_restore_steps_run_sequence",
        ),
    )


def downgrade() -> None:
    op.drop_table("portability_restore_steps")
    op.drop_index(
        "ix_portability_restore_runs_target_state", table_name="portability_restore_runs"
    )
    op.drop_table("portability_restore_runs")
