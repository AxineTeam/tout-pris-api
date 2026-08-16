from polyfactory.factories.pydantic_factory import ModelFactory

from app.schemas import StuffListCreate


class StuffListCreateFactory(ModelFactory[StuffListCreate]):
    __model__ = StuffListCreate
