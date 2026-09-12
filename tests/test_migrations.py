import sqlite3

import pytest
from sqlalchemy import create_engine, inspect, text

from backend.migrations import initialize_database


def test_legacy_upgrade_preserves_accounts_and_archives_messages(tmp_path):
    path = tmp_path / "legacy.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT NOT NULL,
                password_hash TEXT NOT NULL, created_at DATETIME);
            INSERT INTO users VALUES (7, 'kept@example.com', 'existing-hash', '2026-01-01');
            CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_key TEXT NOT NULL,
                role TEXT, content TEXT, model TEXT, created_at DATETIME);
            CREATE INDEX ix_chat_messages_role ON chat_messages(role);
            INSERT INTO chat_messages VALUES (12, 'default', 'user', 'Preserve me', 'model', '2026-01-01');
            CREATE TABLE sessions (id INTEGER PRIMARY KEY, token TEXT);
            INSERT INTO sessions VALUES (1, 'old-session');
        """)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        backup = initialize_database(engine)
        assert backup is not None and backup.exists()
        with sqlite3.connect(backup) as db:
            assert db.execute("SELECT content FROM chat_messages").fetchone() == ("Preserve me",)
        with engine.connect() as db:
            assert db.execute(text("SELECT email, password_hash FROM users")).one() == ("kept@example.com", "existing-hash")
            assert db.execute(text("SELECT content FROM chat_messages_legacy")).scalar() == "Preserve me"
            assert db.execute(text("SELECT COUNT(*) FROM chat_messages")).scalar() == 0
            assert db.execute(text("SELECT COUNT(*) FROM chat_sessions")).scalar() == 0
            assert db.execute(text("SELECT token FROM sessions")).scalar() == "old-session"
            assert "session_id" in {c["name"] for c in inspect(db).get_columns("chat_messages")}
        assert initialize_database(engine) is None  # idempotent; no second archive/reset
        assert len(list(tmp_path.glob("*.backup-*.sqlite"))) == 1
    finally:
        engine.dispose()


def test_ambiguous_legacy_archive_fails_without_deleting_data(tmp_path):
    path = tmp_path / "ambiguous.db"
    with sqlite3.connect(path) as db:
        db.executescript("""
            CREATE TABLE chat_messages (id INTEGER PRIMARY KEY, session_key TEXT);
            INSERT INTO chat_messages VALUES (1, 'keep');
            CREATE TABLE chat_messages_legacy (id INTEGER PRIMARY KEY);
        """)
    engine = create_engine(f"sqlite:///{path.as_posix()}")
    try:
        with pytest.raises(RuntimeError, match="revisao manual"):
            initialize_database(engine)
        with sqlite3.connect(path) as db:
            assert db.execute("SELECT session_key FROM chat_messages").fetchone() == ("keep",)
    finally:
        engine.dispose()


def test_import_and_app_construction_do_not_connect_to_default_database(monkeypatch):
    import importlib
    import backend.main as main

    def forbidden(*args, **kwargs):
        raise AssertionError("Import must not open the real database")
    monkeypatch.setattr(main.engine, "connect", forbidden)
    importlib.reload(main)
    main.create_app()
