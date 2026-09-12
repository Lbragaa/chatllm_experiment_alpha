from __future__ import annotations

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

from backend.config import SQLALCHEMY_DATABASE_URL, SQLITE_PATH


engine = create_engine(
    SQLALCHEMY_DATABASE_URL,
    connect_args={"check_same_thread": False},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session_factory(request: Request):
    return request.app.state.session_factory


def get_db(request: Request):
    with get_session_factory(request)() as db:
        yield db
