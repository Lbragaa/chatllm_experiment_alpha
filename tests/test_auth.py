from __future__ import annotations

import pytest
from fastapi.testclient import TestClient


class TestRegisterEndpoint:
    def test_register_success(self, client: TestClient):
        response = client.post(
            "/api/auth/register",
            json={"email": "teste@email.com", "password": "123456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "teste@email.com"
        assert "user_id" in data

    def test_register_duplicate_email(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={"email": "dup@email.com", "password": "123456"},
        )
        response = client.post(
            "/api/auth/register",
            json={"email": "dup@email.com", "password": "654321"},
        )
        assert response.status_code == 409
        assert "ja cadastrado" in response.json()["detail"].lower()

    def test_register_invalid_email(self, client: TestClient):
        response = client.post(
            "/api/auth/register",
            json={"email": "invalido", "password": "123456"},
        )
        assert response.status_code == 422

    def test_register_short_password(self, client: TestClient):
        response = client.post(
            "/api/auth/register",
            json={"email": "curta@email.com", "password": "123"},
        )
        assert response.status_code == 422

    def test_register_empty_fields(self, client: TestClient):
        response = client.post(
            "/api/auth/register",
            json={"email": "", "password": "123456"},
        )
        assert response.status_code == 422


class TestLoginEndpoint:
    def test_login_success(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={"email": "login@email.com", "password": "123456"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "login@email.com", "password": "123456"},
        )
        assert response.status_code == 200
        data = response.json()
        assert "token" in data
        assert data["email"] == "login@email.com"

    def test_login_wrong_password(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={"email": "wrongpw@email.com", "password": "123456"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "wrongpw@email.com", "password": "senhaerrada"},
        )
        assert response.status_code == 401

    def test_login_nonexistent_user(self, client: TestClient):
        response = client.post(
            "/api/auth/login",
            json={"email": "naoexiste@email.com", "password": "123456"},
        )
        assert response.status_code == 401

    def test_login_case_insensitive_email(self, client: TestClient):
        client.post(
            "/api/auth/register",
            json={"email": "CaseTest@email.com", "password": "123456"},
        )
        response = client.post(
            "/api/auth/login",
            json={"email": "casetest@email.com", "password": "123456"},
        )
        assert response.status_code == 200


class TestMeEndpoint:
    def test_me_authenticated(self, client: TestClient):
        reg = client.post(
            "/api/auth/register",
            json={"email": "me@email.com", "password": "123456"},
        )
        token = reg.json()["token"]

        response = client.get(
            "/api/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == "me@email.com"

    def test_me_no_token(self, client: TestClient):
        response = client.get("/api/auth/me")
        assert response.status_code == 401

    def test_me_invalid_token(self, client: TestClient):
        response = client.get(
            "/api/auth/me",
            headers={"Authorization": "Bearer token_invalido"},
        )
        assert response.status_code == 401


class TestLogoutEndpoint:
    def test_logout_authenticated(self, client: TestClient):
        reg = client.post(
            "/api/auth/register",
            json={"email": "logout@email.com", "password": "123456"},
        )
        token = reg.json()["token"]

        response = client.post(
            "/api/auth/logout",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert response.status_code == 200
        assert response.json()["message"] == "Logout realizado com sucesso"

    def test_logout_no_token(self, client: TestClient):
        response = client.post("/api/auth/logout")
        assert response.status_code == 401

    def test_logout_revokes_only_current_token_and_survives_restart(self, client, engine):
        from backend.main import create_app
        from sqlalchemy import create_engine

        credentials = {"email": "revoke@example.com", "password": "123456"}
        token_a = client.post("/api/auth/register", json=credentials).json()["token"]
        token_b = client.post("/api/auth/login", json=credentials).json()["token"]
        a = {"Authorization": f"Bearer {token_a}"}
        b = {"Authorization": f"Bearer {token_b}"}
        assert client.post("/api/auth/logout", headers=a).status_code == 200
        # Fresh app and engine using the persisted file, no shared session/connection.
        reopened = create_engine(engine.url, connect_args={"check_same_thread": False})
        try:
            with TestClient(create_app(reopened)) as restarted:
                assert restarted.get("/api/auth/me", headers=a).status_code == 401
                assert restarted.get("/api/sessions", headers=a).status_code == 401
                assert restarted.post("/api/chat/stream", headers=a, json={"message": "Oi"}).status_code == 401
                assert restarted.get("/api/auth/me", headers=b).status_code == 200
                assert restarted.post("/api/auth/login", json=credentials).status_code == 200
        finally:
            reopened.dispose()

    def test_jwt_without_persisted_auth_session_is_rejected(self, client):
        from backend.services.auth import create_jwt_token
        response = client.post("/api/auth/register", json={"email": "old@example.com", "password": "123456"})
        data = response.json()
        old_token = create_jwt_token(data["user_id"], data["email"])
        assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_token}"}).status_code == 401
