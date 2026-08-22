"""ORM models (V1 subset of the blueprint's schema). Cloud-first: conversations,
messages and memories are the PRIMARY records here in PostgreSQL."""
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Embedding dimension for semantic memory. Matches a small local model
# (e.g. fastembed BAAI/bge-small-en = 384). Change if you switch providers.
EMBED_DIM = 384


def _now() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"
    id: Mapped[str] = mapped_column(String(128), primary_key=True)  # Firebase UID
    email: Mapped[str | None] = mapped_column(String(320), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Conversation(Base):
    __tablename__ = "conversations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    messages: Mapped[list["Message"]] = relationship(
        back_populates="conversation", cascade="all, delete-orphan"
    )


class Message(Base):
    __tablename__ = "messages"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    conversation_id: Mapped[int] = mapped_column(
        ForeignKey("conversations.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    role: Mapped[str] = mapped_column(String(16))  # user | assistant | system
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    conversation: Mapped["Conversation"] = relationship(back_populates="messages")


class Memory(Base):
    __tablename__ = "memories"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    type: Mapped[str] = mapped_column(String(32))  # preference | fact | ...
    category: Mapped[str | None] = mapped_column(String(64), nullable=True)
    value: Mapped[str] = mapped_column(Text)
    # Semantic memory — nullable until an embeddings provider is enabled.
    embedding: Mapped[list[float] | None] = mapped_column(Vector(EMBED_DIM), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AuditLog(Base):
    """Approval & Audit Engine: record what the AI did (blueprint requirement)."""
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    action: Mapped[str] = mapped_column(String(64))  # chat | tool_call | memory_write ...
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Personality(Base):
    """User's assistant personality (one row per user), stored as JSON."""
    __tablename__ = "personalities"
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    data: Mapped[str] = mapped_column(Text)  # JSON
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Preference(Base):
    """Small per-user key/value settings (e.g. voice mode)."""
    __tablename__ = "preferences"
    user_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text)


class Reminder(Base):
    __tablename__ = "reminders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Recurrence: none | daily | weekly | monthly.
    repeat: Mapped[str] = mapped_column(String(16), default="none")
    done: Mapped[bool] = mapped_column(default=False)
    # Whether the SERVER should deliver this reminder via push. True only for
    # reminders CREATED server-side (e.g. by an automation) that the device never
    # scheduled locally. Reminders created from the app fire as local device
    # notifications, so they stay False to avoid a duplicate push. Cleared to False
    # once pushed, so delivery is exactly-once without depending on Redis.
    push_notify: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Meeting(Base):
    __tablename__ = "meetings"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    title: Mapped[str | None] = mapped_column(String(200), nullable=True)
    transcript: Mapped[str | None] = mapped_column(Text, nullable=True)
    insights: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class DocumentChunk(Base):
    """A ~paragraph-sized chunk of a document with its embedding (pgvector), for
    semantic retrieval (blueprint §13 RAG pipeline)."""
    __tablename__ = "document_chunks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    document_id: Mapped[int] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), index=True
    )
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float] | None] = mapped_column(Vector(384), nullable=True)


class Automation(Base):
    """A trigger→action rule (blueprint V4). V1 supports time triggers
    (daily/weekly at HH:MM) with actions: briefing | reminder | agent."""
    __tablename__ = "automations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    name: Mapped[str] = mapped_column(String(200))
    trigger_type: Mapped[str] = mapped_column(String(16))  # daily | weekly
    hour: Mapped[int] = mapped_column(Integer, default=8)
    minute: Mapped[int] = mapped_column(Integer, default=0)
    weekday: Mapped[int | None] = mapped_column(Integer, nullable=True)  # 0=Mon..6=Sun (weekly)
    action_type: Mapped[str] = mapped_column(String(24))  # briefing | reminder | agent
    action_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    enabled: Mapped[bool] = mapped_column(default=True)
    last_run_date: Mapped[str | None] = mapped_column(String(10), nullable=True)  # YYYY-MM-DD
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class SavedLocation(Base):
    """A named place the user saves (Home, Office, Gym) for geofence reminders.
    Coordinates + a radius; the phone registers the actual geofence locally."""
    __tablename__ = "saved_locations"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    label: Mapped[str] = mapped_column(String(120))
    latitude: Mapped[float] = mapped_column(Float)
    longitude: Mapped[float] = mapped_column(Float)
    radius_m: Mapped[int] = mapped_column(Integer, default=150)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Task(Base):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    text: Mapped[str] = mapped_column(Text)
    done: Mapped[bool] = mapped_column(default=False)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    # Recurrence: none | daily | weekly | monthly.
    repeat: Mapped[str] = mapped_column(String(16), default="none")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class Document(Base):
    """Uploaded file/photo (blueprint §13). We store extracted TEXT + a summary in
    Postgres; large binaries would go to S3 later."""
    __tablename__ = "documents"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    filename: Mapped[str] = mapped_column(String(300))
    mimetype: Mapped[str] = mapped_column(String(128))
    text: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)


class AgentRun(Base):
    """Agent Run Manager (blueprint §6): one multi-step agent execution."""
    __tablename__ = "agent_runs"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(128), index=True)
    goal: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(24))  # planning|running|done|failed|awaiting_approval
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    steps: Mapped[list["AgentStep"]] = relationship(
        back_populates="run", cascade="all, delete-orphan", order_by="AgentStep.idx"
    )


class AgentStep(Base):
    __tablename__ = "agent_steps"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[int] = mapped_column(ForeignKey("agent_runs.id", ondelete="CASCADE"), index=True)
    idx: Mapped[int] = mapped_column(Integer)
    description: Mapped[str] = mapped_column(Text)
    tool_name: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(24))  # done|failed|awaiting_approval|skipped
    result: Mapped[str | None] = mapped_column(Text, nullable=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    run: Mapped["AgentRun"] = relationship(back_populates="steps")
