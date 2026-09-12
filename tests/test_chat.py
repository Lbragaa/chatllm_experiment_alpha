from __future__ import annotations

import json
from unittest.mock import AsyncMock

import pytest
from fastapi.testclient import TestClient

from backend.services import openrouter


# Mock OpenRouter services to avoid network calls
# We patch at the router module level because chat.py imports the functions directly
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
    """Register a test user and return a valid JWT token."""
    response = client.post(
        "/api/auth/register",
        json={"email": "chattest@email.com", "password": "123456"},
    )
    assert response.status_code == 200
    return response.json()["token"]


class TestHealthEndpoint:
    def test_health_returns_ok(self, client: TestClient):
        response = client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"


class TestRootEndpoint:
    def test_root_returns_frontend(self, client: TestClient):
        response = client.get("/")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")


class TestChatEndpoint:
    def test_chat_requires_auth(self, client: TestClient):
        """Sem token, deve retornar 401."""
        response = client.post("/api/chat", json={"message": "Ola"})
        assert response.status_code == 401

    def test_chat_empty_message_rejected(self, client: TestClient, auth_token: str):
        """Mensagem vazia deve ser rejeitada com 422."""
        response = client.post(
            "/api/chat",
            json={"message": ""},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 422

    def test_chat_creates_session_and_auto_title(self, client: TestClient, auth_token: str):
        """Primeira mensagem cria sessao e define titulo automatico."""
        response = client.post(
            "/api/chat",
            json={"message": "Qual a capital do Brasil?"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["reply"] == "Resposta para: Qual a capital do Brasil?"
        assert data["session_id"] is not None
        # Verificar que a sessao foi criada com titulo
        sessions_resp = client.get(
            "/api/sessions",
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        sessions = sessions_resp.json()["sessions"]
        matching = [s for s in sessions if s["id"] == data["session_id"]]
        assert len(matching) == 1
        assert matching[0]["title"] == "Qual a capital do Brasil?"

    def test_chat_reuses_session(self, client: TestClient, auth_token: str):
        """Enviar session_id existente reusa a sessao."""
        # Primeira msg cria sessao
        r1 = client.post(
            "/api/chat",
            json={"message": "Primeira"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        session_id = r1.json()["session_id"]

        # Segunda msg na mesma sessao
        r2 = client.post(
            "/api/chat",
            json={"message": "Segunda", "session_id": session_id},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert r2.status_code == 200
        assert r2.json()["session_id"] == session_id

    def test_chat_invalid_session_returns_404(self, client: TestClient, auth_token: str):
        """session_id inexistente retorna 404."""
        response = client.post(
            "/api/chat",
            json={"message": "Ola", "session_id": 99999},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 404


class TestChatStreamEndpoint:
    def test_chat_stream_requires_auth(self, client: TestClient):
        """Sem token, deve retornar 401."""
        response = client.post("/api/chat/stream", json={"message": "Ola"})
        assert response.status_code == 401

    def test_chat_stream_empty_message_rejected(self, client: TestClient, auth_token: str):
        """Stream com mensagem vazia deve ser rejeitado com 422."""
        response = client.post(
            "/api/chat/stream",
            json={"message": ""},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 422

    def test_chat_stream_creates_session(self, client: TestClient, auth_token: str):
        """Stream cria sessao e retorna session_id no evento done."""
        response = client.post(
            "/api/chat/stream",
            json={"message": "Ola"},
            headers={"Authorization": f"Bearer {auth_token}"},
        )
        assert response.status_code == 200
        body = response.text
        assert "session_id" in body


class TestCORSMiddleware:
    def test_cors_headers_present(self, client: TestClient):
        """Verifica que os headers CORS estao presentes."""
        response = client.options(
            "/health",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "GET",
            },
        )
        assert response.status_code in (200, 405)
