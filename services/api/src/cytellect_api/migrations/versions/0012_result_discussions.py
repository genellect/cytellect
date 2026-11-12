"""Model-drafted discussions of saved comparisons, stored with the result job they discuss."""

from alembic import op
from sqlalchemy import JSON, Column, Float, String

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "result_discussions",
        Column("id", String, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("job_id", String, nullable=False),
        Column("cache_key", String, nullable=False),
        Column("request_id", String, nullable=False),
        Column("state", String, nullable=False),
        Column("created", Float, nullable=False),
        Column("lease_until", Float, nullable=False),
        Column("discussion", JSON),
    )
    op.create_index("ix_result_discussions_workspace_id", "result_discussions", ["workspace_id"])
    op.create_index("ix_result_discussions_job_id", "result_discussions", ["job_id"])
    op.create_index("uq_result_discussion_workspace_key", "result_discussions", ["workspace_id", "cache_key"], unique=True)


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
