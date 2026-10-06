"""Server-owned workspace adoption and reasoned exclusion ledger."""
from alembic import op
from sqlalchemy import JSON, Column, Integer, String

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_selections", Column("workspace_id", String, primary_key=True),
                    Column("version", Integer, nullable=False), Column("entries", JSON, nullable=False))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
