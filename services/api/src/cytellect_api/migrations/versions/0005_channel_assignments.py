"""Current explicit channel assignments without rewriting original scientific metadata."""
from alembic import op
from sqlalchemy import JSON, Column, Integer, String

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_channel_assignments", Column("workspace_id", String, primary_key=True),
                    Column("version", Integer, nullable=False), Column("assignments", JSON, nullable=False))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
