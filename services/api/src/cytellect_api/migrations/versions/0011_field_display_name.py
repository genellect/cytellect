"""Researcher-visible field names for figure labels; existing fields keep none."""

from alembic import op
from sqlalchemy import Column, String

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("fields", Column("display_name", String, nullable=True))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
