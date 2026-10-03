"""Add scoped upload identity and an optional saved analysis plan without rewriting data."""

from alembic import op
from sqlalchemy import JSON, Column, String

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fields", Column("client_upload_id", String, nullable=True))
    op.add_column("fields", Column("upload_fingerprint", String, nullable=True))
    op.create_index(
        "uq_fields_workspace_client_upload_id", "fields",
        ["workspace_id", "client_upload_id"], unique=True,
    )
    op.add_column("workspaces", Column("analysis_plan", JSON, nullable=True))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported; restore a schema-compatible offline snapshot")
