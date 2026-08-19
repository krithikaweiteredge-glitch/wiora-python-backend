"""Alembic environment — wired to Wiora's engine, models and the `wiora` schema.

Going forward, schema changes are made with:
    alembic revision --autogenerate -m "describe change"
    alembic upgrade head
(create_all in app/db.py stays as a dev-convenience baseline for fresh DBs.)"""
from logging.config import fileConfig

from alembic import context
from sqlalchemy import text

# App wiring: reuse the same engine, metadata and schema as the running app.
from app.config import get_settings
from app.db import Base, engine
from app import models  # noqa: F401 — register all models on Base.metadata

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata
SCHEMA = "wiora"


def _configure(connection=None, **kw):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        version_table_schema=SCHEMA,
        include_schemas=True,
        compare_type=True,
        **kw,
    )


def run_migrations_offline() -> None:
    _configure(url=get_settings().sqlalchemy_url, literal_binds=True,
               dialect_opts={"paramstyle": "named"})
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    with engine.connect() as connection:
        connection.execute(text(f"CREATE SCHEMA IF NOT EXISTS {SCHEMA}"))
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        _configure(connection=connection)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
