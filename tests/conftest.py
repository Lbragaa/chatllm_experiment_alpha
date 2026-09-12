from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import NullPool

from backend.main import create_app
from backend.migrations import initialize_database


@pytest.fixture
def engine(tmp_path):
    test_engine = create_engine(
        f"sqlite:///{(tmp_path / 'test.db').as_posix()}",
        connect_args={"check_same_thread": False}, poolclass=NullPool,
    )
    initialize_database(test_engine)
    yield test_engine
    test_engine.dispose()


@pytest.fixture
def db_session(engine):
    with sessionmaker(bind=engine)() as session:
        yield session


@pytest.fixture
def client(engine):
    # Production dependencies/lifecycle, isolated database. No shared transactions.
    with TestClient(create_app(engine)) as test_client:
        yield test_client


@pytest.fixture
def fresh_db(engine):
    # Reopen the file with a different engine and independent physical connections.
    independent_engine = create_engine(engine.url, poolclass=NullPool)
    yield sessionmaker(bind=independent_engine)
    independent_engine.dispose()
