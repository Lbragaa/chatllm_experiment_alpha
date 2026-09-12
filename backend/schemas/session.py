from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ChatSessionCreate(BaseModel):
    pass


class ChatSessionOut(BaseModel):
    id: int
    title: str | None
    created_at: datetime
    updated_at: datetime


class ChatSessionList(BaseModel):
    sessions: list[ChatSessionOut]


class ChatSessionUpdate(BaseModel):
    title: str | None = None