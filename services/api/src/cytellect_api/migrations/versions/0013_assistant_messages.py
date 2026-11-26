"""The researcher's messages to the AI and their answers, per workspace (#284 W2)."""

from alembic import op
from sqlalchemy import JSON, Boolean, Column, Float, String

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "assistant_messages",
        Column("id", String, primary_key=True),
        Column("workspace_id", String, nullable=False),
        Column("field_id", String),
        Column("created", Float, nullable=False),
        Column("text", String, nullable=False),
        Column("state", String, nullable=False),
        Column("reply", String),
        Column("applicable", Boolean),
        Column("reasons", JSON),
        Column("stage", String),
        Column("request_id", String),
        Column("draft_id", String),
        Column("effect", String, nullable=False),
    )
    op.create_index("ix_assistant_messages_workspace_id", "assistant_messages", ["workspace_id"])


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
