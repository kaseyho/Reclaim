from contextlib import contextmanager
from copy import deepcopy
from datetime import timedelta
import hashlib
import secrets
import threading
from pathlib import Path
from sqlalchemy import JSON, DateTime, Integer, String, Text, create_engine, select, update
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker
from .schemas import now


class Base(DeclarativeBase):
    pass


class Workspace(Base):
    __tablename__ = "workspaces"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    owner: Mapped[str | None] = mapped_column(String(100), nullable=True)
    expires_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    revision: Mapped[int] = mapped_column(Integer, default=0)
    state: Mapped[dict] = mapped_column(JSON)


class Membership(Base):
    __tablename__ = "memberships"
    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(80), index=True)
    actor_id: Mapped[str] = mapped_column(String(80))


class Job(Base):
    __tablename__ = "jobs"
    id: Mapped[str] = mapped_column(String(80), primary_key=True)
    workspace_id: Mapped[str] = mapped_column(String(80), index=True)
    kind: Mapped[str] = mapped_column(String(40))
    entity_id: Mapped[str] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(30), default="QUEUED", index=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    generation: Mapped[int] = mapped_column(Integer, default=1)
    available_at: Mapped[object] = mapped_column(DateTime(timezone=True))
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


class Webhook(Base):
    __tablename__ = "webhooks"
    id: Mapped[str] = mapped_column(String(120), primary_key=True)
    body: Mapped[dict] = mapped_column(JSON)


class JournalBase(DeclarativeBase):
    pass


class PaymentOperation(JournalBase):
    __tablename__="payment_operations"
    id: Mapped[str] = mapped_column(String(80),primary_key=True)
    entity_id: Mapped[str] = mapped_column(String(100),index=True)
    kind: Mapped[str] = mapped_column(String(30))
    body: Mapped[dict] = mapped_column(JSON)


class Store:
    """Transactional aggregate + durable outbox. PostgreSQL locks across processes.

    SQLite is an intentionally single-process local development adapter. Every
    entity and operation is persisted inside the versioned workspace aggregate.
    """
    def __init__(self, url: str):
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql+psycopg://", 1)
        elif url.startswith("postgresql://"):
            url = url.replace("postgresql://", "postgresql+psycopg://", 1)
        self.sqlite = url.startswith("sqlite")
        self.engine = create_engine(url, connect_args={"check_same_thread": False} if self.sqlite else {}, pool_pre_ping=True)
        Base.metadata.create_all(self.engine)
        self.sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.local_lock = threading.RLock()
        # The journal commits before external I/O, independently of the aggregate.
        # SQLite uses a sidecar file to avoid a read-to-write upgrade across commits.
        journal_url=url
        if self.sqlite and self.engine.url.database not in {None,":memory:"}:
            journal_url="sqlite:///"+str(Path(self.engine.url.database).with_suffix(".journal.db"))
        self.journal_engine=create_engine(journal_url,connect_args={"check_same_thread":False} if self.sqlite else {},pool_pre_ping=True)
        JournalBase.metadata.create_all(self.journal_engine)
        self.journal_sessions=sessionmaker(self.journal_engine,expire_on_commit=False)

    def read_operation(self,key):
        with self.journal_sessions() as db:
            row=db.get(PaymentOperation,key)
            return deepcopy(row.body) if row else None

    def save_operation(self,operation):
        with self.journal_sessions.begin() as db:
            row=db.scalar(select(PaymentOperation).where(PaymentOperation.id==operation["id"]).with_for_update())
            if row:
                row.body=deepcopy(operation)
            else:
                db.add(PaymentOperation(id=operation["id"],entity_id=operation["commitment_id"],kind=operation["kind"],body=deepcopy(operation)))

    def create(self, state: dict, ttl_hours=72, owner=None):
        workspace_id = "ws_" + secrets.token_hex(12)
        tokens = {}
        with self.sessions.begin() as db:
            db.add(Workspace(id=workspace_id, state=state, owner=owner, expires_at=now()+timedelta(hours=ttl_hours)))
            for actor in state["actors"]:
                token = secrets.token_urlsafe(32)
                tokens[actor["id"]] = token
                db.add(Membership(token_hash=hashlib.sha256(token.encode()).hexdigest(), workspace_id=workspace_id, actor_id=actor["id"]))
        return workspace_id, tokens

    def membership(self, token):
        with self.sessions() as db:
            row = db.get(Membership, hashlib.sha256(token.encode()).hexdigest())
            return (row.workspace_id, row.actor_id) if row else None

    @contextmanager
    def transaction(self, workspace_id, check_expiry=True):
        with self.local_lock, self.sessions.begin() as db:
            row = db.scalar(select(Workspace).where(Workspace.id==workspace_id).with_for_update())
            if row is None:
                raise KeyError("Workspace not found")
            expiry = row.expires_at.replace(tzinfo=now().tzinfo) if row.expires_at.tzinfo is None else row.expires_at
            if check_expiry and expiry <= now():
                raise PermissionError("This session expired. Start a new walkthrough.")
            state = deepcopy(row.state)
            yield state, db
            if state!=row.state:
                row.state = state
                row.revision += 1

    def read(self, workspace_id):
        with self.sessions() as db:
            row=db.get(Workspace,workspace_id)
            if not row:
                raise KeyError("Workspace not found")
            expiry=row.expires_at.replace(tzinfo=now().tzinfo) if row.expires_at.tzinfo is None else row.expires_at
            if expiry<=now():
                raise PermissionError("This session expired. Start a new walkthrough.")
            return deepcopy(row.state)

    def enqueue(self, db, workspace_id, kind, entity_id, available_at=None):
        # Stable outbox key prevents duplicate work when the same command repeats.
        job_id = f"{workspace_id}:{kind}:{entity_id}"
        job=db.scalar(select(Job).where(Job.id==job_id).with_for_update())
        if not job:
            db.add(Job(id=job_id, workspace_id=workspace_id, kind=kind, entity_id=entity_id, available_at=available_at or now()))
        else:
            job.generation+=1
            if job.status!="RUNNING":
                job.status="QUEUED"
                job.attempts=0
                job.available_at=now()
        return job_id

    def claim_job(self):
        with self.local_lock, self.sessions.begin() as db:
            job = db.scalar(select(Job).where(Job.status.in_(["QUEUED", "RUNNING"]), Job.available_at <= now()).order_by(Job.available_at).with_for_update(skip_locked=True).limit(1))
            if job is None:
                return None
            job.status="RUNNING"
            job.attempts += 1
            job.available_at = now()+timedelta(seconds=90)
            return {k:getattr(job,k) for k in ["id","workspace_id","kind","entity_id","attempts","generation"]}

    def finish_job(self, job_id, error=None, generation=None):
        with self.local_lock, self.sessions.begin() as db:
            job = db.scalar(select(Job).where(Job.id==job_id).with_for_update())
            if generation is not None and generation!=job.generation:
                job.status="QUEUED"
                job.available_at=now()
                return
            job.status = "QUEUED" if error and job.attempts < 8 else ("FAILED" if error else "DONE")
            job.error = error
            job.available_at = now()+timedelta(seconds=min(60,2**job.attempts))

    def due_workspaces(self):
        with self.sessions() as db:
            return list(db.scalars(select(Workspace.id)))
