from __future__ import with_statement
import os
from logging.config import fileConfig
import sys
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

# Tambahkan path project
project_root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(project_root))

from sqlalchemy import engine_from_config, pool
from alembic import context

# Import Base SQLAlchemy yang BENAR (bukan Pydantic BaseModel)
from database import Base   # <--- perbaikan utama

# Ambil config Alembic
config = context.config

# Logging
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Ambil DB URL dari environment
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL environment variable is missing.")

# Set URL ke Alembic
config.set_main_option("sqlalchemy.url", database_url.replace("+asyncpg", ""))

# Metadata untuk auto-generate migration
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            compare_server_default=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
