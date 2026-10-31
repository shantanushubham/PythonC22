import os

os.environ.setdefault("JWT_SECRET", "test-secret-not-for-production-0123456789")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

import models.reminder  # noqa: F401  (register tables)
import models.user  # noqa: F401
from app import app
from core.database import Base, get_db


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSession()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


PASSWORD = "secret-pass"


def register(client, email="user@example.com", password=PASSWORD):
    response = client.post("/users/", json={"email": email, "password": password})
    assert response.status_code == 201, response.text
    return response.json()


def login(client, email="user@example.com", password=PASSWORD):
    response = client.post("/users/login", json={"email": email, "password": password})
    assert response.status_code == 200, response.text
    return response.json()


def auth_header(token):
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture()
def user(client):
    return register(client)


@pytest.fixture()
def tokens(client, user):
    return login(client)


@pytest.fixture()
def headers(tokens):
    return auth_header(tokens["access_token"])
