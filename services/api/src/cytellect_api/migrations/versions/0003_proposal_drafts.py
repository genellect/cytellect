"""Workspace-scoped private proposal cache and durable request claims."""
from alembic import op
from sqlalchemy import JSON, Column, Float, String

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "proposal_drafts",
        Column("id", String, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("cache_key", String, nullable=False),
        Column("request_id", String, nullable=False),
        Column("state", String, nullable=False),
        Column("created", Float, nullable=False),
        Column("lease_until", Float, nullable=False),
        Column("proposal", JSON),
    )
    op.create_index("ix_proposal_drafts_workspace_id", "proposal_drafts", ["workspace_id"])
    op.create_index("uq_proposal_workspace_key", "proposal_drafts", ["workspace_id", "cache_key"], unique=True)


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported; restore a schema-compatible offline snapshot")
