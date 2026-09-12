from __future__ import annotations

import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import SQLAlchemyError
import httpx

from backend.config import OPENROUTER_MODEL_DEFAULT
from backend.database import get_db, get_session_factory
from backend.models import ChatMessage, ChatSession, User
from backend.routers.auth import _get_current_user
from backend.schemas.chat import ChatRequest, ChatResponse
from backend.services.openrouter import OpenRouterConfigError, generate_reply, stream_reply


router = APIRouter()

MAX_TITLE_LENGTH = 60


def _auto_title(content: str) -> str:
    """Generate a short title from the first user message."""
    cleaned = content.strip().replace("\n", " ").replace("\r", " ")
    if len(cleaned) <= MAX_TITLE_LENGTH:
        return cleaned
    return cleaned[:MAX_TITLE_LENGTH].rsplit(" ", 1)[0] + "..."


@router.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}


def _resolve_session(payload, current_user, db):
    """Get or create a chat session for the given payload."""
    if payload.session_id:
        session = db.query(ChatSession).filter(
            ChatSession.id == payload.session_id,
            ChatSession.user_id == current_user.id,
        ).first()
        if not session:
            raise HTTPException(status_code=404, detail="Sessao nao encontrada")
    else:
        session = ChatSession(user_id=current_user.id)
        db.add(session)
        db.flush()
    return session


@router.post("/api/chat", response_model=ChatResponse)
async def chat(
    payload: ChatRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
) -> ChatResponse:
    session = _resolve_session(payload, current_user, db)

    try:
        reply, model_name = await generate_reply(
            user_message=payload.message,
            history=[item.model_dump() for item in payload.history],
            model=payload.model,
        )
    except OpenRouterConfigError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    resolved_model = payload.model or model_name or OPENROUTER_MODEL_DEFAULT

    # Auto-title on first message
    if session.title is None:
        session.title = _auto_title(payload.message)

    session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)

    db.add(ChatMessage(session_id=session.id, role="user", content=payload.message, model=resolved_model))
    db.add(ChatMessage(session_id=session.id, role="assistant", content=reply, model=resolved_model))
    db.commit()

    return ChatResponse(reply=reply, model=resolved_model, session_id=session.id)


@router.post("/api/chat/stream")
async def chat_stream(
    payload: ChatRequest,
    current_user: User = Depends(_get_current_user),
    db: Session = Depends(get_db),
    session_factory=Depends(get_session_factory),
) -> StreamingResponse:
    resolved_model = payload.model or OPENROUTER_MODEL_DEFAULT
    session = _resolve_session(payload, current_user, db)
    session_id = session.id
    user_id = current_user.id
    # A newly created conversation must exist before the request dependency closes.
    db.commit()

    async def event_generator():
        full_reply = ""
        try:
            async for delta in stream_reply(
                user_message=payload.message,
                history=[item.model_dump() for item in payload.history],
                model=payload.model,
            ):
                full_reply += delta
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=True)}\n\n"
        except OpenRouterConfigError as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return
        except (RuntimeError, httpx.RequestError) as exc:
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=True)}\n\n"
            return

        if not full_reply.strip():
            yield 'data: {"error": "O modelo retornou uma resposta vazia."}\n\n'
            return
        try:
            # Independent, short transaction: no database connection held during inference.
            with session_factory.begin() as write_db:
                chat_session = write_db.query(ChatSession).filter(
                    ChatSession.id == session_id, ChatSession.user_id == user_id,
                ).first()
                if chat_session is None:
                    yield 'data: {"error": "Conversa removida durante a resposta."}\n\n'
                    return
                if chat_session.title is None:
                    chat_session.title = _auto_title(payload.message)
                chat_session.updated_at = datetime.now(timezone.utc).replace(tzinfo=None)
                write_db.add_all([
                    ChatMessage(session_id=session_id, role="user", content=payload.message, model=resolved_model),
                    ChatMessage(session_id=session_id, role="assistant", content=full_reply, model=resolved_model),
                ])
        except SQLAlchemyError:
            logging.getLogger(__name__).exception("Falha ao persistir resposta do chat")
            yield 'data: {"error": "Nao foi possivel salvar a resposta."}\n\n'
            return

        yield f"data: {json.dumps({'done': True, 'session_id': session_id}, ensure_ascii=True)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "Connection": "keep-alive"},
    )
