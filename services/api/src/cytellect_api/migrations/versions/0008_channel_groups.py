"""Pin existing channel assignments to acquired fields; later imports never inherit roles silently."""
from alembic import op
from sqlalchemy import JSON, Column, column, select, table

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("workspace_channel_assignments", Column("global_field_ids", JSON, nullable=False, server_default="[]"))
    op.add_column("workspace_channel_assignments", Column("groups", JSON, nullable=False, server_default="[]"))
    conn = op.get_bind()
    assignments = table("workspace_channel_assignments", column("workspace_id"), column("global_field_ids", JSON))
    fields = table("fields", column("workspace_id"), column("id"))
    for wid in conn.execute(select(assignments.c.workspace_id)).scalars():
        ids = list(conn.execute(select(fields.c.id).where(fields.c.workspace_id == wid)).scalars())
        conn.execute(assignments.update().where(assignments.c.workspace_id == wid).values(global_field_ids=ids))


def downgrade():
    raise RuntimeError("Destructive downgrade is unsupported")
