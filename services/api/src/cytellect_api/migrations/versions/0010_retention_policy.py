"""Installation-wide workspace retention policy recorded with the data."""

from alembic import op
from sqlalchemy import Column, Float, Integer, String

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "retention_policy",
        Column("id", Integer, primary_key=True),
        Column("mode", String, nullable=False),
        Column("activated", Float, nullable=False),
    )


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
