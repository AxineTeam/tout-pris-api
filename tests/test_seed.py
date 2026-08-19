from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed as seed_module
from app.auth.passwords import verify_password
from app.database import Base
from app.models import HouseholdRole, Person, User
from app.seed import SEED_EMAIL, SEED_PASSWORD, main, seed


def in_memory_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_seed_creates_a_household_with_its_persons():
    with in_memory_session_factory()() as db:
        household = seed(db, person_count=3)

        assert household.name
        assert len(household.persons) == 3
        assert db.query(Person).count() == 3


def test_seed_creates_an_owner_with_a_password_identity():
    with in_memory_session_factory()() as db:
        household = seed(db)

        membership = household.members[0]
        assert membership.role == HouseholdRole.owner
        user = db.query(User).one()
        assert user.email == SEED_EMAIL
        assert membership.user_id == user.id
        assert verify_password(SEED_PASSWORD, user.identities[0].secret)


def test_seed_is_reproducible():
    with in_memory_session_factory()() as first_db, in_memory_session_factory()() as second_db:
        first = seed(first_db)
        second = seed(second_db)
        first_names = (first.name, [person.name for person in first.persons])
        second_names = (second.name, [person.name for person in second.persons])

    assert first_names == second_names


def test_main_seeds_through_the_session_factory(monkeypatch, capsys):
    monkeypatch.setattr(seed_module, "SessionLocal", in_memory_session_factory())
    main()

    output = capsys.readouterr().out
    assert "with 4 persons" in output
    assert SEED_EMAIL in output
