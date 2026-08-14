from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import StuffList
from app.schemas import StuffListCreate, StuffListRead

router = APIRouter(prefix="/stufflists", tags=["stufflists"])

DbSession = Annotated[Session, Depends(get_db)]


@router.post("", response_model=StuffListRead, status_code=201)
def create_stufflist(payload: StuffListCreate, db: DbSession):
    stufflist = StuffList(name=payload.name)
    db.add(stufflist)
    db.commit()
    db.refresh(stufflist)
    return stufflist


@router.get("", response_model=list[StuffListRead])
def list_stufflists(db: DbSession):
    return db.scalars(select(StuffList)).all()


@router.get("/{stufflist_id}", response_model=StuffListRead)
def get_stufflist(stufflist_id: int, db: DbSession):
    stufflist = db.get(StuffList, stufflist_id)
    if stufflist is None:
        raise HTTPException(status_code=404, detail="StuffList not found")
    return stufflist


@router.delete("/{stufflist_id}", status_code=204)
def delete_stufflist(stufflist_id: int, db: DbSession):
    stufflist = db.get(StuffList, stufflist_id)
    if stufflist is None:
        raise HTTPException(status_code=404, detail="StuffList not found")
    db.delete(stufflist)
    db.commit()
