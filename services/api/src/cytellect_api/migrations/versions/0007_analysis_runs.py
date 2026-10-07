"""Durable analysis requests and dependency candidates."""

from alembic import op
from sqlalchemy import JSON, Column, Float, Integer, String

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_analysis_runs",
        Column("id", String, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("request_id", String, nullable=False),
        Column("request_fingerprint", String, nullable=False),
        Column("spec_version", Integer, nullable=False),
        Column("spec_snapshot", JSON, nullable=False),
        Column("selection_snapshot", JSON, nullable=False),
        Column("assignments_snapshot", JSON, nullable=False),
        Column("target", String, nullable=False),
        Column("state", String, nullable=False),
        Column("steps", JSON, nullable=False),
        Column("created", Float, nullable=False),
        Column("updated", Float, nullable=False),
    )
    op.create_index("ix_workspace_analysis_runs_workspace_id", "workspace_analysis_runs", ["workspace_id"])
    op.create_index(
        "uq_analysis_run_request", "workspace_analysis_runs", ["workspace_id", "request_id"], unique=True
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
