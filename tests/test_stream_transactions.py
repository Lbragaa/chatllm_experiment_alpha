import json

import pytest
from sqlalchemy import event
from sqlalchemy.exc import SQLAlchemyError

from backend.models import ChatMessage, ChatSession


def events(response):
    return [json.loads(line[6:]) for line in response.text.splitlines() if line.startswith("data: ")]


@pytest.fixture
def credentials(client):
    reg = client.post("/api/auth/register", json={"email": "stream@example.com", "password": "123456"})
    return {"Authorization": f"Bearer {reg.json()['token']}"}


def test_stream_persists_after_app_restart(client, credentials, engine, monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine
    from backend.main import create_app

    async def reply(**kwargs):
        yield "Resposta "
        yield "completa"
    monkeypatch.setattr("backend.routers.chat.stream_reply", reply)
    response = client.post("/api/chat/stream", headers=credentials, json={"message": "Titulo persistido"})
    last = events(response)[-1]
    assert last["done"] is True
    reopened = create_engine(engine.url, connect_args={"check_same_thread": False})
    try:
        with TestClient(create_app(reopened)) as restarted:
            sessions = restarted.get("/api/sessions", headers=credentials).json()["sessions"]
            assert sessions[0]["title"] == "Titulo persistido"
            history = restarted.get(f"/api/sessions/{last['session_id']}/messages", headers=credentials).json()
            assert [m["content"] for m in history] == ["Titulo persistido", "Resposta completa"]
    finally:
        reopened.dispose()


def test_commit_failure_rolls_back_title_and_messages(client, credentials, monkeypatch, fresh_db):
    session_id = client.post("/api/sessions", headers=credentials, json={}).json()["id"]

    async def reply(**kwargs):
        yield "Resposta"
    monkeypatch.setattr("backend.routers.chat.stream_reply", reply)
    session_class = client.app.state.session_factory.class_

    def fail_before_commit(db):
        if any(isinstance(obj, ChatMessage) for obj in db.new):
            raise SQLAlchemyError("simulated commit failure")
    event.listen(session_class, "before_commit", fail_before_commit)
    try:
        response = client.post("/api/chat/stream", headers=credentials, json={"message": "Teste", "session_id": session_id})
    finally:
        event.remove(session_class, "before_commit", fail_before_commit)
    assert any("error" in item for item in events(response))
    assert not any(item.get("done") for item in events(response))
    with fresh_db() as db:
        assert db.get(ChatSession, session_id).title is None
        assert db.query(ChatMessage).filter_by(session_id=session_id).count() == 0


def test_stream_refuses_other_users_session(client, credentials, monkeypatch):
    session_id = client.post("/api/sessions", headers=credentials, json={}).json()["id"]
    other = client.post("/api/auth/register", json={"email": "other@example.com", "password": "123456"}).json()["token"]
    response = client.post("/api/chat/stream", headers={"Authorization": f"Bearer {other}"}, json={"message": "Intrusao", "session_id": session_id})
    assert response.status_code == 404
