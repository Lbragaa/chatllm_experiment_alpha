from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import ChatMessage, ChatSession, User
from backend.routers.auth import _get_current_user
from backend.schemas.session import ChatSessionCreate, ChatSessionList, ChatSessionOut


router = APIRouter()


@router.get("/api/sessions", response_model=ChatSessionList)
def list_sessions(
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionList:
    sessions = (
        db.query(ChatSession)
        .filter(ChatSession.user_id == current_user.id)
        .order_by(ChatSession.updated_at.desc())
        .all()
    )
    return ChatSessionList(
        sessions=[ChatSessionOut(id=s.id, title=s.title, created_at=s.created_at, updated_at=s.updated_at) for s in sessions]
    )


@router.post("/api/sessions", response_model=ChatSessionOut, status_code=201)
def create_session(
    payload: ChatSessionCreate,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> ChatSessionOut:
    session = ChatSession(user_id=current_user.id)
    db.add(session)
    db.commit()
    db.refresh(session)
    return ChatSessionOut(id=session.id, title=session.title, created_at=session.created_at, updated_at=session.updated_at)


@router.delete("/api/sessions/{session_id}")
def delete_session(
    session_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> dict[str, str]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    db.delete(session)
    db.commit()
    return {"message": "Sessao removida"}


@router.get("/api/sessions/{session_id}/messages")
def get_session_messages(
    session_id: int,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> list[dict]:
    session = db.query(ChatSession).filter(ChatSession.id == session_id, ChatSession.user_id == current_user.id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Sessao nao encontrada")

    messages = (
        db.query(ChatMessage)
        .filter(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.id)
        .all()
    )
    return [
        {"id": m.id, "role": m.role, "content": m.content, "model": m.model, "created_at": m.created_at.isoformat()}
        for m in messages
    ]