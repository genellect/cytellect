"""Private PoC schema; adopts only the preceding unversioned bootstrap schema."""

from alembic import op
from sqlalchemy import JSON, Boolean, Column, Float, Integer, MetaData, String, Table, inspect

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None

meta = MetaData()
workspaces = Table(
    "workspaces",
    meta,
    Column("id", String, primary_key=True),
    Column("owner", String, nullable=False, index=True),
    Column("title", String, nullable=False),
    Column("created", Float, nullable=False),
    Column("expires", Float, nullable=False),
    Column("deleted", Boolean, default=False, nullable=False),
    Column("active_revision", String),
    Column("bytes", Integer, default=0, nullable=False),
)
invitations = Table(
    "invitations",
    meta,
    Column("digest", String, primary_key=True),
    Column("expires", Float, nullable=False),
    Column("used", Boolean, default=False, nullable=False),
)
sessions = Table(
    "sessions",
    meta,
    Column("digest", String, primary_key=True),
    Column("owner", String, nullable=False),
    Column("expires", Float, nullable=False),
    Column("revoked", Boolean, default=False, nullable=False),
)
fields = Table(
    "fields",
    meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=False, index=True),
    Column("metadata", JSON, nullable=False),
    Column("image_info", JSON, nullable=False),
    Column("synthetic", Boolean, default=False, nullable=False),
)
revisions = Table(
    "revisions",
    meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=False, index=True),
    Column("parent_id", String),
    Column("config", JSON, nullable=False),
    Column("state", String, nullable=False),
    Column("reviewed", Boolean, default=False, nullable=False),
    Column("review_record", JSON),
    Column("result_dir", String),
    Column("created", Float, nullable=False),
)
jobs = Table(
    "jobs",
    meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=False, index=True),
    Column("revision_id", String, nullable=False),
    Column("kind", String, nullable=False),
    Column("state", String, nullable=False),
    Column("payload", JSON, nullable=False),
    Column("created", Float, nullable=False),
    Column("lease", String),
    Column("lease_until", Float),
    Column("attempts", Integer, default=0, nullable=False),
    Column("error", String),
    Column("result_dir", String),
)
attempts = Table(
    "job_attempts",
    meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=False, index=True),
    Column("job_id", String, nullable=False),
    Column("created", Float, nullable=False),
)
tables = Table(
    "numerical_tables",
    meta,
    Column("id", String, primary_key=True),
    Column("workspace_id", String, nullable=False, index=True),
    Column("metadata", JSON, nullable=False),
    Column("row_count", Integer, nullable=False),
    Column("created", Float, nullable=False),
)
events = Table(
    "events",
    meta,
    Column("id", String, primary_key=True),
    Column("kind", String, nullable=False),
    Column("created", Float, nullable=False),
    Column("data", JSON, nullable=False),
)


def upgrade():
    bind = op.get_bind()
    for table in meta.sorted_tables:
        table.create(bind, checkfirst=True)
    if "review_record" not in {column["name"] for column in inspect(bind).get_columns("revisions")}:
        op.add_column("revisions", Column("review_record", JSON))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported; restore a schema-compatible offline snapshot")
