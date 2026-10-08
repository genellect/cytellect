"""Non-destructive field/reference relationships."""

from alembic import op
from sqlalchemy import JSON, Column, Integer, String

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "workspace_field_links",
        Column("workspace_id", String, primary_key=True),
        Column("version", Integer, nullable=False),
        Column("entries", JSON, nullable=False),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
