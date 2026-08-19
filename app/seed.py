from sqlalchemy.orm import Session

from app.auth.passwords import hash_password
from app.database import SessionLocal
from app.factories import HouseholdCreateFactory, PersonCreateFactory
from app.models import (
    Household,
    HouseholdMember,
    HouseholdRole,
    Identity,
    IdentityProvider,
    Person,
    User,
)

SEED_EMAIL = "demo@tout-pris.local"
SEED_PASSWORD = "tout-pris-demo"
SEED_PERSON_COUNT = 4
SEED_RANDOM_SEED = 0


def seed(db: Session, person_count: int = SEED_PERSON_COUNT) -> Household:
    HouseholdCreateFactory.seed_random(SEED_RANDOM_SEED)
    PersonCreateFactory.seed_random(SEED_RANDOM_SEED)

    user = User(email=SEED_EMAIL)
    user.identities.append(
        Identity(
            provider=IdentityProvider.password,
            provider_uid=SEED_EMAIL,
            secret=hash_password(SEED_PASSWORD),
        )
    )

    household = Household(**HouseholdCreateFactory.build().model_dump())
    household.members.append(HouseholdMember(user=user, role=HouseholdRole.owner))
    household.persons.extend(
        Person(**PersonCreateFactory.build().model_dump()) for _ in range(person_count)
    )

    db.add(household)
    db.commit()
    db.refresh(household)
    return household


def main() -> None:
    with SessionLocal() as db:
        household = seed(db)
        person_count = len(household.persons)
    print(f"Seeded household {household.name!r} with {person_count} persons")
    print(f"Sign in with {SEED_EMAIL} / {SEED_PASSWORD}")


if __name__ == "__main__":
    main()
