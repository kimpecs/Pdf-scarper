"""
Alembic env.py — wired to Larry's ORM models and config.

DATABASE_URL resolution order:
  1. POSTGRES_DSN env var (production PostgreSQL)
  2. Fallback to SQLite at app/data/catalog.db (local dev)
"""

import os
import sys
from logging.config import fileConfig
from pathlib import Path

from sqlalchemy import engine_from_config, pool

from alembic import context

# ── Make sure the project root is on sys.path ────────────────────────────
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# ── Import our models so Alembic can autogenerate diffs ─────────────────
from app.services.db.orm_models import Base           # noqa: E402
from app.utils.config import settings                 # noqa: E402

# ── Alembic Config ───────────────────────────────────────────────────────
alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

# ── Resolve DB URL ───────────────────────────────────────────────────────
def get_url() -> str:
    return settings.active_database_url


# ── Offline mode ─────────────────────────────────────────────────────────
def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Online mode ──────────────────────────────────────────────────────────
def run_migrations_online() -> None:
    cfg = alembic_config.get_section(alembic_config.config_ini_section, {})
    cfg["sqlalchemy.url"] = get_url()

    connectable = engine_from_config(
        cfg,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_type=True,
        )
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
