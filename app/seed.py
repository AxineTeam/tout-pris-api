from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.factories import StuffListCreateFactory
from app.models import StuffList

SEED_STUFFLIST_COUNT = 10
SEED_RANDOM_SEED = 0


def seed(db: Session, count: int = SEED_STUFFLIST_COUNT) -> list[StuffList]:
    StuffListCreateFactory.seed_random(SEED_RANDOM_SEED)
    stufflists = [StuffList(**StuffListCreateFactory.build().model_dump()) for _ in range(count)]
    db.add_all(stufflists)
    db.commit()
    return stufflists


def main() -> None:
    with SessionLocal() as db:
        created = seed(db)
    print(f"Seeded {len(created)} stufflists")


if __name__ == "__main__":
    main()
