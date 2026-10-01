import logging

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


class Mailer:
    def __init__(self):
        self.sent: dict[str, str] = {}

    def send_code(self, email: str, code: str) -> None:
        self.sent[email] = code

    def last_code_for(self, email: str) -> str:
        return self.sent[email]


@pytest.fixture
def mailer():
    return Mailer()


@pytest.fixture
def client(mailer, tmp_path):
    app = create_app(database_url=f"sqlite+pysqlite:///{tmp_path / 'auth.db'}")
    app.state.email_sender = mailer
    with TestClient(app) as test_client:
        yield test_client


def test_register_and_login_with_email_code(client, mailer):
    client.post("/api/v1/auth/code", json={"email": "a@b.com"}).raise_for_status()
    code = mailer.last_code_for("a@b.com")
    response = client.post(
        "/api/v1/auth/register",
        json={"email": "a@b.com", "code": code, "password": "S3cret!pass"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_token"]
    assert body["refresh_token"]
    assert client.post(
        "/api/v1/auth/login",
        json={"email": "a@b.com", "password": "S3cret!pass"},
    ).status_code == 200


def test_code_is_not_written_to_logs(client, mailer, caplog):
    with caplog.at_level(logging.DEBUG):
        client.post("/api/v1/auth/code", json={"email": "log@b.com"})
    code = mailer.last_code_for("log@b.com")
    assert code
    assert code not in caplog.text


def test_code_is_single_use_and_response_does_not_contain_code(client, mailer):
    email = "once@b.com"
    first = client.post("/api/v1/auth/code", json={"email": email})
    assert first.status_code == 200
    assert "code" not in first.json()
    code = mailer.last_code_for(email)
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": code, "password": "S3cret!pass"},
    )
    assert register.status_code == 200
    assert client.post(
        "/api/v1/auth/register",
        json={"email": "once-2@b.com", "code": code, "password": "S3cret!pass"},
    ).status_code == 400


def test_wrong_code_is_rejected_and_limited(client, mailer):
    email = "wrong@b.com"
    client.post("/api/v1/auth/code", json={"email": email})
    for _ in range(5):
        response = client.post(
            "/api/v1/auth/register",
            json={"email": email, "code": "000000", "password": "S3cret!pass"},
        )
        assert response.status_code == 400
    assert client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": mailer.last_code_for(email), "password": "S3cret!pass"},
    ).status_code == 429


def test_resend_is_throttled(client):
    first = client.post("/api/v1/auth/code", json={"email": "throttle@b.com"})
    second = client.post("/api/v1/auth/code", json={"email": "throttle@b.com"})
    assert first.status_code == 200
    assert second.status_code == 429


def test_refresh_exchanges_refresh_token(client, mailer):
    client.post("/api/v1/auth/code", json={"email": "refresh@b.com"})
    body = client.post(
        "/api/v1/auth/register",
        json={"email": "refresh@b.com", "code": mailer.last_code_for("refresh@b.com"), "password": "S3cret!pass"},
    ).json()
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": body["refresh_token"]})
    assert refreshed.status_code == 200
    assert refreshed.json()["access_token"]
