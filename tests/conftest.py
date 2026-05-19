import os
from pathlib import Path

_test_db = Path(__file__).resolve().parent.parent / ".pytest.sqlite3"
os.environ["SQLITE_PATH"] = str(_test_db)

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.auth import hash_password
from app.database import Base, SessionLocal, engine
from app.main import app
from app.models import User


@pytest.fixture(autouse=True)
def reset_db():
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield


@pytest.fixture
def db() -> Session:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


@pytest.fixture
def user(db: Session) -> User:
    u = User(username="testuser", password_hash=hash_password("pass1234"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


@pytest.fixture
def auth_client(client: TestClient, user: User):
    client.post(
        "/login",
        data={"username": user.username, "password": "pass1234"},
    )
    return client


@pytest.fixture
def other_user(db: Session) -> User:
    u = User(username="other", password_hash=hash_password("pass5678"))
    db.add(u)
    db.commit()
    db.refresh(u)
    return u
