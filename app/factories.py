from polyfactory.factories.pydantic_factory import ModelFactory

from app.schemas import HouseholdCreate, PersonCreate


class HouseholdCreateFactory(ModelFactory[HouseholdCreate]):
    __model__ = HouseholdCreate

    @classmethod
    def name(cls) -> str:
        return f"Foyer {cls.__faker__.last_name()}"


class PersonCreateFactory(ModelFactory[PersonCreate]):
    __model__ = PersonCreate

    @classmethod
    def name(cls) -> str:
        return cls.__faker__.first_name()
