import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.auth.passwords import hash_password
from app.auth.tokens import create_access_token
from app.database import Base, enable_sqlite_pragmas, get_db
from app.main import app
from app.models import (
    Household,
    HouseholdMember,
    HouseholdRole,
    Identity,
    IdentityProvider,
    Person,
    User,
)

DEFAULT_EMAIL = "member@example.com"
DEFAULT_PASSWORD = "correct-horse-battery"
OTHER_EMAIL = "outsider@example.com"


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


@pytest.fixture
def other_user(create_user):
    return create_user(email=OTHER_EMAIL)


@pytest.fixture
def create_household(db):
    def factory(owner: User, name: str) -> Household:
        household = Household(name=name)
        household.members.append(HouseholdMember(user_id=owner.id, role=HouseholdRole.owner))
        db.add(household)
        db.commit()
        db.refresh(household)
        return household

    return factory


@pytest.fixture
def create_person(db):
    def factory(household: Household, name: str) -> Person:
        person = Person(household_id=household.id, name=name)
        db.add(person)
        db.commit()
        db.refresh(person)
        return person

    return factory


@pytest.fixture
def household(create_household, user):
    return create_household(user, "Maison")


@pytest.fixture
def other_household(create_household, other_user):
    return create_household(other_user, "Chez les autres")


@pytest.fixture
def person(create_person, household):
    return create_person(household, "Alice")


@pytest.fixture
def other_person(create_person, other_household):
    return create_person(other_household, "Bob")


@pytest.fixture
def stored(db):
    def load(model, primary_key):
        db.expire_all()
        return db.get(model, primary_key)

    return load
