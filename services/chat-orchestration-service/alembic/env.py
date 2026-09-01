import pathlib
import sys
from logging.config import fileConfig

from alembic import context
from sqlalchemy import engine_from_config, pool

# So `import app` resolves when alembic is invoked from the service root
# (mirrors auth-user-service, card O2.1).
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

from app import models  # noqa: E402,F401  (registers models on Base.metadata)
from app.config import get_settings  # noqa: E402
from app.database import Base  # noqa: E402

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# DATABASE_URL (env var, see app/config.py) is the single source of truth for the
# connection string — nothing DB-specific is hardcoded in alembic.ini.
_database_url = get_settings().database_url
config.set_main_option("sqlalchemy.url", _database_url)

target_metadata = Base.metadata

# This service defaults to SQLite for local dev (app/config.py). SQLite cannot
# ALTER a column in place, so batch mode is required there or any future
# alter/drop migration fails on a developer machine while passing on Postgres.
_render_as_batch = _database_url.startswith("sqlite")


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        render_as_batch=_render_as_batch,
        version_table="alembic_version_chat",
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            render_as_batch=_render_as_batch,
            version_table="alembic_version_chat",
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
