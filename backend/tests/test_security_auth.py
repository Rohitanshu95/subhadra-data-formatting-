"""
Tests for JWT Security and Authentication endpoints.
"""

import pytest
from fastapi.testclient import TestClient
from app.core.security import create_access_token, verify_access_token
from app.main import app

client = TestClient(app)


class TestSecurityAuth:
    def test_jwt_create_and_verify(self):
        payload = {"sub": "operator1", "role": "admin"}
        token = create_access_token(payload, expires_in=3600)
        assert isinstance(token, str)

        decoded = verify_access_token(token)
        assert decoded is not None
        assert decoded["sub"] == "operator1"
        assert decoded["role"] == "admin"

    def test_jwt_expired_token(self):
        payload = {"sub": "operator1"}
        token = create_access_token(payload, expires_in=-10)  # already expired
        decoded = verify_access_token(token)
        assert decoded is None

    def test_login_api_endpoint(self):
        # Valid login
        resp = client.post("/api/auth/login", json={"username": "admin", "password": "password"})
        assert resp.status_code == 200
        data = resp.json()
        assert "access_token" in data
        assert data["username"] == "admin"

        # Invalid login
        bad_resp = client.post("/api/auth/login", json={"username": "admin", "password": "wrong_password"})
        assert bad_resp.status_code == 401

    def test_protected_me_endpoint(self):
        login_resp = client.post("/api/auth/login", json={"username": "admin", "password": "password"})
        token = login_resp.json()["access_token"]

        headers = {"Authorization": f"Bearer {token}"}
        me_resp = client.get("/api/auth/me", headers=headers)
        assert me_resp.status_code == 200
        assert me_resp.json()["username"] == "admin"
