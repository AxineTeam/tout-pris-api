from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app import seed as seed_module
from app.database import Base
from app.models import StuffList
from app.seed import main, seed


def in_memory_session_factory():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    return sessionmaker(bind=engine, autoflush=False, autocommit=False)


def test_seed_inserts_the_requested_count():
    session_factory = in_memory_session_factory()
    with session_factory() as db:
        created = seed(db, count=5)
        assert len(created) == 5
        assert db.query(StuffList).count() == 5
        assert all(stufflist.name for stufflist in created)


def test_seed_is_reproducible():
    first_factory = in_memory_session_factory()
    second_factory = in_memory_session_factory()
    with first_factory() as first_db, second_factory() as second_db:
        first_names = [stufflist.name for stufflist in seed(first_db)]
        second_names = [stufflist.name for stufflist in seed(second_db)]
    assert first_names == second_names


def test_main_seeds_through_the_session_factory(monkeypatch, capsys):
    monkeypatch.setattr(seed_module, "SessionLocal", in_memory_session_factory())
    main()
    assert "Seeded 10 stufflists" in capsys.readouterr().out
