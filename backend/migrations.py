"""Idempotent SQLite upgrade preserving legacy messages without guessing owners."""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path
from uuid import uuid4

from sqlalchemy import inspect
from backend.database import Base


def initialize_database(engine):
    from backend import models  # noqa: F401 -- registers all tables

    database = engine.url.database
    if database and database != ":memory:":
        Path(database).parent.mkdir(parents=True, exist_ok=True)
    backup = None
    with engine.connect() as connection:
        connection.exec_driver_sql("BEGIN IMMEDIATE")
        try:
            inspector = inspect(connection)
            names = inspector.get_table_names()
            if "chat_messages" in names:
                columns = {c["name"] for c in inspector.get_columns("chat_messages")}
                if "session_key" in columns and "session_id" not in columns:
                    if "chat_messages_legacy" in names:
                        raise RuntimeError("Arquivo legado ja existe; migracao requer revisao manual.")
                    if database and database != ":memory:":
                        backup = Path(str(database) + f".backup-{uuid4().hex}.sqlite")
                        with sqlite3.connect(str(database)) as source:
                            with sqlite3.connect(str(backup)) as target:
                                source.backup(target)
                    indexes = inspector.get_indexes("chat_messages")
                    connection.exec_driver_sql(
                        "ALTER TABLE chat_messages RENAME TO chat_messages_legacy"
                    )
                    # Names of secondary indexes are global in SQLite. Preserve
                    # every row/column but release the old index names for the new table.
                    for index in indexes:
                        name = connection.dialect.identifier_preparer.quote(index["name"])
                        connection.exec_driver_sql(f"DROP INDEX {name}")
            Base.metadata.create_all(connection)
            connection.commit()
        except BaseException:
            connection.rollback()
            raise
    if backup:
        logging.getLogger(__name__).warning(
            "Historico antigo preservado em chat_messages_legacy; backup: %s", backup
        )
    return backup
