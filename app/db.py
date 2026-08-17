"""Database engine + session (SQLAlchemy 2.0). PostgreSQL is the PRIMARY store
(cloud-first per the blueprint), with pgvector for semantic memory."""
from collections.abc import Iterator
from sqlalchemy import MetaData, create_engine, event, text
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# Isolate this backend's tables in a dedicated "wiora" schema so they never
# collide with legacy tables in the same database. pool_pre_ping keeps Neon's
# autosuspended connections healthy.
engine = create_engine(settings.sqlalchemy_url, pool_pre_ping=True, future=True)


# Neon's pooler rejects search_path as a startup parameter, so set it per
# connection with a normal SET statement instead.
@event.listens_for(engine, "connect")
def _set_search_path(dbapi_conn, _record) -> None:
    with dbapi_conn.cursor() as cur:
        cur.execute("SET search_path TO wiora, public")


SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    # All tables live explicitly in the "wiora" schema — never the legacy public
    # tables — so create_all and every query target the right ones.
    metadata = MetaData(schema="wiora")


def init_db() -> None:
    """Enable pgvector and create tables. Safe to run on every startup."""
    from . import models  # noqa: F401 — register models on Base

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS wiora"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(engine)


def get_db() -> Iterator[Session]:
    """FastAPI dependency: a request-scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
