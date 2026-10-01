import pytest
from fastapi.testclient import TestClient

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.base import Base
from app.main import create_app


@pytest.fixture
def session():
    engine = create_engine("sqlite+pysqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    factory = sessionmaker(bind=engine, future=True)
    db = factory()
    try:
        yield db
    finally:
        db.close()
        engine.dispose()


class MemoryMailer:
    def __init__(self):
        self.sent = {}

    def send_code(self, email: str, code: str) -> None:
        self.sent[email] = code


@pytest.fixture
def mailer():
    return MemoryMailer()


@pytest.fixture
def api(mailer, tmp_path):
    app = create_app(database_url=f"sqlite+pysqlite:///{tmp_path / 'api.db'}")
    app.state.email_sender = mailer
    with TestClient(app) as client:
        yield client


def register_email(client: TestClient, mailer: MemoryMailer, email: str) -> str:
    client.post("/api/v1/auth/code", json={"email": email})
    response = client.post(
        "/api/v1/auth/register",
        json={"email": email, "code": mailer.sent[email], "password": "S3cret!pass"},
    )
    response.raise_for_status()
    return response.json()["access_token"]


@pytest.fixture
def client_factory(api, mailer):
    def make(email: str | None = None):
        client = TestClient(api.app)
        if email:
            token = register_email(client, mailer, email)
            client.headers.update({"Authorization": f"Bearer {token}"})
        return client
    return make


@pytest.fixture
def owner_client(client_factory):
    return client_factory("owner@example.com")


@pytest.fixture
def member_client(client_factory):
    return client_factory("member@example.com")
