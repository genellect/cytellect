"""Workspace analysis drafts with compare-and-swap versions."""
from alembic import op
from sqlalchemy import JSON, Column, Integer, String

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table("workspace_analysis_specs", Column("workspace_id", String, primary_key=True),
                    Column("version", Integer, nullable=False), Column("spec", JSON, nullable=False))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
