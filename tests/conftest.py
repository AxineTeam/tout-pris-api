import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.auth.tokens import create_access_token
from app.database import Base, enable_sqlite_pragmas, get_db
from app.main import app
from app.models import Identity, IdentityProvider, User

DEFAULT_EMAIL = "member@example.com"
DEFAULT_PASSWORD = "correct-horse-battery"


@pytest.fixture
def engine():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    event.listen(engine, "connect", enable_sqlite_pragmas)
    Base.metadata.create_all(bind=engine)
    return engine


@pytest.fixture
def db(engine):
    with sessionmaker(bind=engine, autoflush=False, autocommit=False)() as session:
        yield session


@pytest.fixture
def client(engine):
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


@pytest.fixture
def create_user(db):
    def factory(email: str = DEFAULT_EMAIL, password: str = DEFAULT_PASSWORD) -> User:
        user = User(email=email)
        user.identities.append(
            Identity(
                provider=IdentityProvider.password,
                provider_uid=email,
                secret=hash_password(password),
            )
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    return factory


@pytest.fixture
def user(create_user):
    return create_user()


@pytest.fixture
def credentials():
    return {"email": DEFAULT_EMAIL, "password": DEFAULT_PASSWORD}


@pytest.fixture
def authenticated_client(client, user):
    client.headers["Authorization"] = f"Bearer {create_access_token(user.id)}"
    return client
