from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


# Mock OpenRouter to avoid network calls
@pytest.fixture(autouse=True)
def mock_openrouter(monkeypatch):
    async def mock_generate_reply(*, user_message, history, model):
        return (f"Resposta para: {user_message}", model or "google/gemma-4-31b-it")

    async def mock_stream_reply(*, user_message, history, model):
        yield f"Resposta para: {user_message}"

    monkeypatch.setattr("backend.routers.chat.generate_reply", mock_generate_reply)
    monkeypatch.setattr("backend.routers.chat.stream_reply", mock_stream_reply)


@pytest.fixture
def auth_token(client: TestClient) -> str:
    response = client.post(
        "/api/auth/register",
        json={"email": "sessions@email.com", "password": "123456"},
    )
    assert response.status_code == 200
    return response.json()["token"]


@pytest.fixture
def auth_token_b(client: TestClient) -> str:
    """Second user for isolation tests."""
    response = client.post(
        "/api/auth/register",
        json={"email": "sessions_b@email.com", "password": "123456"},
    )
    assert response.status_code == 200
    return response.json()["token"]


class TestSessionCRUD:
    def test_create_session(self, client: TestClient, auth_token: str):
        """Criar sessao retorna 201 com id."""
        response = client.post(
            "/api/sessions",
            json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 201
        data = response.json()
        assert data["id"] is not None
        assert data["title"] is None

    def test_list_sessions(self, client: TestClient, auth_token: str):
        """Listar sessoes retorna lista ordenada por updated_at desc."""
        # Criar 2 sessoes
        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {auth_token}"})
        client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {auth_token}"})

        response = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "sessions" in data
        assert len(data["sessions"]) >= 2

    def test_delete_session(self, client: TestClient, auth_token: str):
        """Deletar sessao retorna 200 e remove do banco."""
        created = client.post(
            "/api/sessions", json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = created.json()["id"]

        delete_resp = client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert delete_resp.status_code == 200

        # Verificar que foi removida
        list_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        ids = [s["id"] for s in list_resp.json()["sessions"]]
        assert session_id not in ids

    def test_delete_nonexistent_session(self, client: TestClient, auth_token: str):
        """Deletar sessao inexistente retorna 404."""
        response = client.delete(
            "/api/sessions/99999",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404

    def test_sessions_require_auth(self, client: TestClient):
        """Listar sessoes sem token retorna 401."""
        response = client.get("/api/sessions")
        assert response.status_code == 401

        response = client.post("/api/sessions", json={})
        assert response.status_code == 401

        response = client.delete("/api/sessions/1")
        assert response.status_code == 401


class TestSessionMessages:
    def test_get_session_messages_empty(self, client: TestClient, auth_token: str):
        """Sessao nova tem lista vazia de mensagens."""
        created = client.post(
            "/api/sessions", json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = created.json()["id"]

        response = client.get(
            f"/api/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        assert response.json() == []

    def test_get_session_messages_after_chat(self, client: TestClient, auth_token: str):
        """Apos enviar mensagem, o historico da sessao contem as mensagens."""
        # Enviar mensagem (cria sessao automaticamente)
        chat_resp = client.post(
            "/api/chat",
            json={"message": "Ola"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = chat_resp.json()["session_id"]

        # Buscar mensagens da sessao
        response = client.get(
            f"/api/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        msgs = response.json()
        assert len(msgs) == 2  # user + assistant
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"

    def test_get_messages_nonexistent_session(self, client: TestClient, auth_token: str):
        """Buscar mensagens de sessao inexistente retorna 404."""
        response = client.get(
            "/api/sessions/99999/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404


class TestSessionIsolation:
    def test_user_a_cannot_access_user_b_sessions(self, client: TestClient, auth_token: str, auth_token_b: str):
        """Usuario A nao ve sessoes do usuario B."""
        # Usuario A cria sessao
        a_session = client.post(
            "/api/sessions", json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()

        # Usuario B lista sessoes — nao deve ver a sessao de A
        b_list = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token_b}"},
        ).json()
        b_ids = [s["id"] for s in b_list["sessions"]]
        assert a_session["id"] not in b_ids

    def test_user_b_cannot_read_user_a_messages(self, client: TestClient, auth_token: str, auth_token_b: str):
        """Usuario B nao pode ler mensagens da sessao do usuario A."""
        # Usuario A cria sessao via chat
        a_chat = client.post(
            "/api/chat",
            json={"message": "Segredo"},
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()
        a_session_id = a_chat["session_id"]

        # Usuario B tenta acessar
        response = client.get(
            f"/api/sessions/{a_session_id}/messages",
            headers={"Authorization": f"Bearer {auth_token_b}"},
        )
        assert response.status_code == 404

    def test_user_b_cannot_delete_user_a_session(self, client: TestClient, auth_token: str, auth_token_b: str):
        """Usuario B nao pode deletar sessao do usuario A."""
        a_session = client.post(
            "/api/sessions", json={},
            headers={"Authorization": f"Bearer {auth_token}"},
        ).json()

        response = client.delete(
            f"/api/sessions/{a_session['id']}",
            headers={"Authorization": f"Bearer {auth_token_b}"},
        )
        assert response.status_code == 404


class TestAutoTitle:
    def test_title_set_after_first_message(self, client: TestClient, auth_token: str):
        """Titulo definido apos primeira mensagem no chat."""
        chat_resp = client.post(
            "/api/chat",
            json={"message": "Qual a capital do Brasil?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = chat_resp.json()["session_id"]

        sessions_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        matching = [s for s in sessions if s["id"] == session_id]
        assert len(matching) == 1
        assert matching[0]["title"] is not None
        assert "Qual a capital do Brasil?" in matching[0]["title"]

    def test_title_set_after_stream(self, client: TestClient, auth_token: str):
        """Titulo definido apos primeira mensagem via streaming."""
        response = client.post(
            "/api/chat/stream",
            json={"message": "O que e Python?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        # Extract session_id from stream body
        body = response.text
        assert "session_id" in body
        import re
        match = re.search(r'"session_id":\s*(\d+)', body)
        assert match, "session_id not found in stream response"
        session_id = int(match.group(1))

        # Verify title was set
        sessions_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        matching = [s for s in sessions if s["id"] == session_id]
        assert len(matching) == 1
        assert matching[0]["title"] is not None
        assert "O que e Python?" in matching[0]["title"]

    def test_title_truncated_if_long(self, client: TestClient, auth_token: str):
        """Titulo truncado em ~60 chars para mensagens longas."""
        long_msg = "Eu gostaria de saber qual e a melhor forma de aprender uma nova lingua estrangeira de maneira eficiente e rapida"
        chat_resp = client.post(
            "/api/chat",
            json={"message": long_msg},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = chat_resp.json()["session_id"]

        sessions_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        matching = [s for s in sessions if s["id"] == session_id]
        assert len(matching) == 1
        title = matching[0]["title"]
        assert title is not None
        assert len(title) <= 63  # 60 + "..."

    def test_title_not_overwritten_on_second_message(self, client: TestClient, auth_token: str):
        """Titulo nao muda ao enviar segunda mensagem na mesma sessao."""
        r1 = client.post(
            "/api/chat",
            json={"message": "Primeira mensagem"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = r1.json()["session_id"]

        # Segunda mensagem
        client.post(
            "/api/chat",
            json={"message": "Segunda mensagem", "session_id": session_id},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        sessions_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        matching = [s for s in sessions if s["id"] == session_id]
        assert matching[0]["title"] == "Primeira mensagem"


class TestDeleteCascade:
    def test_delete_session_removes_messages(self, client: TestClient, auth_token: str, fresh_db):
        """Deletar sessao tambem remove as mensagens associadas."""
        chat_resp = client.post(
            "/api/chat",
            json={"message": "Mensagem para deletar"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = chat_resp.json()["session_id"]

        # Deletar sessao
        client.delete(
            f"/api/sessions/{session_id}",
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        # Sessao removida — GET messages retorna 404
        response = client.get(
            f"/api/sessions/{session_id}/messages",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404

        # Sessao nao aparece na listagem
        list_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        ids = [s["id"] for s in list_resp.json()["sessions"]]
        assert session_id not in ids

        from backend.models import ChatMessage
        with fresh_db() as independent:
            assert independent.query(ChatMessage).filter(ChatMessage.session_id == session_id).count() == 0


class TestPersistence:
    """Tests that verify data survives across DB sessions using a temp file."""

    def test_title_and_messages_persist_after_stream(self, client: TestClient, auth_token: str, fresh_db):
        """After consuming a stream response, title and messages are committed to DB."""
        import re

        response = client.post(
            "/api/chat/stream",
            json={"message": "O que e Python?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        body = response.text
        match = re.search(r'"session_id":\s*(\d+)', body)
        assert match, "session_id not found in stream response"
        session_id = int(match.group(1))

        # Verify using a fresh DB session (new connection)
        db = fresh_db()
        try:
            from backend.models import ChatSession, ChatMessage

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            assert session is not None, "Session should exist in DB"
            assert session.title is not None, "Title should be set"
            assert "O que e Python?" in session.title

            msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
            assert len(msgs) == 2, "Should have 2 messages (user + assistant)"
            assert msgs[0].role == "user"
            assert msgs[1].role == "assistant"
        finally:
            db.close()

    def test_title_and_messages_persist_after_non_stream(self, client: TestClient, auth_token: str, fresh_db):
        """After a non-stream chat, title and messages are committed."""
        chat_resp = client.post(
            "/api/chat",
            json={"message": "Qual a capital do Brasil?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = chat_resp.json()["session_id"]

        db = fresh_db()
        try:
            from backend.models import ChatSession, ChatMessage

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            assert session is not None
            assert session.title is not None
            assert "Qual a capital do Brasil?" in session.title

            msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
            assert len(msgs) == 2
        finally:
            db.close()

    def test_second_message_does_not_overwrite_title(self, client: TestClient, auth_token: str, fresh_db):
        """Second message in same session keeps original title."""
        r1 = client.post(
            "/api/chat",
            json={"message": "Primeira"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = r1.json()["session_id"]

        client.post(
            "/api/chat",
            json={"message": "Segunda", "session_id": session_id},
            headers={"Authorization": f"Bearer {auth_token}"},
        )

        db = fresh_db()
        try:
            from backend.models import ChatSession, ChatMessage

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            assert session.title == "Primeira"

            msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
            assert len(msgs) == 4  # 2 user + 2 assistant
        finally:
            db.close()

    def test_stream_with_existing_session(self, client: TestClient, auth_token: str, fresh_db):
        """Stream with an existing session_id works and persists."""
        import re

        # Create session first
        created = client.post("/api/sessions", json={}, headers={"Authorization": f"Bearer {auth_token}"})
        session_id = created.json()["id"]

        # Send stream message to existing session
        response = client.post(
            "/api/chat/stream",
            json={"message": "Mensagem em sessao existente", "session_id": session_id},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200

        db = fresh_db()
        try:
            from backend.models import ChatSession, ChatMessage

            session = db.query(ChatSession).filter(ChatSession.id == session_id).first()
            assert session is not None
            assert session.title is not None
            assert "Mensagem em sessao existente" in session.title

            msgs = db.query(ChatMessage).filter(ChatMessage.session_id == session_id).order_by(ChatMessage.id).all()
            assert len(msgs) == 2
        finally:
            db.close()
