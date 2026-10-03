"""Local SQLite transactions; CAS leases prevent stale workers publishing."""

import contextlib
import hashlib
import secrets
import time
import uuid
from pathlib import Path

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Float,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    event,
    select,
    update,
)

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
    Column("analysis_plan", JSON),
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
    Column("client_upload_id", String),
    Column("upload_fingerprint", String),
    Index("uq_fields_workspace_client_upload_id", "workspace_id", "client_upload_id", unique=True),
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


def uid():
    return str(uuid.uuid4())


def digest(token):
    return hashlib.sha256(token.encode()).hexdigest()


class Store:
    def __init__(self, root: Path):
        self.root = root.resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.engine = create_engine(
            "sqlite:///" + (self.root / "cytellect.sqlite").as_posix(),
            connect_args={"check_same_thread": False, "timeout": 30},
        )

        @event.listens_for(self.engine, "connect")
        def pragma(dbapi, _):
            dbapi.execute("PRAGMA journal_mode=WAL")
            dbapi.execute("PRAGMA foreign_keys=ON")
            dbapi.execute("PRAGMA busy_timeout=30000")

        from alembic import command
        from alembic.config import Config

        migration = Config()
        migration.set_main_option("script_location", str(Path(__file__).parent / "migrations"))
        with self.transaction() as conn:
            migration.attributes["connection"] = conn
            command.upgrade(migration, "head")

    @contextlib.contextmanager
    def transaction(self):
        with self.engine.connect() as conn:
            conn.exec_driver_sql("BEGIN IMMEDIATE")
            try:
                yield conn
                conn.commit()
            except BaseException:
                conn.rollback()
                raise

    def one(self, table, **filters):
        with self.engine.connect() as conn:
            return conn.execute(select(table).filter_by(**filters)).mappings().first()

    def rows(self, table, **filters):
        with self.engine.connect() as conn:
            return list(conn.execute(select(table).filter_by(**filters)).mappings())

    def invite(self, ttl=86400):
        token = secrets.token_urlsafe(32)
        with self.transaction() as c:
            c.execute(
                invitations.insert().values(digest=digest(token), expires=time.time() + ttl, used=False)
            )
        return token

    def claim(self):
        now = time.time()
        with self.transaction() as c:
            expired = (
                c.execute(select(jobs).where(jobs.c.state == "running", jobs.c.lease_until < now))
                .mappings()
                .all()
            )
            for job in expired:
                state = "queued" if job["attempts"] < 2 else "failed"
                c.execute(
                    update(jobs)
                    .where(jobs.c.id == job["id"])
                    .values(
                        state=state, lease=None, error="worker_interrupted" if state == "failed" else None
                    )
                )
                if state == "failed" and job["kind"] == "analysis":
                    c.execute(
                        update(revisions).where(revisions.c.id == job["revision_id"]).values(state="failed")
                    )
            # Exactly one live scientific task across multiple accidental worker processes.
            if c.execute(
                select(jobs.c.id).where(jobs.c.lease_until > now, jobs.c.state.in_(["running", "cancelled"]))
            ).first():
                return None
            job = (
                c.execute(
                    select(jobs)
                    .join(workspaces, jobs.c.workspace_id == workspaces.c.id)
                    .where(
                        jobs.c.state == "queued", workspaces.c.deleted.is_(False), workspaces.c.expires > now
                    )
                    .order_by(jobs.c.created)
                    .limit(1)
                )
                .mappings()
                .first()
            )
            if job is None:
                return None
            lease = uid()
            c.execute(
                update(jobs)
                .where(jobs.c.id == job["id"])
                .values(state="running", lease=lease, lease_until=now + 60, attempts=job["attempts"] + 1)
            )
            if job["kind"] == "analysis":
                c.execute(
                    update(revisions).where(revisions.c.id == job["revision_id"]).values(state="running")
                )
            return {**dict(job), "lease": lease, "attempts": job["attempts"] + 1}

    def heartbeat(self, job):
        with self.transaction() as c:
            workspace = (
                c.execute(select(workspaces).where(workspaces.c.id == job["workspace_id"])).mappings().first()
            )
            if not workspace or workspace["deleted"] or workspace["expires"] <= time.time():
                return False
            result = c.execute(
                update(jobs)
                .where(
                    jobs.c.id == job["id"],
                    jobs.c.lease == job["lease"],
                    jobs.c.state == "running",
                    jobs.c.lease_until > time.time(),
                )
                .values(lease_until=time.time() + 60)
            )
            return result.rowcount == 1

    def finish(self, job, result_dir=None, error=None):
        state = "failed" if error else "succeeded"
        with self.transaction() as c:
            workspace = (
                c.execute(select(workspaces).where(workspaces.c.id == job["workspace_id"])).mappings().first()
            )
            if not workspace or workspace["deleted"] or workspace["expires"] <= time.time():
                return False
            result = c.execute(
                update(jobs)
                .where(
                    jobs.c.id == job["id"],
                    jobs.c.lease == job["lease"],
                    jobs.c.state == "running",
                    jobs.c.lease_until > time.time(),
                )
                .values(state=state, result_dir=result_dir, error=error)
            )
            if result.rowcount != 1:
                return False
            if job["kind"] == "analysis":
                c.execute(
                    update(revisions)
                    .where(revisions.c.id == job["revision_id"])
                    .values(state=state, result_dir=result_dir)
                )
            c.execute(
                events.insert().values(
                    id=uid(),
                    kind="job_finished",
                    created=time.time(),
                    data={"kind": job["kind"], "state": state, "attempt": job["attempts"]},
                )
            )
            return True

    def safe_path(self, *parts):
        target = self.root.joinpath(*parts).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError("invalid_storage_path")
        return target
