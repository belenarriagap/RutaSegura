"""Entorno de Alembic.

En la aplicación, ``rutasegura.data.database.upgrade_to_head`` pasa una conexión abierta en
``config.attributes["connection"]``. Desde la línea de comandos (desarrollo) se usa la URL
de ``alembic.ini``.
"""

from __future__ import annotations

from alembic import context
from sqlalchemy import Connection, create_engine

from rutasegura.data.models import Base

config = context.config
target_metadata = Base.metadata


def _configure_and_run(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True,  # SQLite necesita recrear tablas para la mayoría de ALTER
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_offline() -> None:
    """Genera SQL sin conectarse."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        render_as_batch=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Aplica las migraciones sobre una conexión."""
    connection = config.attributes.get("connection")
    if connection is not None:
        _configure_and_run(connection)
        return
    url = config.get_main_option("sqlalchemy.url")
    if url is None:
        raise RuntimeError("Falta sqlalchemy.url en alembic.ini")
    engine = create_engine(url)
    with engine.begin() as conn:
        _configure_and_run(conn)
    engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
