from pydantic import BaseModel, ConfigDict


class StuffListCreate(BaseModel):
    name: str


class StuffListRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
