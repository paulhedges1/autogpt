import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base
from app.dependencies import get_db
from app.main import app
from app.services.auth_service import hash_password
from app.models.user import User


@pytest.fixture(scope="session")
def engine():
    e = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=e)
    yield e
    Base.metadata.drop_all(bind=e)


@pytest.fixture(scope="session")
def SessionFactory(engine):
    return sessionmaker(bind=engine)


@pytest.fixture(scope="session")
def seeded_db(SessionFactory):
    session = SessionFactory()
    if not session.query(User).filter_by(username="testuser").first():
        session.add(User(username="testuser", hashed_password=hash_password("testpass"), is_active=True))
        session.commit()
    session.close()


@pytest.fixture
def db(SessionFactory, seeded_db):
    session = SessionFactory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture
def client(db):
    def override_get_db():
        yield db

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def auth_headers(client):
    resp = client.post("/api/auth/token", data={"username": "testuser", "password": "testpass"})
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
